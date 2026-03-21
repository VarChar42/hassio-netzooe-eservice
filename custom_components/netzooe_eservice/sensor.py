"""NetzOÖ eService sensors."""
from __future__ import annotations

import datetime
import hashlib
import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN
from .eservice_api import EServiceApi

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    """Set up NetzOÖ sensors from a config entry."""
    api: EServiceApi = hass.data[DOMAIN][entry.entry_id]
    coordinator = ApiCoordinator(hass, api)
    await coordinator.async_config_entry_first_refresh()

    entities = []
    data = api.data
    seen_accounts = set()

    for meter_id, meter in data.get("meters", {}).items():
        device = _device_info(meter)

        # Meter reading (total kWh)
        entities.append(MeterReadingSensor(coordinator, meter_id, device))

        # Daily consumption from smart meter
        if meter.get("smart_meter_active"):
            entities.append(DailyConsumptionSensor(coordinator, meter_id, device))
            entities.append(WeeklyConsumptionSensor(coordinator, meter_id, device))

        # Monthly trend
        if meter.get("monthly_trend_current"):
            entities.append(MonthlyConsumptionSensor(coordinator, meter_id, device))
            entities.append(MonthlyConsumptionPreviousSensor(coordinator, meter_id, device))
            entities.append(DailyAverageSensor(coordinator, meter_id, device))

        # Contract power
        if meter.get("contract_power") is not None:
            entities.append(ContractPowerSensor(coordinator, meter_id, device))

        # Account-level sensors (invoice, installment) - only once per contract account
        can = meter.get("contract_account", "")
        if can and can not in seen_accounts:
            seen_accounts.add(can)
            account = data.get("accounts", {}).get(can, {})
            if account.get("invoices"):
                entities.append(LastInvoiceAmountSensor(coordinator, meter_id, can, device))
                entities.append(LastInvoiceDateSensor(coordinator, meter_id, can, device))
            if account.get("installment"):
                entities.append(InstallmentAmountSensor(coordinator, meter_id, can, device))
                entities.append(NextInstallmentDateSensor(coordinator, meter_id, can, device))

        # Diagnostic sensors
        if meter.get("supplier"):
            entities.append(SupplierSensor(coordinator, meter_id, device))
        if meter.get("smart_meter_type"):
            entities.append(SmartMeterTypeSensor(coordinator, meter_id, device))
        if meter.get("traffic_light"):
            entities.append(GridTrafficLightSensor(coordinator, meter_id, device))

        # Energy community sensors
        for ec in meter.get("energy_communities", []):
            ec_id = ec["id"]
            ec_name = ec["name"]
            entities.append(EnergyCommunityOwnCoverageSensor(coordinator, meter_id, ec_id, ec_name, device))
            entities.append(EnergyCommunityConsumptionSensor(coordinator, meter_id, ec_id, ec_name, device))

    async_add_entities(entities)


def _device_info(meter: dict) -> DeviceInfo:
    """Create device info for a meter."""
    return DeviceInfo(
        identifiers={(DOMAIN, meter["meter_number"])},
        name=f"NetzOÖ Meter {meter['meter_number']}",
        manufacturer="Netz Oberösterreich",
        model=meter.get("smart_meter_type", "Unknown"),
        sw_version=meter.get("scale_type", ""),
        configuration_url="https://eservice.netzooe.at/app/portal/dashboard",
    )


class ApiCoordinator(DataUpdateCoordinator):
    """Coordinator to fetch data from NetzOÖ API."""

    def __init__(self, hass: HomeAssistant, api: EServiceApi):
        super().__init__(
            hass, _LOGGER, name="NetzOÖ eService",
            update_interval=datetime.timedelta(hours=1),
        )
        self.api = api

    async def _async_update_data(self):
        try:
            await self.hass.async_add_executor_job(self.api.update)
        except Exception as err:
            raise UpdateFailed(f"Error fetching NetzOÖ data: {err}") from err
        return self.api.data


class _BaseSensor(CoordinatorEntity, SensorEntity):
    """Base sensor with translation support."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ApiCoordinator, meter_id: str, device: DeviceInfo):
        super().__init__(coordinator)
        self._meter_id = meter_id
        self._attr_device_info = device

    def _meter(self) -> dict:
        return self.coordinator.data.get("meters", {}).get(self._meter_id, {})


# ── Energy sensors ──────────────────────────────────────────────────────


class MeterReadingSensor(_BaseSensor):
    """Total meter reading (kWh)."""

    _attr_translation_key = "meter_reading"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

    def __init__(self, coordinator, meter_id, device):
        super().__init__(coordinator, meter_id, device)
        self._attr_unique_id = f"{meter_id}_reading"

    @property
    def native_value(self):
        return self._meter().get("meter_reading")

    @property
    def extra_state_attributes(self):
        m = self._meter()
        attrs = {}
        if m.get("meter_reading_timestamp"):
            attrs["last_reading_time"] = m["meter_reading_timestamp"]
        if m.get("mpan"):
            attrs["mpan"] = m["mpan"]
        return attrs


class DailyConsumptionSensor(_BaseSensor):
    """Yesterday's consumption from smart meter profile (kWh)."""

    _attr_translation_key = "daily_consumption"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_icon = "mdi:lightning-bolt"

    def __init__(self, coordinator, meter_id, device):
        super().__init__(coordinator, meter_id, device)
        self._attr_unique_id = f"{meter_id}_daily_consumption"

    @property
    def native_value(self):
        return self._meter().get("yesterday_consumption")


class WeeklyConsumptionSensor(_BaseSensor):
    """Last 7 days consumption (kWh)."""

    _attr_translation_key = "weekly_consumption"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_icon = "mdi:chart-bar"

    def __init__(self, coordinator, meter_id, device):
        super().__init__(coordinator, meter_id, device)
        self._attr_unique_id = f"{meter_id}_weekly_consumption"

    @property
    def native_value(self):
        return self._meter().get("weekly_consumption")


class MonthlyConsumptionSensor(_BaseSensor):
    """Current 30-day period consumption (kWh)."""

    _attr_translation_key = "monthly_consumption"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_icon = "mdi:calendar-month"

    def __init__(self, coordinator, meter_id, device):
        super().__init__(coordinator, meter_id, device)
        self._attr_unique_id = f"{meter_id}_monthly_consumption"

    @property
    def native_value(self):
        trend = self._meter().get("monthly_trend_current")
        return trend["sum"] if trend else None

    @property
    def extra_state_attributes(self):
        trend = self._meter().get("monthly_trend_current")
        if not trend:
            return {}
        return {
            "period_from": trend.get("from", ""),
            "period_to": trend.get("to", ""),
            "days": trend.get("days", 0),
        }


class MonthlyConsumptionPreviousSensor(_BaseSensor):
    """Previous 30-day period consumption (kWh)."""

    _attr_translation_key = "monthly_consumption_previous"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_icon = "mdi:calendar-month-outline"

    def __init__(self, coordinator, meter_id, device):
        super().__init__(coordinator, meter_id, device)
        self._attr_unique_id = f"{meter_id}_monthly_consumption_previous"

    @property
    def native_value(self):
        trend = self._meter().get("monthly_trend_previous")
        return trend["sum"] if trend else None

    @property
    def extra_state_attributes(self):
        trend = self._meter().get("monthly_trend_previous")
        if not trend:
            return {}
        return {
            "period_from": trend.get("from", ""),
            "period_to": trend.get("to", ""),
            "days": trend.get("days", 0),
        }


class DailyAverageSensor(_BaseSensor):
    """Average daily consumption for current period (kWh/day)."""

    _attr_translation_key = "daily_average"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_icon = "mdi:chart-line"

    def __init__(self, coordinator, meter_id, device):
        super().__init__(coordinator, meter_id, device)
        self._attr_unique_id = f"{meter_id}_daily_average"

    @property
    def native_value(self):
        trend = self._meter().get("monthly_trend_current")
        if trend and trend.get("per_day"):
            return round(trend["per_day"], 2)
        return None


class ContractPowerSensor(_BaseSensor):
    """Contracted power (kW)."""

    _attr_translation_key = "contract_power"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
    _attr_icon = "mdi:flash"

    def __init__(self, coordinator, meter_id, device):
        super().__init__(coordinator, meter_id, device)
        self._attr_unique_id = f"{meter_id}_contract_power"

    @property
    def native_value(self):
        return self._meter().get("contract_power")


# ── Financial sensors ───────────────────────────────────────────────────


class LastInvoiceAmountSensor(_BaseSensor):
    """Last invoice amount (EUR)."""

    _attr_translation_key = "last_invoice_amount"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "EUR"
    _attr_icon = "mdi:receipt-text"

    def __init__(self, coordinator, meter_id, can, device):
        super().__init__(coordinator, meter_id, device)
        self._can = can
        self._attr_unique_id = f"{can}_last_invoice_amount"

    @property
    def native_value(self):
        account = self.coordinator.data.get("accounts", {}).get(self._can, {})
        invoices = account.get("invoices", [])
        return invoices[0]["total"] if invoices else None

    @property
    def extra_state_attributes(self):
        account = self.coordinator.data.get("accounts", {}).get(self._can, {})
        invoices = account.get("invoices", [])
        if not invoices:
            return {}
        return {
            "invoice_number": invoices[0].get("number", ""),
            "invoice_date": invoices[0].get("date", ""),
        }


class LastInvoiceDateSensor(_BaseSensor):
    """Last invoice date."""

    _attr_translation_key = "last_invoice_date"
    _attr_device_class = SensorDeviceClass.DATE
    _attr_icon = "mdi:calendar-text"

    def __init__(self, coordinator, meter_id, can, device):
        super().__init__(coordinator, meter_id, device)
        self._can = can
        self._attr_unique_id = f"{can}_last_invoice_date"

    @property
    def native_value(self):
        account = self.coordinator.data.get("accounts", {}).get(self._can, {})
        invoices = account.get("invoices", [])
        if invoices and invoices[0].get("date"):
            try:
                return datetime.date.fromisoformat(invoices[0]["date"])
            except ValueError:
                return None
        return None


class InstallmentAmountSensor(_BaseSensor):
    """Monthly installment amount (EUR)."""

    _attr_translation_key = "installment_amount"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "EUR"
    _attr_icon = "mdi:cash-clock"

    def __init__(self, coordinator, meter_id, can, device):
        super().__init__(coordinator, meter_id, device)
        self._can = can
        self._attr_unique_id = f"{can}_installment_amount"

    @property
    def native_value(self):
        account = self.coordinator.data.get("accounts", {}).get(self._can, {})
        inst = account.get("installment")
        return inst["amount"] if inst else None

    @property
    def extra_state_attributes(self):
        account = self.coordinator.data.get("accounts", {}).get(self._can, {})
        inst = account.get("installment")
        if not inst:
            return {}
        return {
            "cycle": inst.get("cycle", ""),
            "period_from": inst.get("begin_date", ""),
            "period_to": inst.get("end_date", ""),
        }


class NextInstallmentDateSensor(_BaseSensor):
    """Next installment due date."""

    _attr_translation_key = "next_installment_date"
    _attr_device_class = SensorDeviceClass.DATE
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator, meter_id, can, device):
        super().__init__(coordinator, meter_id, device)
        self._can = can
        self._attr_unique_id = f"{can}_next_installment_date"

    @property
    def native_value(self):
        account = self.coordinator.data.get("accounts", {}).get(self._can, {})
        inst = account.get("installment")
        if inst and inst.get("next_due_date"):
            try:
                return datetime.date.fromisoformat(inst["next_due_date"])
            except ValueError:
                return None
        return None


# ── Diagnostic sensors ──────────────────────────────────────────────────


class SupplierSensor(_BaseSensor):
    """Energy supplier name."""

    _attr_translation_key = "supplier"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:domain"

    def __init__(self, coordinator, meter_id, device):
        super().__init__(coordinator, meter_id, device)
        self._attr_unique_id = f"{meter_id}_supplier"

    @property
    def native_value(self):
        return self._meter().get("supplier")


class SmartMeterTypeSensor(_BaseSensor):
    """Smart meter type."""

    _attr_translation_key = "smart_meter_type"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:meter-electric"

    def __init__(self, coordinator, meter_id, device):
        super().__init__(coordinator, meter_id, device)
        self._attr_unique_id = f"{meter_id}_smart_meter_type"

    @property
    def native_value(self):
        return self._meter().get("smart_meter_type")


class GridTrafficLightSensor(_BaseSensor):
    """Grid traffic light color (RED/YELLOW/GREEN)."""

    _attr_translation_key = "grid_traffic_light"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:traffic-light"

    def __init__(self, coordinator, meter_id, device):
        super().__init__(coordinator, meter_id, device)
        self._attr_unique_id = f"{meter_id}_grid_traffic_light"

    @property
    def native_value(self):
        return self._meter().get("traffic_light")


# ── Energy community sensors ───────────────────────────────────────────


class EnergyCommunityOwnCoverageSensor(_BaseSensor):
    """Energy community own coverage (kWh/day)."""

    _attr_translation_key = "ec_own_coverage"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_icon = "mdi:solar-power"

    def __init__(self, coordinator, meter_id, ec_id, ec_name, device):
        super().__init__(coordinator, meter_id, device)
        self._ec_id = ec_id
        self._attr_unique_id = f"{meter_id}_ec_{hashlib.md5(ec_id.encode()).hexdigest()[:12]}_own_coverage"
        self._attr_translation_placeholders = {"energy_community_name": ec_name}

    @property
    def native_value(self):
        for ec in self._meter().get("energy_communities", []):
            if ec["id"] == self._ec_id:
                return ec.get("own_coverage")
        return None


class EnergyCommunityConsumptionSensor(_BaseSensor):
    """Energy community consumption per contribution factor (kWh/day)."""

    _attr_translation_key = "ec_consumption"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_icon = "mdi:home-lightning-bolt"

    def __init__(self, coordinator, meter_id, ec_id, ec_name, device):
        super().__init__(coordinator, meter_id, device)
        self._ec_id = ec_id
        self._attr_unique_id = f"{meter_id}_ec_{hashlib.md5(ec_id.encode()).hexdigest()[:12]}_consumption"
        self._attr_translation_placeholders = {"energy_community_name": ec_name}

    @property
    def native_value(self):
        for ec in self._meter().get("energy_communities", []):
            if ec["id"] == self._ec_id:
                return ec.get("consumption")
        return None

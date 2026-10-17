"""Sensors for NetzOÖ eService."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import NetzOoeConfigEntry, NetzOoeCoordinator
from .entity import NetzOoeEntity, account_meters, async_track_entities, community_hash
from .models import TRAFFIC_LIGHTS, Account, EnergyCommunity, Invoice, Meter, NetzOoeData, Period

PARALLEL_UPDATES = 0


def _period_attrs(period: Period | None) -> dict[str, Any]:
    if not period:
        return {}
    return {"period_start": period.start, "period_end": period.end, "days": period.days}


def _last_invoice(account: Account) -> Invoice | None:
    dated = [inv for inv in account.invoices if inv.date]
    if dated:
        return max(dated, key=lambda inv: inv.date)
    return account.invoices[0] if account.invoices else None


@dataclass(frozen=True, kw_only=True)
class MeterSensorDescription(SensorEntityDescription):
    value_fn: Callable[[Meter], StateType | date]
    exists_fn: Callable[[Meter], bool] = lambda meter: True
    attrs_fn: Callable[[Meter], dict[str, Any]] | None = None


@dataclass(frozen=True, kw_only=True)
class AccountSensorDescription(SensorEntityDescription):
    value_fn: Callable[[Account], StateType | date]
    exists_fn: Callable[[Account], bool]
    attrs_fn: Callable[[Account], dict[str, Any]] | None = None


ENERGY = {
    "device_class": SensorDeviceClass.ENERGY,
    "native_unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
}

METER_SENSORS: tuple[MeterSensorDescription, ...] = (
    MeterSensorDescription(
        key="consumption_total",
        translation_key="consumption_total",
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
        value_fn=lambda m: m.consumption_total,
        exists_fn=lambda m: m.consumption_total is not None,
        attrs_fn=lambda m: {"last_reading": m.reading_timestamp},
        **ENERGY,
    ),
    MeterSensorDescription(
        key="feed_in_total",
        translation_key="feed_in_total",
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
        value_fn=lambda m: m.feed_in_total,
        exists_fn=lambda m: m.feed_in_total is not None,
        **ENERGY,
    ),
    MeterSensorDescription(
        key="peak_power",
        translation_key="peak_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda m: m.peak_power.value if m.peak_power else None,
        exists_fn=lambda m: m.peak_power is not None,
        attrs_fn=lambda m: {"timestamp": m.peak_power.timestamp} if m.peak_power else {},
    ),
    MeterSensorDescription(
        key="daily_consumption",
        translation_key="daily_consumption",
        value_fn=lambda m: m.consumption_yesterday,
        exists_fn=lambda m: m.smart_meter_active,
        **ENERGY,
    ),
    MeterSensorDescription(
        key="weekly_consumption",
        translation_key="weekly_consumption",
        value_fn=lambda m: m.consumption_week,
        exists_fn=lambda m: m.smart_meter_active,
        **ENERGY,
    ),
    MeterSensorDescription(
        key="monthly_consumption",
        translation_key="monthly_consumption",
        value_fn=lambda m: m.trend_current.value if m.trend_current else None,
        exists_fn=lambda m: m.trend_current is not None,
        attrs_fn=lambda m: _period_attrs(m.trend_current),
        **ENERGY,
    ),
    MeterSensorDescription(
        key="monthly_consumption_previous",
        translation_key="monthly_consumption_previous",
        value_fn=lambda m: m.trend_previous.value if m.trend_previous else None,
        exists_fn=lambda m: m.trend_previous is not None,
        attrs_fn=lambda m: _period_attrs(m.trend_previous),
        **ENERGY,
    ),
    MeterSensorDescription(
        key="daily_average",
        translation_key="daily_average",
        native_unit_of_measurement="kWh/d",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda m: m.trend_current.per_day if m.trend_current else None,
        exists_fn=lambda m: m.trend_current is not None,
    ),
    MeterSensorDescription(
        key="yearly_consumption",
        translation_key="yearly_consumption",
        suggested_display_precision=0,
        value_fn=lambda m: m.yearly_current.value if m.yearly_current else None,
        exists_fn=lambda m: m.yearly_current is not None,
        attrs_fn=lambda m: {
            **_period_attrs(m.yearly_current),
            "previous_value": m.yearly_previous.value if m.yearly_previous else None,
        },
        **ENERGY,
    ),
    MeterSensorDescription(
        key="total_consumption",
        translation_key="total_consumption",
        suggested_display_precision=0,
        value_fn=lambda m: m.billing_total,
        exists_fn=lambda m: m.billing_total is not None,
        attrs_fn=lambda m: {"periods": [asdict(p) for p in m.billing_periods]},
        **ENERGY,
    ),
    MeterSensorDescription(
        key="contract_power",
        translation_key="contract_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda m: m.contract_power,
        exists_fn=lambda m: m.smart_meter_active,
    ),
    MeterSensorDescription(
        key="supplier",
        translation_key="supplier",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda m: m.supplier,
        exists_fn=lambda m: bool(m.supplier),
    ),
    MeterSensorDescription(
        key="smart_meter_type",
        translation_key="smart_meter_type",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda m: m.smart_meter_type,
        exists_fn=lambda m: bool(m.smart_meter_type),
    ),
    MeterSensorDescription(
        key="grid_traffic_light",
        translation_key="grid_traffic_light",
        device_class=SensorDeviceClass.ENUM,
        options=list(TRAFFIC_LIGHTS),
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda m: m.traffic_light,
    ),
    MeterSensorDescription(
        key="move_in_date",
        translation_key="move_in_date",
        device_class=SensorDeviceClass.DATE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda m: m.move_in_date,
        exists_fn=lambda m: m.move_in_date is not None,
    ),
    MeterSensorDescription(
        key="address",
        translation_key="address",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda m: m.address,
        exists_fn=lambda m: bool(m.address),
    ),
)

ACCOUNT_SENSORS: tuple[AccountSensorDescription, ...] = (
    AccountSensorDescription(
        key="last_invoice_amount",
        translation_key="last_invoice_amount",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="EUR",
        value_fn=lambda a: inv.total if (inv := _last_invoice(a)) else None,
        exists_fn=lambda a: bool(a.invoices),
        attrs_fn=lambda a: {"invoices": [asdict(inv) for inv in a.invoices]},
    ),
    AccountSensorDescription(
        key="last_invoice_date",
        translation_key="last_invoice_date",
        device_class=SensorDeviceClass.DATE,
        value_fn=lambda a: inv.date if (inv := _last_invoice(a)) else None,
        exists_fn=lambda a: bool(a.invoices),
    ),
    AccountSensorDescription(
        key="installment_amount",
        translation_key="installment_amount",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="EUR",
        value_fn=lambda a: a.installment.amount if a.installment else None,
        exists_fn=lambda a: a.installment is not None,
        attrs_fn=lambda a: (
            {
                "cycle": a.installment.cycle,
                "period_start": a.installment.start,
                "period_end": a.installment.end,
            }
            if a.installment
            else {}
        ),
    ),
    AccountSensorDescription(
        key="next_installment_date",
        translation_key="next_installment_date",
        device_class=SensorDeviceClass.DATE,
        value_fn=lambda a: a.installment.next_due_date if a.installment else None,
        exists_fn=lambda a: a.installment is not None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NetzOoeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data

    def build(data: NetzOoeData) -> Iterator[SensorEntity]:
        for meter_id, meter in data.meters.items():
            for description in METER_SENSORS:
                if description.exists_fn(meter):
                    yield MeterSensor(coordinator, meter_id, description)
            for register in meter.tariff_registers:
                yield RegisterSensor(coordinator, meter_id, register.obis)
            for community in meter.energy_communities:
                yield CommunitySensor(coordinator, meter_id, community.id, "own_coverage")
                yield CommunitySensor(coordinator, meter_id, community.id, "consumption")
        for meter in account_meters(data).values():
            account = data.accounts.get(meter.contract_account)
            for description in ACCOUNT_SENSORS:
                if account and description.exists_fn(account):
                    yield AccountSensor(coordinator, meter.id, description)
        if data.meters:
            yield UnreadMessagesSensor(coordinator, next(iter(data.meters)))

    async_track_entities(coordinator, async_add_entities, build)


class MeterSensor(NetzOoeEntity, SensorEntity):
    entity_description: MeterSensorDescription

    def __init__(
        self, coordinator: NetzOoeCoordinator, meter_id: str, description: MeterSensorDescription
    ) -> None:
        super().__init__(coordinator, meter_id, f"{meter_id}_{description.key}")
        self.entity_description = description

    @property
    def native_value(self) -> StateType | date:
        return self.entity_description.value_fn(self.meter) if self.meter else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.meter and self.entity_description.attrs_fn:
            return self.entity_description.attrs_fn(self.meter)
        return None


class AccountSensor(NetzOoeEntity, SensorEntity):
    entity_description: AccountSensorDescription

    def __init__(
        self, coordinator: NetzOoeCoordinator, meter_id: str, description: AccountSensorDescription
    ) -> None:
        account = coordinator.data.meters[meter_id].contract_account
        super().__init__(coordinator, meter_id, f"{account}_{description.key}")
        self.entity_description = description

    @property
    def native_value(self) -> StateType | date:
        return self.entity_description.value_fn(self.account) if self.account else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.account and self.entity_description.attrs_fn:
            return self.entity_description.attrs_fn(self.account)
        return None


class RegisterSensor(NetzOoeEntity, SensorEntity):
    _attr_translation_key = "register"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_suggested_display_precision = 1

    def __init__(self, coordinator: NetzOoeCoordinator, meter_id: str, obis: str) -> None:
        super().__init__(coordinator, meter_id, f"{meter_id}_register_{obis}")
        self._obis = obis
        self._attr_translation_placeholders = {"register": obis}

    @property
    def native_value(self) -> float | None:
        if not self.meter:
            return None
        return next((r.value for r in self.meter.registers if r.obis == self._obis), None)


class CommunitySensor(NetzOoeEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator: NetzOoeCoordinator, meter_id: str, community_id: str, kind: str) -> None:
        super().__init__(coordinator, meter_id, f"{meter_id}_ec_{community_hash(community_id)}_{kind}")
        self._community_id = community_id
        self._kind = kind
        self._attr_translation_key = f"ec_{kind}"
        community = self._community()
        self._attr_translation_placeholders = {"community": community.name if community else community_id}

    def _community(self) -> EnergyCommunity | None:
        if not self.meter:
            return None
        return next((c for c in self.meter.energy_communities if c.id == self._community_id), None)

    @property
    def native_value(self) -> float | None:
        community = self._community()
        return getattr(community, self._kind) if community else None


class UnreadMessagesSensor(NetzOoeEntity, SensorEntity):
    _attr_translation_key = "unread_messages"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: NetzOoeCoordinator, meter_id: str) -> None:
        super().__init__(coordinator, meter_id, f"{coordinator.data.business_partner}_unread_messages")

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data.unread_messages

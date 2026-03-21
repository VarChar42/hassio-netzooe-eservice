"""NetzOÖ eService binary sensors."""
from __future__ import annotations

import hashlib
import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .helpers import device_info

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    """Set up NetzOÖ binary sensors from a config entry."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    coordinator = entry_data["coordinator"]

    entities = []
    data = coordinator.data
    seen_accounts = set()

    for meter_id, meter in data.get("meters", {}).items():
        device = device_info(meter)

        # Smart meter active
        entities.append(SmartMeterActiveSensor(coordinator, meter_id, device))

        # Disconnection notification
        entities.append(DisconnectionNotificationSensor(coordinator, meter_id, device))

        # Account-level binary sensors - only once per contract account
        can = meter.get("contract_account", "")
        if can and can not in seen_accounts:
            seen_accounts.add(can)
            entities.append(PaperlessBillingSensor(coordinator, meter_id, can, device))

        # Energy community active sensors
        for ec in meter.get("energy_communities", []):
            ec_id = ec.get("id", "")
            ec_name = ec.get("name", "")
            entities.append(EnergyCommunityActiveSensor(coordinator, meter_id, ec_id, ec_name, device))

    async_add_entities(entities)


class _BaseBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Base binary sensor with translation support."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, meter_id: str, device: DeviceInfo):
        super().__init__(coordinator)
        self._meter_id = meter_id
        self._attr_device_info = device

    def _meter(self) -> dict:
        return self.coordinator.data.get("meters", {}).get(self._meter_id, {})


class SmartMeterActiveSensor(_BaseBinarySensor):
    """Whether the smart meter is active."""

    _attr_translation_key = "smart_meter_active"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:meter-electric"

    def __init__(self, coordinator, meter_id, device):
        super().__init__(coordinator, meter_id, device)
        self._attr_unique_id = f"{meter_id}_smart_meter_active"

    @property
    def is_on(self):
        return self._meter().get("smart_meter_active", False)


class DisconnectionNotificationSensor(_BaseBinarySensor):
    """Whether there is a disconnection notification."""

    _attr_translation_key = "disconnection_notification"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:power-plug-off"

    def __init__(self, coordinator, meter_id, device):
        super().__init__(coordinator, meter_id, device)
        self._attr_unique_id = f"{meter_id}_disconnection_notification"

    @property
    def is_on(self):
        return self._meter().get("disconnection_notification", False)


class PaperlessBillingSensor(_BaseBinarySensor):
    """Whether paperless billing is enabled."""

    _attr_translation_key = "paperless_billing"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:leaf"

    def __init__(self, coordinator, meter_id, can, device):
        super().__init__(coordinator, meter_id, device)
        self._can = can
        self._attr_unique_id = f"{can}_paperless_billing"

    @property
    def is_on(self):
        account = self.coordinator.data.get("accounts", {}).get(self._can, {})
        return account.get("paperless", False)


class EnergyCommunityActiveSensor(_BaseBinarySensor):
    """Whether the energy community membership is active."""

    _attr_translation_key = "ec_active"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:solar-power-variant"

    def __init__(self, coordinator, meter_id, ec_id, ec_name, device):
        super().__init__(coordinator, meter_id, device)
        self._ec_id = ec_id
        self._attr_unique_id = f"{meter_id}_ec_{hashlib.sha256(ec_id.encode()).hexdigest()[:12]}_active"
        self._attr_translation_placeholders = {"energy_community_name": ec_name}

    @property
    def is_on(self):
        for ec in self._meter().get("energy_communities", []):
            if ec["id"] == self._ec_id:
                return ec.get("status") == "ACTIVE"
        return False

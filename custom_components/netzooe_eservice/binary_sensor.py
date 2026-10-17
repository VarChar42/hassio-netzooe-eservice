"""Binary sensors for NetzOÖ eService."""

from __future__ import annotations

from collections.abc import Iterator

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import NetzOoeConfigEntry, NetzOoeCoordinator
from .entity import NetzOoeEntity, account_meters, async_track_entities, community_hash
from .models import NetzOoeData

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NetzOoeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data

    def build(data: NetzOoeData) -> Iterator[BinarySensorEntity]:
        for meter_id, meter in data.meters.items():
            yield SmartMeterActiveSensor(coordinator, meter_id)
            yield DisconnectionSensor(coordinator, meter_id)
            for community in meter.energy_communities:
                yield CommunityActiveSensor(coordinator, meter_id, community.id)
        for meter in account_meters(data).values():
            account = data.accounts.get(meter.contract_account)
            if account and account.paperless is not None:
                yield PaperlessSensor(coordinator, meter.id)

    async_track_entities(coordinator, async_add_entities, build)


class SmartMeterActiveSensor(NetzOoeEntity, BinarySensorEntity):
    _attr_translation_key = "smart_meter_active"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: NetzOoeCoordinator, meter_id: str) -> None:
        super().__init__(coordinator, meter_id, f"{meter_id}_smart_meter_active")

    @property
    def is_on(self) -> bool | None:
        return self.meter.smart_meter_active if self.meter else None


class DisconnectionSensor(NetzOoeEntity, BinarySensorEntity):
    _attr_translation_key = "disconnection_notification"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator: NetzOoeCoordinator, meter_id: str) -> None:
        super().__init__(coordinator, meter_id, f"{meter_id}_disconnection_notification")

    @property
    def is_on(self) -> bool | None:
        return self.meter.disconnection_notification if self.meter else None


class PaperlessSensor(NetzOoeEntity, BinarySensorEntity):
    _attr_translation_key = "paperless_billing"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: NetzOoeCoordinator, meter_id: str) -> None:
        account = coordinator.data.meters[meter_id].contract_account
        super().__init__(coordinator, meter_id, f"{account}_paperless_billing")

    @property
    def is_on(self) -> bool | None:
        return self.account.paperless if self.account else None


class CommunityActiveSensor(NetzOoeEntity, BinarySensorEntity):
    _attr_translation_key = "ec_active"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: NetzOoeCoordinator, meter_id: str, community_id: str) -> None:
        super().__init__(coordinator, meter_id, f"{meter_id}_ec_{community_hash(community_id)}_active")
        self._community_id = community_id
        community = next(
            c for c in coordinator.data.meters[meter_id].energy_communities if c.id == community_id
        )
        self._attr_translation_placeholders = {"community": community.name}

    @property
    def is_on(self) -> bool | None:
        if not self.meter:
            return None
        return any(c.active for c in self.meter.energy_communities if c.id == self._community_id)

"""Base entity for NetzOÖ eService."""

from __future__ import annotations

from collections.abc import Callable, Iterable
import hashlib

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, PORTAL_URL
from .coordinator import NetzOoeCoordinator
from .models import Account, Meter, NetzOoeData


class NetzOoeEntity(CoordinatorEntity[NetzOoeCoordinator]):
    """Entity attached to a meter device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: NetzOoeCoordinator, meter_id: str, unique_id: str) -> None:
        super().__init__(coordinator)
        self._meter_id = meter_id
        self._attr_unique_id = unique_id
        meter = coordinator.data.meters[meter_id]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, meter_id)},
            name=meter.name,
            manufacturer=MANUFACTURER,
            model=meter.smart_meter_type,
            serial_number=meter.meter_number or None,
            configuration_url=PORTAL_URL,
        )

    @property
    def meter(self) -> Meter | None:
        return self.coordinator.data.meters.get(self._meter_id)

    @property
    def account(self) -> Account | None:
        meter = self.meter
        return self.coordinator.data.accounts.get(meter.contract_account) if meter else None

    @property
    def available(self) -> bool:
        return super().available and self.meter is not None


def community_hash(community_id: str) -> str:
    return hashlib.sha256(community_id.encode()).hexdigest()[:12]


def account_meters(data: NetzOoeData) -> dict[str, Meter]:
    """First meter of each contract account, which hosts the account-level entities."""
    result: dict[str, Meter] = {}
    for meter in data.meters.values():
        result.setdefault(meter.contract_account, meter)
    return result


def async_track_entities(
    coordinator: NetzOoeCoordinator,
    async_add_entities: AddConfigEntryEntitiesCallback,
    build: Callable[[NetzOoeData], Iterable[Entity]],
) -> None:
    """Add entities now and whenever new meters or communities show up."""
    known: set[str | None] = set()

    @callback
    def _add() -> None:
        new = [entity for entity in build(coordinator.data) if entity.unique_id not in known]
        known.update(entity.unique_id for entity in new)
        if new:
            async_add_entities(new)

    _add()
    coordinator.config_entry.async_on_unload(coordinator.async_add_listener(_add))

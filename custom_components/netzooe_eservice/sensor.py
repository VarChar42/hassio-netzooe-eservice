"""NetzOOE power meter sensor"""
from __future__ import annotations
import datetime
import logging


from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)

from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .eservice_api import EServiceApi
from .const import DOMAIN

from homeassistant.core import callback
from homeassistant.const import ENERGY_KILO_WATT_HOUR
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    _LOGGER.info("Setup NetzOOE Sensor")
    entries = []
    api = hass.data[DOMAIN][entry.entry_id]
    coordinator = ApiCoordinator(hass, api)
    await coordinator.async_config_entry_first_refresh()

    _LOGGER.info("Api state: %s" % api.state)
    _LOGGER.info("Coordinator state: %s" % coordinator.data)

    for meter in api.state:
        entries.append(PowerMeter(coordinator, api, meter, hass))

    async_add_entities(entries)


class ApiCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, api):
        super().__init__(
            hass,
            _LOGGER,
            name="NetzOOE",
            update_interval=datetime.timedelta(hours=1),
        )
        self.api = api
        self.hass = hass

    async def _async_update_data(self):
        await self.hass.async_add_executor_job(self.api.update)


class PowerMeter(CoordinatorEntity, SensorEntity):
    """Representation of a Sensor."""

    def __init__(self, coordinator, api: EServiceApi, meter_id, hass) -> None:
        super().__init__(coordinator)
        self._api = api
        self._hass = hass
        self._meter_id = self._attr_unique_id = meter_id
        self._attr_name = "netzooe_meter_%s" % meter_id
        self._get_api_state()

    _attr_native_unit_of_measurement = ENERGY_KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL

    def _get_api_state(self) -> None:
        self._attr_native_value = self._api.state[self._meter_id]

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._get_api_state()
        self.async_write_ha_state()

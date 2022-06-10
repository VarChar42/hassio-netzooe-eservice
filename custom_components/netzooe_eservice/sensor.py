"""NetzOOE power meter sensor"""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)

from .eservice_api import EServiceApi
from .const import DOMAIN

from homeassistant.const import ENERGY_KILO_WATT_HOUR


async def async_setup_entry(hass, entry, async_add_entities):
    entries = []
    api = hass.data[DOMAIN][entry.entry_id]

    for meter in api.state:
        entries.append(PowerMeter(api, meter, hass))

    async_add_entities(entries)


class PowerMeter(SensorEntity):
    """Representation of a Sensor."""

    def __init__(self, api: EServiceApi, meter_id, hass) -> None:
        self._api = api
        self._hass = hass
        self._meter_id = self._attr_unique_id = meter_id

        self._attr_name = "netzooe_meter_%s" % meter_id

    _attr_native_unit_of_measurement = ENERGY_KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL

    async def async_update(self):
        """Retrieve latest state."""
        await self._hass.async_add_executor_job(self._api.update)

        self._attr_native_value = self._api.state[self._meter_id]

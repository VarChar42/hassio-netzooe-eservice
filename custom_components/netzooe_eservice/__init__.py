"""The NetzOÖ eService integration."""
from __future__ import annotations
from .eservice_api import EServiceApi

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up NetzOÖ eService from a config entry."""
    
    username = entry.data["username"]
    password = entry.data["password"]

    api = EServiceApi(username, password)

    await hass.async_add_executor_job(api.update)

    if not hasattr(hass.data, DOMAIN):
        hass.data[DOMAIN] = {}

    hass.data[DOMAIN][entry.entry_id] = api
    
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, Platform.SENSOR)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, Platform.SENSOR):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok

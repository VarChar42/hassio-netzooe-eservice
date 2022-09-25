"""The NetzOÖ eService integration."""
from __future__ import annotations
from .eservice_api import EServiceApi

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN

# TODO List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up NetzOÖ eService from a config entry."""
    
    username = entry.data["username"]
    password = entry.data["password"]

    api = EServiceApi(username, password)

    await hass.async_add_executor_job(api.update)

    if not hasattr(hass.data, DOMAIN):
        hass.data[DOMAIN] = {}

    hass.data[DOMAIN][entry.entry_id] = api

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok

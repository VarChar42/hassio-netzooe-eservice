"""The NetzOÖ eService integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .eservice_api import EServiceApi


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up NetzOÖ eService from a config entry."""
    api = EServiceApi(entry.data["username"], entry.data["password"])
    try:
        await hass.async_add_executor_job(api.update)
    except Exception as err:
        await hass.async_add_executor_job(api.close)
        raise ConfigEntryNotReady(f"Failed to connect to NetzOÖ eService: {err}") from err

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = api

    await hass.config_entries.async_forward_entry_setups(entry, [Platform.SENSOR])
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, [Platform.SENSOR]):
        api: EServiceApi = hass.data[DOMAIN].pop(entry.entry_id)
        await hass.async_add_executor_job(api.close)
    return unload_ok

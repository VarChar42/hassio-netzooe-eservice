"""The NetzOÖ eService integration."""
from __future__ import annotations

import datetime
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .eservice_api import EServiceApi

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]

DEFAULT_SCAN_INTERVAL = 60  # minutes


class ApiCoordinator(DataUpdateCoordinator):
    """Coordinator to fetch data from NetzOÖ API."""

    def __init__(self, hass: HomeAssistant, api: EServiceApi, scan_interval_min: int = DEFAULT_SCAN_INTERVAL):
        super().__init__(
            hass, _LOGGER, name="NetzOÖ eService",
            update_interval=datetime.timedelta(minutes=scan_interval_min),
        )
        self.api = api

    async def _async_update_data(self):
        try:
            await self.hass.async_add_executor_job(self.api.update)
        except ConnectionError as err:
            if "login" in str(err).lower():
                raise ConfigEntryAuthFailed(str(err)) from err
            raise UpdateFailed(f"Error fetching NetzOÖ data: {err}") from err
        except Exception as err:
            raise UpdateFailed(f"Error fetching NetzOÖ data: {err}") from err
        return self.api.data


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up NetzOÖ eService from a config entry."""
    api = EServiceApi(entry.data["username"], entry.data["password"])
    try:
        await hass.async_add_executor_job(api.update)
    except Exception as err:
        await hass.async_add_executor_job(api.close)
        raise ConfigEntryNotReady(f"Failed to connect to NetzOÖ eService: {err}") from err

    scan_interval = entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL)
    coordinator = ApiCoordinator(hass, api, scan_interval)
    coordinator.async_set_updated_data(api.data)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update - reload the integration."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        entry_data = hass.data[DOMAIN].pop(entry.entry_id)
        await hass.async_add_executor_job(entry_data["api"].close)
    return unload_ok

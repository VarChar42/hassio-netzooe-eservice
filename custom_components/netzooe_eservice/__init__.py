"""The NetzOÖ eService integration."""

from __future__ import annotations

from collections import Counter

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import NetzOoeClient
from .const import DOMAIN, LOGGER
from .coordinator import NetzOoeConfigEntry, NetzOoeCoordinator
from .models import NetzOoeData

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: NetzOoeConfigEntry) -> bool:
    client = NetzOoeClient(
        async_create_clientsession(hass), entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD]
    )
    coordinator = NetzOoeCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    if entry.minor_version < 2:
        _async_migrate_registry(hass, entry, coordinator.data)
        hass.config_entries.async_update_entry(entry, minor_version=2)

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: NetzOoeConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload(hass: HomeAssistant, entry: NetzOoeConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


@callback
def _async_migrate_registry(hass: HomeAssistant, entry: NetzOoeConfigEntry, data: NetzOoeData) -> None:
    """Move v2 ids keyed by meter number to metering point ids.

    The old "reading" entity reported whichever register came first (often the kW
    peak), so it is left orphaned instead of polluting the new energy statistics.
    """
    counts = Counter(m.meter_number for m in data.meters.values())
    mapping = {m.meter_number: m.id for m in data.meters.values() if counts[m.meter_number] == 1}
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)

    for reg_entry in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
        old = reg_entry.unique_id
        if old == f"{DOMAIN}_unread_messages":
            new = f"{data.business_partner}_unread_messages"
        else:
            number, _, key = old.partition("_")
            if number not in mapping or not key or key == "reading" or key.startswith("register_1.6"):
                continue
            new = f"{mapping[number]}_{key}"
        if ent_reg.async_get_entity_id(reg_entry.domain, DOMAIN, new):
            continue
        LOGGER.debug("Migrating %s unique_id %s -> %s", reg_entry.entity_id, old, new)
        ent_reg.async_update_entity(reg_entry.entity_id, new_unique_id=new)

    for device in dr.async_entries_for_config_entry(dev_reg, entry.entry_id):
        for domain, identifier in device.identifiers:
            if domain == DOMAIN and identifier in mapping:
                target = {(DOMAIN, mapping[identifier])}
                if not dev_reg.async_get_device(identifiers=target):
                    dev_reg.async_update_device(device.id, new_identifiers=target)

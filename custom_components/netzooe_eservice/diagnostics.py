"""Diagnostics for NetzOÖ eService."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .coordinator import NetzOoeConfigEntry

TO_REDACT = {
    CONF_USERNAME,
    CONF_PASSWORD,
    "business_partner",
    "number",
    "id",
    "mpan",
    "meter_number",
    "contract_account",
    "contract_number",
    "address",
    "description",
    "name",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: NetzOoeConfigEntry
) -> dict[str, Any]:
    data = entry.runtime_data.data
    return async_redact_data(
        {
            "entry": {"data": dict(entry.data), "options": dict(entry.options)},
            "business_partner": data.business_partner,
            "unread_messages": data.unread_messages,
            "accounts": [asdict(a) for a in data.accounts.values()],
            "meters": [asdict(m) for m in data.meters.values()],
        },
        TO_REDACT,
    )

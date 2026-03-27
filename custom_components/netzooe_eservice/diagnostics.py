"""Diagnostics support for NetzOÖ eService."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.redact import async_redact_data

from .const import DOMAIN

TO_REDACT_CONFIG = {"username", "password"}
TO_REDACT_DATA = {
    "number",  # business partner number
    "name",
    "email",
    "address",
    "mpan",
    "meter_number",
    "contract_account",
    "contract_number",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    coordinator = entry_data["coordinator"]

    return {
        "config": async_redact_data(dict(entry.data), TO_REDACT_CONFIG),
        "options": dict(entry.options),
        "data": _redact_api_data(coordinator.data),
    }


def _redact_api_data(data: dict) -> dict:
    """Redact sensitive fields from API data."""
    if not data:
        return {}

    result = {}

    # Business partner
    bp = data.get("business_partner", {})
    result["business_partner"] = async_redact_data(bp, TO_REDACT_DATA)

    # Accounts
    result["accounts"] = {}
    for i, (can, account) in enumerate(data.get("accounts", {}).items()):
        redacted = dict(account)
        redacted["address"] = "**REDACTED**"
        # Keep invoice structure but redact numbers
        redacted["invoices"] = [
            {**inv, "number": "**REDACTED**"} for inv in account.get("invoices", [])
        ]
        result["accounts"][f"account_{i}"] = redacted

    # Meters
    result["meters"] = {}
    for i, (meter_id, meter) in enumerate(data.get("meters", {}).items()):
        redacted = async_redact_data(meter, TO_REDACT_DATA)
        result["meters"][f"meter_{i}"] = redacted

    # Messages count (don't include content)
    result["messages_count"] = len(data.get("messages", []))

    return result

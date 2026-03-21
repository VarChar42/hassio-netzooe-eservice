"""Config flow for NetzOÖ eService integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN
from .eservice_api import EServiceApi

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("username"): str,
        vol.Required("password"): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for NetzOÖ eService."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}
        api = EServiceApi(user_input["username"], user_input["password"])
        try:
            ok = await self.hass.async_add_executor_job(api.login)
            if not ok:
                errors["base"] = "invalid_auth"
        except Exception:
            _LOGGER.exception("Failed to connect to NetzOÖ eService")
            errors["base"] = "cannot_connect"
        finally:
            await self.hass.async_add_executor_job(api.close)

        if errors:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
            )

        await self.async_set_unique_id(user_input["username"])
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=f"NetzOÖ eService ({user_input['username']})",
            data=user_input,
        )

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

DEFAULT_SCAN_INTERVAL = 60


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

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> FlowResult:
        """Handle reauth when credentials become invalid."""
        self._reauth_username = entry_data.get("username", "")
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle reauth confirmation."""
        errors = {}

        if user_input is not None:
            username = self._reauth_username
            password = user_input["password"]
            api = EServiceApi(username, password)
            try:
                ok = await self.hass.async_add_executor_job(api.login)
                if not ok:
                    errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Failed to connect to NetzOÖ eService")
                errors["base"] = "cannot_connect"
            finally:
                await self.hass.async_add_executor_job(api.close)

            if not errors:
                entry = self.hass.config_entries.async_get_entry(
                    self.context["entry_id"]
                )
                self.hass.config_entries.async_update_entry(
                    entry, data={"username": username, "password": password}
                )
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        reauth_schema = vol.Schema(
            {
                vol.Required("password"): str,
            }
        )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=reauth_schema,
            errors=errors,
            description_placeholders={"username": self._reauth_username},
        )

    @staticmethod
    def async_get_options_flow(config_entry):
        """Get the options flow handler."""
        return OptionsFlow(config_entry)


class OptionsFlow(config_entries.OptionsFlow):
    """Handle options for NetzOÖ eService."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_interval = self._config_entry.options.get(
            "scan_interval", DEFAULT_SCAN_INTERVAL
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "scan_interval",
                        default=current_interval,
                    ): vol.All(vol.Coerce(int), vol.Range(min=15, max=1440)),
                }
            ),
        )

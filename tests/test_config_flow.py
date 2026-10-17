"""Tests for the config flow."""

from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.netzooe_eservice.api import NetzOoeAuthError, NetzOoeConnectionError
from custom_components.netzooe_eservice.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import PASSWORD, USERNAME


async def test_user_flow(hass: HomeAssistant, mock_client: AsyncMock) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"username": f" {USERNAME} ", "password": PASSWORD}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == USERNAME
    assert result["data"] == {"username": USERNAME, "password": PASSWORD}
    assert result["result"].unique_id == USERNAME


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (NetzOoeAuthError, "invalid_auth"),
        (NetzOoeConnectionError, "cannot_connect"),
        (RuntimeError, "unknown"),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant, mock_client: AsyncMock, side_effect: type[Exception], error: str
) -> None:
    mock_client.login.side_effect = side_effect
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"username": USERNAME, "password": PASSWORD}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_client.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"username": USERNAME, "password": PASSWORD}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_already_configured(
    hass: HomeAssistant, mock_client: AsyncMock, mock_entry: MockConfigEntry
) -> None:
    mock_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"username": USERNAME, "password": PASSWORD}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth(hass: HomeAssistant, mock_client: AsyncMock, mock_entry: MockConfigEntry) -> None:
    mock_entry.add_to_hass(hass)
    result = await mock_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"

    mock_client.login.side_effect = NetzOoeAuthError
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"password": "bad"})
    assert result["errors"] == {"base": "invalid_auth"}

    mock_client.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"password": "new"})
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_entry.data["password"] == "new"


async def test_options(hass: HomeAssistant, mock_client: AsyncMock, mock_entry: MockConfigEntry) -> None:
    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_entry.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"scan_interval": 30})
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_entry.options == {"scan_interval": 30}
    assert mock_entry.runtime_data.update_interval.total_seconds() == 1800

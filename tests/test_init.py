"""Tests for setup, unload, migration and diagnostics."""

from unittest.mock import AsyncMock

from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from custom_components.netzooe_eservice.api import NetzOoeAuthError, NetzOoeConnectionError
from custom_components.netzooe_eservice.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import MPAN, PASSWORD, USERNAME, load_fixture


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_setup_and_unload(
    hass: HomeAssistant, mock_client: AsyncMock, mock_entry: MockConfigEntry
) -> None:
    await _setup(hass, mock_entry)
    assert mock_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_entry.entry_id)
    assert mock_entry.state is ConfigEntryState.NOT_LOADED


async def test_auth_failure_starts_reauth(
    hass: HomeAssistant, mock_client: AsyncMock, mock_entry: MockConfigEntry
) -> None:
    mock_client.get_dashboard.side_effect = NetzOoeAuthError
    await _setup(hass, mock_entry)
    assert mock_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert [flow["context"]["source"] for flow in flows] == ["reauth"]


async def test_connection_failure_retries(
    hass: HomeAssistant, mock_client: AsyncMock, mock_entry: MockConfigEntry
) -> None:
    mock_client.get_dashboard.side_effect = NetzOoeConnectionError
    await _setup(hass, mock_entry)
    assert mock_entry.state is ConfigEntryState.SETUP_RETRY


async def test_profile_failure_keeps_other_data(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    mock_client.get_profile.side_effect = NetzOoeConnectionError
    mock_client.get_messages.side_effect = NetzOoeConnectionError
    await _setup(hass, mock_entry)
    assert mock_entry.state is ConfigEntryState.LOADED
    entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, f"{MPAN}_consumption_total")
    assert hass.states.get(entity_id).state == "100265.928"


async def test_migrates_v2_unique_ids(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    raw = load_fixture("contract_account")
    raw["contracts"] = raw["contracts"][:1]
    mock_client.get_contract_account.side_effect = lambda bp, acc: raw
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=USERNAME, data={"username": USERNAME, "password": PASSWORD}, minor_version=1
    )
    entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, "1234567")}
    )
    old = {
        "1234567_reading": None,
        "1234567_monthly_consumption": f"{MPAN}_monthly_consumption",
        "200100000001_installment_amount": "200100000001_installment_amount",
        "netzooe_eservice_unread_messages": "1000000001_unread_messages",
    }
    for unique_id in old:
        entity_registry.async_get_or_create(
            "sensor", DOMAIN, unique_id, config_entry=entry, device_id=device.id
        )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.minor_version == 2
    ids = {e.unique_id for e in er.async_entries_for_config_entry(entity_registry, entry.entry_id)}
    assert "1234567_reading" in ids
    for new in filter(None, old.values()):
        assert new in ids
    assert device_registry.async_get(device.id).identifiers == {(DOMAIN, MPAN)}


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_client: AsyncMock,
    mock_entry: MockConfigEntry,
) -> None:
    await _setup(hass, mock_entry)
    diag = await get_diagnostics_for_config_entry(hass, hass_client, mock_entry)
    text = str(diag)
    for secret in (PASSWORD, MPAN, "1234567", "200100000001", "Musterstraße"):
        assert secret not in text
    assert diag["meters"][0]["registers"][1]["value"] == 100265.928

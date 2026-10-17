"""Tests for sensor and binary sensor entities."""

from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.netzooe_eservice.const import DOMAIN
from custom_components.netzooe_eservice.entity import community_hash
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import ACCOUNT, MPAN, MPAN_FEED_IN, load_fixture

EC = community_hash("AT00300000000RC100000000000000001")


@pytest.fixture
async def setup(hass: HomeAssistant, mock_client: AsyncMock, mock_entry: MockConfigEntry) -> MockConfigEntry:
    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    return mock_entry


def _state(hass: HomeAssistant, platform: str, unique_id: str):
    entity_id = er.async_get(hass).async_get_entity_id(platform, DOMAIN, unique_id)
    assert entity_id, unique_id
    return hass.states.get(entity_id)


@pytest.mark.parametrize(
    ("unique_id", "value"),
    [
        (f"{MPAN}_consumption_total", "100265.928"),
        (f"{MPAN}_peak_power", "13.831"),
        (f"{MPAN}_daily_consumption", "41.083"),
        (f"{MPAN}_weekly_consumption", "186.069"),
        (f"{MPAN}_monthly_consumption", "833.0"),
        (f"{MPAN}_monthly_consumption_previous", "575.0"),
        (f"{MPAN}_yearly_consumption", "14225.62"),
        (f"{MPAN}_total_consumption", "70867.0"),
        (f"{MPAN}_contract_power", "4.0"),
        (f"{MPAN}_grid_traffic_light", "green"),
        (f"{MPAN}_move_in_date", "2019-12-03"),
        (f"{MPAN}_ec_{EC}_own_coverage", "5.832559"),
        (f"{MPAN}_ec_{EC}_consumption", "41.083"),
        (f"{MPAN_FEED_IN}_feed_in_total", "5000.75"),
        (f"{MPAN_FEED_IN}_register_2.8.1", "4100.5"),
        (f"{MPAN_FEED_IN}_register_2.8.2", "900.25"),
        (f"{ACCOUNT}_last_invoice_amount", "389.1"),
        (f"{ACCOUNT}_last_invoice_date", "2026-07-15"),
        (f"{ACCOUNT}_installment_amount", "95.0"),
        (f"{ACCOUNT}_next_installment_date", "2026-11-05"),
        ("1000000001_unread_messages", "1"),
    ],
)
async def test_sensor_values(hass: HomeAssistant, setup: MockConfigEntry, unique_id: str, value: str) -> None:
    assert _state(hass, "sensor", unique_id).state == value


async def test_energy_sensor_attributes(hass: HomeAssistant, setup: MockConfigEntry) -> None:
    state = _state(hass, "sensor", f"{MPAN}_consumption_total")
    assert state.attributes["unit_of_measurement"] == "kWh"
    assert state.attributes["state_class"] == "total_increasing"
    assert state.attributes["device_class"] == "energy"
    assert _state(hass, "sensor", f"{MPAN}_daily_consumption").attributes.get("state_class") is None


@pytest.mark.parametrize(
    ("unique_id", "value"),
    [
        (f"{MPAN}_smart_meter_active", "on"),
        (f"{MPAN_FEED_IN}_smart_meter_active", "off"),
        (f"{MPAN}_disconnection_notification", "off"),
        (f"{MPAN}_ec_{EC}_active", "on"),
    ],
)
async def test_binary_sensor_values(
    hass: HomeAssistant, setup: MockConfigEntry, unique_id: str, value: str
) -> None:
    assert _state(hass, "binary_sensor", unique_id).state == value


async def test_entity_selection(
    hass: HomeAssistant, setup: MockConfigEntry, entity_registry: er.EntityRegistry
) -> None:
    ids = {e.unique_id for e in er.async_entries_for_config_entry(entity_registry, setup.entry_id)}
    assert f"{MPAN_FEED_IN}_consumption_total" not in ids
    assert f"{MPAN_FEED_IN}_daily_consumption" not in ids
    assert f"{ACCOUNT}_paperless_billing" not in ids
    assert (
        entity_registry.async_get(
            entity_registry.async_get_entity_id("sensor", DOMAIN, f"{MPAN}_address")
        ).disabled_by
        is er.RegistryEntryDisabler.INTEGRATION
    )


async def test_devices_per_metering_point(
    hass: HomeAssistant, setup: MockConfigEntry, device_registry: dr.DeviceRegistry
) -> None:
    devices = dr.async_entries_for_config_entry(device_registry, setup.entry_id)
    assert sorted(d.name for d in devices) == ["Meter 1234567 (100001)", "Meter 1234567 (100002)"]
    assert {d.serial_number for d in devices} == {"1234567"}


async def test_new_meter_added_on_update(
    hass: HomeAssistant, setup: MockConfigEntry, mock_client: AsyncMock, freezer
) -> None:
    raw = load_fixture("contract_account")
    extra = raw["contracts"][0]
    extra["pointOfDelivery"]["meterPointAdministrationNumber"] = "AT0030000000000000000000000100003"
    extra["pointOfDelivery"]["meter"]["meterNumber"] = "7654321"
    mock_client.get_contract_account.side_effect = lambda bp, acc: raw

    freezer.tick(3601)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert _state(hass, "sensor", "AT0030000000000000000000000100003_consumption_total").state == "100265.928"

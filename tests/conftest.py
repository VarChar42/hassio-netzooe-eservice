"""Fixtures for NetzOÖ eService tests."""

from collections.abc import Generator
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.netzooe_eservice.api import (
    PROFILE_CONSUMPTION,
    PROFILE_EC_CONSUMPTION,
    PROFILE_EC_OWN_COVERAGE,
)
from custom_components.netzooe_eservice.const import DOMAIN

FIXTURES = Path(__file__).parent / "fixtures"
USERNAME = "max"
PASSWORD = "secret"
MPAN = "AT0030000000000000000000000100001"
MPAN_FEED_IN = "AT0030000000000000000000000100002"
ACCOUNT = "200100000001"


def load_fixture(name: str) -> Any:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf8"))


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    return


@pytest.fixture(autouse=True)
def frozen_time(freezer) -> None:
    freezer.move_to("2026-10-17 10:00:00+00:00")


@pytest.fixture
def mock_client() -> Generator[AsyncMock]:
    profiles = {
        PROFILE_CONSUMPTION: load_fixture("profile_consumption"),
        PROFILE_EC_OWN_COVERAGE: load_fixture("profile_ec_own_coverage"),
        PROFILE_EC_CONSUMPTION: load_fixture("profile_ec_consumption"),
    }
    with (
        patch("custom_components.netzooe_eservice.NetzOoeClient", autospec=True) as client_cls,
        patch("custom_components.netzooe_eservice.config_flow.NetzOoeClient", new=client_cls),
    ):
        client = client_cls.return_value
        client.get_dashboard.side_effect = lambda: load_fixture("dashboard")
        client.get_messages.side_effect = lambda: load_fixture("messages")
        client.get_contract_account.side_effect = lambda bp, acc: load_fixture("contract_account")
        client.get_profile.side_effect = lambda account, mpan, kind, start, end, ec=None: profiles[kind]
        yield client


@pytest.fixture
def mock_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title=USERNAME,
        unique_id=USERNAME,
        data={"username": USERNAME, "password": PASSWORD},
        minor_version=2,
    )

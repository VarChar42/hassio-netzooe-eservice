"""Tests for the API client."""

from collections.abc import AsyncGenerator

import aiohttp
import pytest
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.netzooe_eservice.api import (
    DASHBOARD_URL,
    LOGIN_URL,
    NetzOoeAuthError,
    NetzOoeClient,
    NetzOoeConnectionError,
)
from homeassistant.core import HomeAssistant


@pytest.fixture
async def client(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> AsyncGenerator[NetzOoeClient]:
    session = aioclient_mock.create_session(hass.loop)
    yield NetzOoeClient(session, "u", "p")
    await session.close()


@pytest.mark.parametrize(("status", "error"), [(401, NetzOoeAuthError), (503, NetzOoeConnectionError)])
async def test_login_errors(
    client: NetzOoeClient, aioclient_mock: AiohttpClientMocker, status: int, error: type[Exception]
) -> None:
    aioclient_mock.post(LOGIN_URL, status=status)
    with pytest.raises(error):
        await client.login()


async def test_get_logs_in_and_parses(client: NetzOoeClient, aioclient_mock: AiohttpClientMocker) -> None:
    aioclient_mock.post(LOGIN_URL)
    aioclient_mock.get(DASHBOARD_URL, json={"ok": True})
    assert await client.get_dashboard() == {"ok": True}
    assert aioclient_mock.mock_calls[0][2] == {"j_username": "u", "j_password": "p"}


async def test_unauthorized_relogs_once(client: NetzOoeClient, aioclient_mock: AiohttpClientMocker) -> None:
    aioclient_mock.post(LOGIN_URL)
    aioclient_mock.get(DASHBOARD_URL, status=401)
    with pytest.raises(NetzOoeConnectionError):
        await client.get_dashboard()
    assert [call[1].path for call in aioclient_mock.mock_calls].count(LOGIN_URL.split(".at")[1]) == 2


async def test_network_error(client: NetzOoeClient, aioclient_mock: AiohttpClientMocker) -> None:
    aioclient_mock.post(LOGIN_URL)
    aioclient_mock.get(DASHBOARD_URL, exc=aiohttp.ClientConnectionError())
    with pytest.raises(NetzOoeConnectionError):
        await client.get_dashboard()

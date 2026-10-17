"""Async client for the NetzOÖ eService portal."""

from __future__ import annotations

from datetime import date
from typing import Any

import aiohttp

BASE_URL = "https://eservice.netzooe.at/service"
LOGIN_URL = f"{BASE_URL}/j_security_check"
DASHBOARD_URL = f"{BASE_URL}/v1.0/dashboard"
CONTRACT_ACCOUNT_URL = f"{BASE_URL}/v1.0/contract-accounts"
PROFILE_URL = f"{BASE_URL}/v1.0/consumptions/profile/active"
MESSAGES_URL = f"{BASE_URL}/partner-messages"

PROFILE_CONSUMPTION = "ACTIVE_CURRENT"
PROFILE_EC_OWN_COVERAGE = "ENERGY_COMMUNITY_OWN_COVERAGE"
PROFILE_EC_CONSUMPTION = "ENERGY_COMMUNITY_CONSUMPTION_PER_CONTRIBUTION_FACTOR"

TIMEOUT = aiohttp.ClientTimeout(total=30)
HEADERS = {"client-id": "netzonline"}


class NetzOoeError(Exception):
    """Base error."""


class NetzOoeAuthError(NetzOoeError):
    """Credentials rejected."""


class NetzOoeConnectionError(NetzOoeError):
    """Portal unreachable or returned an unexpected response."""


class NetzOoeClient:
    """Session-based client; the portal uses cookies plus an XSRF token for POSTs."""

    def __init__(self, session: aiohttp.ClientSession, username: str, password: str) -> None:
        self._session = session
        self._username = username
        self._password = password
        self._logged_in = False

    async def login(self) -> None:
        self._session.cookie_jar.clear()
        self._logged_in = False
        try:
            async with self._session.post(
                LOGIN_URL,
                json={"j_username": self._username, "j_password": self._password},
                headers=HEADERS,
                timeout=TIMEOUT,
            ) as resp:
                if resp.status in (400, 401, 403):
                    raise NetzOoeAuthError("Invalid credentials")
                if resp.status != 200:
                    raise NetzOoeConnectionError(f"Login returned HTTP {resp.status}")
        except (aiohttp.ClientError, TimeoutError) as err:
            raise NetzOoeConnectionError(f"Login failed: {err}") from err
        self._logged_in = True

    def _xsrf_token(self) -> str | None:
        for cookie in self._session.cookie_jar:
            if cookie.key == "XSRF-TOKEN":
                return cookie.value
        return None

    async def _request(self, method: str, url: str, payload: Any = None, *, retry: bool = True) -> Any:
        if not self._logged_in:
            await self.login()
        headers = dict(HEADERS)
        if method == "POST":
            if not self._xsrf_token():
                await self._request("GET", DASHBOARD_URL, retry=False)
            headers["X-XSRF-TOKEN"] = self._xsrf_token() or ""
        try:
            async with self._session.request(
                method, url, json=payload, headers=headers, timeout=TIMEOUT
            ) as resp:
                if resp.status == 401 and retry:
                    self._logged_in = False
                    return await self._request(method, url, payload, retry=False)
                if resp.status != 200:
                    raise NetzOoeConnectionError(f"{method} {url} returned HTTP {resp.status}")
                return await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise NetzOoeConnectionError(f"{method} {url} failed: {err}") from err

    async def get_dashboard(self) -> dict[str, Any]:
        return await self._request("GET", DASHBOARD_URL)

    async def get_messages(self) -> dict[str, Any]:
        return await self._request("GET", MESSAGES_URL)

    async def get_contract_account(self, business_partner: str, account: str) -> dict[str, Any]:
        return await self._request("GET", f"{CONTRACT_ACCOUNT_URL}/{business_partner}/{account}")

    async def get_profile(
        self,
        account: str,
        mpan: str,
        profile_type: str,
        start: date,
        end: date,
        energy_community_id: str | None = None,
    ) -> list[dict[str, Any]]:
        pod: dict[str, Any] = {
            "contractAccountNumber": account,
            "meterPointAdministrationNumber": mpan,
            "type": profile_type,
            "timerange": {"from": start.isoformat(), "to": end.isoformat()},
            "bestAvailableGranularity": "DAY",
        }
        if energy_community_id:
            pod["energyCommunityId"] = energy_community_id
        return await self._request("POST", PROFILE_URL, {"dimension": "ENERGY", "pods": [pod]})

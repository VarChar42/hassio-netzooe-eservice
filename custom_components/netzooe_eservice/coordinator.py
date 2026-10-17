"""Data update coordinator for NetzOÖ eService."""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    PROFILE_CONSUMPTION,
    PROFILE_EC_CONSUMPTION,
    PROFILE_EC_OWN_COVERAGE,
    NetzOoeAuthError,
    NetzOoeClient,
    NetzOoeConnectionError,
)
from .const import (
    COMMUNITY_PROFILE_DAYS,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LOGGER,
    PROFILE_DAYS,
)
from .models import (
    VIENNA,
    Meter,
    NetzOoeData,
    apply_consumption_profile,
    count_unread,
    latest_community_value,
    parse_account,
    parse_dashboard,
    parse_meters,
)

type NetzOoeConfigEntry = ConfigEntry[NetzOoeCoordinator]


class NetzOoeCoordinator(DataUpdateCoordinator[NetzOoeData]):
    config_entry: NetzOoeConfigEntry

    def __init__(self, hass: HomeAssistant, entry: NetzOoeConfigEntry, client: NetzOoeClient) -> None:
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)),
        )
        self.client = client

    async def _async_update_data(self) -> NetzOoeData:
        try:
            return await self._fetch()
        except NetzOoeAuthError as err:
            raise ConfigEntryAuthFailed(translation_domain=DOMAIN, translation_key="invalid_auth") from err
        except (NetzOoeConnectionError, ValueError) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err

    async def _fetch(self) -> NetzOoeData:
        business_partner, account_numbers = parse_dashboard(await self.client.get_dashboard())

        unread = None
        try:
            unread = count_unread(await self.client.get_messages())
        except NetzOoeConnectionError as err:
            LOGGER.debug("Fetching messages failed: %s", err)

        accounts, meters = {}, {}
        for number in account_numbers:
            raw = await self.client.get_contract_account(business_partner, number)
            account = parse_account(raw)
            accounts[account.number] = account
            for meter in parse_meters(raw, account):
                meters[meter.id] = meter

        duplicates = Counter(m.meter_number for m in meters.values())
        today = datetime.now(VIENNA).date()
        for meter in meters.values():
            meter.name = f"Meter {meter.meter_number or meter.mpan}"
            if duplicates[meter.meter_number] > 1:
                meter.name += f" ({meter.mpan[-6:]})"
            await self._fetch_profiles(meter, today)

        return NetzOoeData(business_partner, accounts, meters, unread)

    async def _fetch_profiles(self, meter: Meter, today: date) -> None:
        if not meter.mpan:
            return
        client = self.client
        try:
            if meter.smart_meter_active:
                apply_consumption_profile(
                    meter,
                    await client.get_profile(
                        meter.contract_account, meter.mpan, PROFILE_CONSUMPTION, today - PROFILE_DAYS, today
                    ),
                    today,
                )
            for community in meter.energy_communities:
                if not community.active:
                    continue
                start = today - COMMUNITY_PROFILE_DAYS
                community.own_coverage = latest_community_value(
                    await client.get_profile(
                        meter.contract_account,
                        meter.mpan,
                        PROFILE_EC_OWN_COVERAGE,
                        start,
                        today,
                        community.id,
                    )
                )
                community.consumption = latest_community_value(
                    await client.get_profile(
                        meter.contract_account, meter.mpan, PROFILE_EC_CONSUMPTION, start, today, community.id
                    )
                )
        except NetzOoeConnectionError as err:
            LOGGER.warning("Fetching profiles for %s failed: %s", meter.name or meter.id, err)

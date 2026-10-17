"""Tests for response parsing."""

from datetime import date

from custom_components.netzooe_eservice.models import (
    Register,
    _date,
    _datetime,
    apply_consumption_profile,
    latest_community_value,
    parse_account,
    parse_dashboard,
    parse_meters,
)

from .conftest import MPAN, MPAN_FEED_IN, load_fixture


def _meters():
    raw = load_fixture("contract_account")
    return {m.id: m for m in parse_meters(raw, parse_account(raw))}


def test_dashboard_skips_inactive_accounts() -> None:
    assert parse_dashboard(load_fixture("dashboard")) == ("1000000001", ["200100000001"])


def test_meters_keyed_by_metering_point() -> None:
    meters = _meters()
    assert set(meters) == {MPAN, MPAN_FEED_IN}
    assert {m.meter_number for m in meters.values()} == {"1234567"}


def test_registers() -> None:
    meter = _meters()[MPAN]
    assert meter.consumption_total == 100265.928
    assert meter.feed_in_total is None
    assert meter.peak_power.value == 13.831
    assert meter.peak_power.unit == "kW"
    assert meter.tariff_registers == []

    feed_in = _meters()[MPAN_FEED_IN]
    assert feed_in.consumption_total is None
    assert feed_in.feed_in_total == 5000.75
    assert [r.obis for r in feed_in.tariff_registers] == ["2.8.1", "2.8.2"]


def test_total_register_preferred_over_tariffs() -> None:
    meter = _meters()[MPAN]
    meter.registers = [
        Register("1.8.0", 30.0, "kWh", None),
        Register("1.8.1", 10.0, "kWh", None),
        Register("1.8.2", 20.0, "kWh", None),
    ]
    assert meter.consumption_total == 30.0
    assert [r.obis for r in meter.tariff_registers] == ["1.8.1", "1.8.2"]


def test_account() -> None:
    account = parse_account(load_fixture("contract_account"))
    assert account.address == "Musterstraße 1, 4020 Linz"
    assert account.paperless is None
    assert account.disconnection_notification is False
    assert account.installment.next_due_date == date(2026, 11, 5)
    assert len(account.invoices) == 2


def test_consumption_profile_uses_local_days() -> None:
    meter = _meters()[MPAN]
    apply_consumption_profile(meter, load_fixture("profile_consumption"), date(2026, 10, 17))
    assert meter.consumption_yesterday == 41.083
    assert meter.consumption_week == 186.069
    assert meter.contract_power == 4.0


def test_community_value_ignores_provisional() -> None:
    assert latest_community_value(load_fixture("profile_ec_own_coverage")) == 5.832559
    assert latest_community_value([]) is None


def test_datetime_parsing() -> None:
    assert _datetime("2026-10-17T10:18:53.335767967").microsecond == 335767
    assert _datetime("2026-10-15T22:00:00Z").utcoffset().total_seconds() == 0
    assert _date("2026-03-28T23:00:00Z") == date(2026, 3, 29)
    assert _date("2026-03-29T22:00:00Z") == date(2026, 3, 30)
    assert _date("9999-12-31") is None
    assert _datetime("garbage") is None

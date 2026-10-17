"""Data models and parsers for NetzOÖ eService responses."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

VIENNA = ZoneInfo("Europe/Vienna")
VALID_STATUSES = ("VALID", "CALCULATED")
TRAFFIC_LIGHTS = ("green", "yellow", "red")


@dataclass(slots=True)
class Register:
    obis: str
    value: float | None
    unit: str | None
    timestamp: datetime | None


@dataclass(slots=True)
class Period:
    value: float | None
    per_day: float | None
    days: int | None
    start: date | None
    end: date | None


@dataclass(slots=True)
class Invoice:
    number: str
    date: date | None
    total: float | None


@dataclass(slots=True)
class Installment:
    amount: float | None
    cycle: str | None
    next_due_date: date | None
    start: date | None
    end: date | None


@dataclass(slots=True)
class EnergyCommunity:
    id: str
    name: str
    active: bool
    start: date | None
    end: date | None
    own_coverage: float | None = None
    consumption: float | None = None


@dataclass(slots=True)
class Account:
    number: str
    description: str
    address: str
    paperless: bool | None
    disconnection_notification: bool
    invoices: list[Invoice] = field(default_factory=list)
    installment: Installment | None = None


@dataclass(slots=True)
class Meter:
    id: str
    mpan: str
    meter_number: str
    contract_account: str
    contract_number: str
    smart_meter_type: str | None
    smart_meter_active: bool
    supplier: str | None
    move_in_date: date | None
    address: str
    traffic_light: str | None
    disconnection_notification: bool
    registers: list[Register] = field(default_factory=list)
    trend_current: Period | None = None
    trend_previous: Period | None = None
    yearly_current: Period | None = None
    yearly_previous: Period | None = None
    billing_total: float | None = None
    billing_periods: list[Period] = field(default_factory=list)
    energy_communities: list[EnergyCommunity] = field(default_factory=list)
    contract_power: float | None = None
    consumption_yesterday: float | None = None
    consumption_week: float | None = None
    name: str = ""

    def _energy_total(self, prefix: str) -> float | None:
        regs = [r for r in self.registers if r.obis.startswith(prefix) and r.value is not None]
        for reg in regs:
            if reg.obis == f"{prefix}0":
                return reg.value
        return round(sum(r.value for r in regs), 3) if regs else None

    @property
    def consumption_total(self) -> float | None:
        return self._energy_total("1.8.")

    @property
    def feed_in_total(self) -> float | None:
        return self._energy_total("2.8.")

    @property
    def peak_power(self) -> Register | None:
        return next((r for r in self.registers if r.obis == "1.6.0"), None)

    @property
    def tariff_registers(self) -> list[Register]:
        """Energy registers worth exposing individually (multi-tariff meters)."""
        result = []
        for prefix in ("1.8.", "2.8."):
            regs = [r for r in self.registers if r.obis.startswith(prefix) and r.obis != f"{prefix}0"]
            if len(regs) > 1:
                result.extend(regs)
        return result

    @property
    def reading_timestamp(self) -> datetime | None:
        stamps = [r.timestamp for r in self.registers if r.obis.startswith("1.8.") and r.timestamp]
        return max(stamps) if stamps else None


@dataclass(slots=True)
class NetzOoeData:
    business_partner: str
    accounts: dict[str, Account]
    meters: dict[str, Meter]
    unread_messages: int | None


def _float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    head, sep, frac = value.partition(".")
    if sep:
        tz = ""
        for marker in ("Z", "+", "-"):
            if marker in frac:
                idx = frac.index(marker)
                frac, tz = frac[:idx], frac[idx:]
                break
        value = f"{head}.{frac[:6]}{tz}"
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed.replace(tzinfo=VIENNA) if parsed.tzinfo is None else parsed


def _date(value: Any) -> date | None:
    if not isinstance(value, str) or not value or value.startswith("9999"):
        return None
    if "T" not in value:
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    parsed = _datetime(value)
    return parsed.astimezone(VIENNA).date() if parsed else None


def _address(raw: dict[str, Any]) -> str:
    street = f"{raw.get('street', '')} {raw.get('housenumber', '')}".strip()
    city = f"{raw.get('postcode', '')} {raw.get('city', '')}".strip()
    return ", ".join(part for part in (street, city) if part)


def _period(consumption: dict[str, Any] | None, timerange: dict[str, Any] | None) -> Period | None:
    if not consumption or not consumption.get("days"):
        return None
    timerange = timerange or {}
    return Period(
        value=_float(consumption.get("sum")),
        per_day=_float(consumption.get("perDay")),
        days=consumption.get("days"),
        start=_date(timerange.get("from")),
        end=_date(timerange.get("to")),
    )


def parse_dashboard(raw: dict[str, Any]) -> tuple[str, list[str]]:
    partners = raw.get("businessPartners") or []
    if not partners or not partners[0].get("businessPartnerNumber"):
        raise ValueError("No business partner in dashboard")
    accounts = [
        acc["contractAccountNumber"]
        for acc in raw.get("contractAccounts", [])
        if acc.get("active") and acc.get("contractAccountNumber")
    ]
    return partners[0]["businessPartnerNumber"], accounts


def count_unread(raw: dict[str, Any] | None) -> int:
    messages = (raw or {}).get("partnerMessages") or []
    return sum(1 for msg in messages if not msg.get("read", True))


def parse_account(raw: dict[str, Any]) -> Account:
    settings = raw.get("invoiceSettings") or {}
    account = Account(
        number=raw.get("contractAccountNumber", ""),
        description=raw.get("description", ""),
        address=_address(raw.get("address") or {}),
        paperless=settings["paperless"] == "PAPERLESS" if "paperless" in settings else None,
        disconnection_notification=bool(raw.get("disconnectionNotification")),
        invoices=[
            Invoice(
                number=inv.get("invoiceNumber", ""),
                date=_date(inv.get("invoiceDate")),
                total=_float(inv.get("total")),
            )
            for inv in raw.get("invoices") or []
        ],
    )
    if inst := raw.get("installmentAgreement"):
        upcoming = inst.get("installments") or []
        account.installment = Installment(
            amount=_float(inst.get("currentAmount")),
            cycle=inst.get("cycle"),
            next_due_date=_date(upcoming[0].get("dueDate")) if upcoming else None,
            start=_date(inst.get("beginDate")),
            end=_date(inst.get("endDate")),
        )
    return account


def _parse_registers(pod: dict[str, Any]) -> list[Register]:
    registers = []
    for reg in (pod.get("lastReadings") or {}).get("values") or []:
        result = reg.get("newResult") or {}
        unit = {"KWH": "kWh", "KW": "kW"}.get(str(reg.get("unitForCalculatedConsumption")).upper())
        registers.append(
            Register(
                obis=reg.get("referenceNumber", ""),
                value=_float(result.get("readingValue")),
                unit=unit,
                timestamp=_datetime(result.get("timestamp")),
            )
        )
    return registers


def _parse_communities(contract: dict[str, Any]) -> list[EnergyCommunity]:
    communities: dict[str, EnergyCommunity] = {}
    for ts in (contract.get("energyCommunityData") or {}).get("timeslices") or []:
        ec_id = ts.get("energyCommunityId")
        if not ec_id:
            continue
        community = EnergyCommunity(
            id=ec_id,
            name=ts.get("energyCommunityName") or ec_id,
            active=ts.get("status") == "ACTIVE",
            start=_date(ts.get("from")),
            end=_date(ts.get("to")),
        )
        if ec_id not in communities or community.active:
            communities[ec_id] = community
    return list(communities.values())


def parse_meters(raw: dict[str, Any], account: Account) -> list[Meter]:
    meters = []
    for contract in raw.get("contracts") or []:
        if contract.get("active") is False:
            continue
        pod = contract.get("pointOfDelivery") or {}
        mpan = pod.get("meterPointAdministrationNumber", "")
        meter_number = (pod.get("meter") or {}).get("meterNumber", "")
        if not mpan and not meter_number:
            continue
        trend = pod.get("monthlyTrend") or {}
        yearly = pod.get("yearlyTrend") or {}
        consumptions = contract.get("consumptions") or {}
        light = str((contract.get("generationData") or {}).get("trafficLightColor", "")).lower()
        meters.append(
            Meter(
                id=mpan or meter_number,
                mpan=mpan,
                meter_number=meter_number,
                contract_account=account.number,
                contract_number=contract.get("contractNumber", ""),
                smart_meter_type=contract.get("smartMeterType"),
                smart_meter_active=bool(pod.get("smartMeterActive")),
                supplier=(contract.get("supplier") or {}).get("name"),
                move_in_date=_date(contract.get("moveInDate")),
                address=account.address,
                traffic_light=light if light in TRAFFIC_LIGHTS else None,
                disconnection_notification=account.disconnection_notification
                or bool(contract.get("disconnectionNotification")),
                registers=_parse_registers(pod),
                trend_current=_period(trend.get("consumptionNew"), trend.get("timerangeNew")),
                trend_previous=_period(trend.get("consumptionOld"), trend.get("timerangeOld")),
                yearly_current=_period(yearly.get("consumptionNew"), yearly.get("timerangeNew")),
                yearly_previous=_period(yearly.get("consumptionOld"), yearly.get("timerangeOld")),
                billing_total=_float(consumptions.get("totalConsumption")) or None,
                billing_periods=[
                    Period(
                        value=_float(p.get("value")),
                        per_day=_float(p.get("consumptionPerDay")),
                        days=p.get("nrOfDays"),
                        start=_date(p.get("from")),
                        end=_date(p.get("to")),
                    )
                    for p in consumptions.get("values") or []
                ],
                energy_communities=_parse_communities(contract),
            )
        )
    return meters


def _first_profile(raw: Any) -> dict[str, Any] | None:
    if isinstance(raw, list) and raw and isinstance(raw[0], dict):
        return raw[0]
    return None


def _valid_values(profile: dict[str, Any]) -> list[tuple[date, float]]:
    values = []
    for item in profile.get("profileValues") or []:
        value = _float(item.get("value"))
        day = _date(item.get("datetime"))
        if item.get("status") in VALID_STATUSES and value is not None and day:
            values.append((day, value))
    return values


def apply_consumption_profile(meter: Meter, raw: Any, today: date) -> None:
    if not (profile := _first_profile(raw)):
        return
    meter.contract_power = _float(profile.get("contractPower"))
    meter.consumption_week = _float((profile.get("sum") or {}).get("value"))
    yesterday = today - timedelta(days=1)
    meter.consumption_yesterday = next(
        (value for day, value in _valid_values(profile) if day == yesterday), None
    )


def latest_community_value(raw: Any) -> float | None:
    if not (profile := _first_profile(raw)):
        return None
    values = [value for _, value in _valid_values(profile) if value > 0]
    return values[-1] if values else None

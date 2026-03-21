"""NetzOÖ eService API client."""
import logging
from datetime import date, timedelta

import requests

from .const import (
    CLIENT_ID_HEADER,
    CONSUMPTION_PROFILE_URL,
    CONTRACT_ACCOUNT_URL,
    DASHBOARD_URL,
    LOGIN_URL,
)

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = 30  # seconds


class EServiceApi:
    def __init__(self, username, password):
        self._session = None
        self._username = username
        self._password = password
        self._data = {}

    def login(self):
        if self._session is not None:
            self._session.close()
        self._session = requests.Session()
        self._session.headers.update(CLIENT_ID_HEADER)

        response = self._session.post(
            LOGIN_URL,
            json={"j_username": self._username, "j_password": self._password},
            timeout=REQUEST_TIMEOUT,
        )

        ok = response.status_code == 200
        if not ok:
            _LOGGER.error("Login failed with status %s", response.status_code)
            self._session = None
        return ok

    def close(self):
        """Close the session and clear tokens."""
        if self._session is not None:
            self._session.close()
            self._session = None

    def _get(self, url):
        """GET request with automatic re-login on 401."""
        response = self._session.get(url, timeout=REQUEST_TIMEOUT)
        if response.status_code == 401:
            _LOGGER.debug("Got 401, re-logging in")
            if self.login():
                response = self._session.get(url, timeout=REQUEST_TIMEOUT)
        if response.status_code != 200:
            _LOGGER.error("GET %s failed: %s", url, response.status_code)
            return None
        try:
            return response.json()
        except ValueError:
            _LOGGER.error("Invalid JSON from GET %s", url)
            return None

    def _post(self, url, json_data):
        """POST request with XSRF token and automatic re-login on 401."""
        xsrf = self._session.cookies.get("XSRF-TOKEN", "")
        headers = {}
        if xsrf:
            headers["X-XSRF-TOKEN"] = xsrf

        response = self._session.post(url, json=json_data, headers=headers, timeout=REQUEST_TIMEOUT)
        if response.status_code == 401:
            _LOGGER.debug("Got 401 on POST, re-logging in")
            if self.login():
                # Re-fetch XSRF after new login
                self._session.get(DASHBOARD_URL, timeout=REQUEST_TIMEOUT)
                xsrf = self._session.cookies.get("XSRF-TOKEN", "")
                if xsrf:
                    headers["X-XSRF-TOKEN"] = xsrf
                response = self._session.post(url, json=json_data, headers=headers, timeout=REQUEST_TIMEOUT)

        if response.status_code != 200:
            _LOGGER.error("POST %s failed: %s", url, response.status_code)
            return None
        try:
            return response.json()
        except ValueError:
            _LOGGER.error("Invalid JSON from POST %s", url)
            return None

    def _fetch_daily_consumption(self, contract_account_number, mpan, days=7):
        """Fetch daily consumption profile values."""
        today = date.today()
        from_date = (today - timedelta(days=days)).isoformat()
        to_date = today.isoformat()

        data = self._post(CONSUMPTION_PROFILE_URL, {
            "dimension": "ENERGY",
            "pods": [{
                "contractAccountNumber": contract_account_number,
                "meterPointAdministrationNumber": mpan,
                "type": "ACTIVE_CURRENT",
                "timerange": {"from": from_date, "to": to_date},
                "bestAvailableGranularity": "DAY",
            }],
        })

        if not data or not isinstance(data, list) or len(data) == 0:
            return None
        return data[0]

    def _fetch_energy_community_profile(self, contract_account_number, mpan, community_id, profile_type, days=7):
        """Fetch energy community consumption profile."""
        today = date.today()
        from_date = (today - timedelta(days=days)).isoformat()
        to_date = today.isoformat()

        data = self._post(CONSUMPTION_PROFILE_URL, {
            "dimension": "ENERGY",
            "pods": [{
                "contractAccountNumber": contract_account_number,
                "meterPointAdministrationNumber": mpan,
                "type": profile_type,
                "timerange": {"from": from_date, "to": to_date},
                "bestAvailableGranularity": "DAY",
                "energyCommunityId": community_id,
            }],
        })

        if not data or not isinstance(data, list) or len(data) == 0:
            return None
        return data[0]

    def update(self):
        if self._session is None:
            if not self.login():
                raise ConnectionError("Failed to login to NetzOÖ eService")

        dashboard = self._get(DASHBOARD_URL)
        if not dashboard:
            self._session = None
            raise ConnectionError("Failed to fetch dashboard from NetzOÖ eService")

        business_partners = dashboard.get("businessPartners", [])
        if not business_partners:
            raise ValueError("No business partners found in NetzOÖ eService dashboard")

        bp = business_partners[0]
        bpn = bp.get("businessPartnerNumber", "")
        if not bpn:
            raise ValueError("Business partner has no number in NetzOÖ eService")

        result = {
            "business_partner": {
                "number": bpn,
                "name": bp.get("entity", {}).get("fullname", ""),
                "email": bp.get("email", ""),
            },
            "accounts": {},
            "meters": {},
        }

        for account in dashboard.get("contractAccounts", []):
            if not account.get("active"):
                continue

            can = account.get("contractAccountNumber", "")
            if not can:
                continue
            ca_data = self._get(f"{CONTRACT_ACCOUNT_URL}/{bpn}/{can}")
            if not ca_data:
                continue

            account_info = {
                "description": ca_data.get("description", ""),
                "address": f"{ca_data.get('address', {}).get('postcode', '')} {ca_data.get('address', {}).get('city', '')}, {ca_data.get('address', {}).get('street', '')} {ca_data.get('address', {}).get('housenumber', '')}".strip(),
                "branch": ca_data.get("branch", ""),
                "invoices": [],
                "installment": None,
            }

            # Invoices
            for inv in ca_data.get("invoices", []):
                account_info["invoices"].append({
                    "number": inv.get("invoiceNumber", ""),
                    "date": inv.get("invoiceDate", ""),
                    "total": inv.get("total", 0),
                })

            # Installment
            inst = ca_data.get("installmentAgreement")
            if inst:
                next_due = None
                installments = inst.get("installments", [])
                if installments:
                    next_due = installments[0].get("dueDate")
                account_info["installment"] = {
                    "amount": inst.get("currentAmount", 0),
                    "cycle": inst.get("cycle", ""),
                    "next_due_date": next_due,
                    "begin_date": inst.get("beginDate"),
                    "end_date": inst.get("endDate"),
                }

            result["accounts"][can] = account_info

            # Contracts and meters
            for contract in ca_data.get("contracts", []):
                cn = contract.get("contractNumber", "")
                pod = contract.get("pointOfDelivery", {})
                meter_number = pod.get("meter", {}).get("meterNumber", "")
                mpan = pod.get("meterPointAdministrationNumber", "")

                if not meter_number:
                    continue

                meter_info = {
                    "contract_account": can,
                    "contract_number": cn,
                    "meter_number": meter_number,
                    "mpan": mpan,
                    "branch": contract.get("branch", "STROM"),
                    "scale_type": contract.get("scaleType", ""),
                    "smart_meter_type": contract.get("smartMeterType", ""),
                    "smart_meter_active": pod.get("smartMeterActive", False),
                    "supplier": contract.get("supplier", {}).get("name", ""),
                    "contract_power": None,
                    "move_in_date": contract.get("moveInDate"),
                    "address": account_info["address"],
                }

                # Meter reading
                readings = pod.get("lastReadings", {}).get("values", [])
                if readings:
                    reading = readings[0]
                    raw_value = reading.get("newResult", {}).get("readingValue")
                    try:
                        meter_info["meter_reading"] = float(raw_value) if raw_value is not None else None
                    except (TypeError, ValueError):
                        meter_info["meter_reading"] = None
                    meter_info["meter_reading_timestamp"] = reading.get("newResult", {}).get("timestamp")
                else:
                    meter_info["meter_reading"] = None
                    meter_info["meter_reading_timestamp"] = None

                # Monthly trend
                mt = pod.get("monthlyTrend")
                if mt:
                    meter_info["monthly_trend_current"] = {
                        "sum": mt.get("consumptionNew", {}).get("sum", 0),
                        "per_day": mt.get("consumptionNew", {}).get("perDay", 0),
                        "days": mt.get("consumptionNew", {}).get("days", 0),
                        "from": mt.get("timerangeNew", {}).get("from", ""),
                        "to": mt.get("timerangeNew", {}).get("to", ""),
                    }
                    meter_info["monthly_trend_previous"] = {
                        "sum": mt.get("consumptionOld", {}).get("sum", 0),
                        "per_day": mt.get("consumptionOld", {}).get("perDay", 0),
                        "days": mt.get("consumptionOld", {}).get("days", 0),
                        "from": mt.get("timerangeOld", {}).get("from", ""),
                        "to": mt.get("timerangeOld", {}).get("to", ""),
                    }
                else:
                    meter_info["monthly_trend_current"] = None
                    meter_info["monthly_trend_previous"] = None

                # Billing period consumptions
                cons = contract.get("consumptions", {})
                meter_info["total_consumption"] = cons.get("totalConsumption", 0)
                meter_info["consumption_periods"] = []
                for period in cons.get("values", []):
                    meter_info["consumption_periods"].append({
                        "from": period.get("from", ""),
                        "to": period.get("to", ""),
                        "value": period.get("value", 0),
                        "days": period.get("nrOfDays", 0),
                        "per_day": period.get("consumptionPerDay", 0),
                    })

                # Generation data / traffic light
                gen = contract.get("generationData", {})
                meter_info["traffic_light"] = gen.get("trafficLightColor", "")

                # Energy communities
                meter_info["energy_communities"] = []
                ec_data = contract.get("energyCommunityData", {})
                for ts in ec_data.get("timeslices", []):
                    if ts.get("status") == "ACTIVE":
                        meter_info["energy_communities"].append({
                            "id": ts.get("energyCommunityId", ""),
                            "name": ts.get("energyCommunityName", ""),
                            "status": ts.get("status", ""),
                            "from": ts.get("from", ""),
                            "to": ts.get("to", ""),
                        })

                # Daily consumption from smart meter profile
                meter_info["daily_consumption"] = None
                meter_info["yesterday_consumption"] = None
                meter_info["weekly_consumption"] = None

                if pod.get("smartMeterActive") and mpan:
                    try:
                        profile = self._fetch_daily_consumption(can, mpan)
                        if profile:
                            meter_info["contract_power"] = profile.get("contractPower")
                            meter_info["weekly_consumption"] = profile.get("sum", {}).get("value") if profile.get("sum") else None

                            values = profile.get("profileValues", [])
                            # Find yesterday's value
                            # API returns UTC timestamps where e.g. 2026-03-19T23:00:00Z
                            # represents 2026-03-20 in CET (Austria). Add 1 day to UTC date.
                            yesterday = (date.today() - timedelta(days=1)).isoformat()
                            for pv in reversed(values):
                                dt = pv.get("datetime", "")
                                if pv.get("status") in ("VALID", "CALCULATED") and pv.get("value") is not None:
                                    utc_date_str = dt[:10] if "T" in dt else dt
                                    try:
                                        local_date = (date.fromisoformat(utc_date_str) + timedelta(days=1)).isoformat()
                                    except ValueError:
                                        local_date = utc_date_str
                                    if local_date == yesterday:
                                        meter_info["yesterday_consumption"] = pv["value"]
                                    # Latest valid value as daily consumption
                                    if meter_info["daily_consumption"] is None:
                                        meter_info["daily_consumption"] = pv["value"]
                    except Exception:
                        _LOGGER.exception("Failed to fetch consumption profile for %s", meter_number)

                # Energy community profiles
                for ec in meter_info["energy_communities"]:
                    ec["own_coverage"] = None
                    ec["consumption"] = None
                    if mpan:
                        try:
                            # Own coverage (how much from community)
                            profile = self._fetch_energy_community_profile(
                                can, mpan, ec["id"],
                                "ENERGY_COMMUNITY_OWN_COVERAGE",
                                days=3,
                            )
                            if profile and profile.get("profileValues"):
                                for pv in reversed(profile["profileValues"]):
                                    if pv.get("status") in ("VALID", "CALCULATED") and pv.get("value") is not None and pv["value"] > 0:
                                        ec["own_coverage"] = pv["value"]
                                        break

                            # Consumption per contribution factor
                            profile = self._fetch_energy_community_profile(
                                can, mpan, ec["id"],
                                "ENERGY_COMMUNITY_CONSUMPTION_PER_CONTRIBUTION_FACTOR",
                                days=3,
                            )
                            if profile and profile.get("profileValues"):
                                for pv in reversed(profile["profileValues"]):
                                    if pv.get("status") in ("VALID", "CALCULATED") and pv.get("value") is not None and pv["value"] > 0:
                                        ec["consumption"] = pv["value"]
                                        break
                        except Exception:
                            _LOGGER.exception("Failed to fetch EC profile for %s / %s", meter_number, ec["name"])

                result["meters"][meter_number] = meter_info

        self._data = result

    @property
    def data(self):
        return self._data

    @property
    def state(self):
        """Legacy property: return {meter_number: reading_value} for backward compat."""
        meters = {}
        for meter_id, info in self._data.get("meters", {}).items():
            if info.get("meter_reading") is not None:
                meters[meter_id] = info["meter_reading"]
        return meters

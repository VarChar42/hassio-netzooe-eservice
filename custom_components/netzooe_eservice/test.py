import json
import os
import sys

# Standalone test: inline the constants to avoid relative import issues
sys.path.insert(0, os.path.dirname(__file__))

import requests
from datetime import date, timedelta
import logging

logging.basicConfig(level=logging.DEBUG)

BASE_URL = "https://eservice.netzooe.at/service"
LOGIN_URL = f"{BASE_URL}/j_security_check"
DASHBOARD_URL = f"{BASE_URL}/v1.0/dashboard"
CONTRACT_ACCOUNT_URL = f"{BASE_URL}/v1.0/contract-accounts"
CONSUMPTION_PROFILE_URL = f"{BASE_URL}/v1.0/consumptions/profile/active"
CLIENT_ID_HEADER = {"client-id": "netzonline"}

user = os.getenv("ESERVICE_USER")
pw = os.getenv("ESERVICE_PW")

session = requests.Session()
session.headers.update(CLIENT_ID_HEADER)

# Login
r = session.post(LOGIN_URL, json={"j_username": user, "j_password": pw})
print(f"Login: {r.status_code}")

# Dashboard
r = session.get(DASHBOARD_URL)
print(f"Dashboard: {r.status_code}")
dashboard = r.json()
bpn = dashboard["businessPartners"][0]["businessPartnerNumber"]

# Contract accounts
for account in dashboard["contractAccounts"]:
    if not account["active"]:
        continue
    can = account["contractAccountNumber"]
    r = session.get(f"{CONTRACT_ACCOUNT_URL}/{bpn}/{can}")
    print(f"\nContract Account {can}: {r.status_code}")
    ca = r.json()

    for contract in ca.get("contracts", []):
        pod = contract.get("pointOfDelivery", {})
        meter = pod.get("meter", {}).get("meterNumber", "?")
        mpan = pod.get("meterPointAdministrationNumber", "")
        reading = pod.get("lastReadings", {}).get("values", [{}])[0]
        value = reading.get("newResult", {}).get("readingValue", "N/A")
        print(f"  Meter {meter}: {value} kWh")

        mt = pod.get("monthlyTrend", {})
        if mt:
            curr = mt.get("consumptionNew", {})
            prev = mt.get("consumptionOld", {})
            print(f"  Monthly trend - Current: {curr.get('sum')} kWh ({curr.get('perDay')} kWh/day), Previous: {prev.get('sum')} kWh")

        # Consumption profiles
        if pod.get("smartMeterActive") and mpan:
            today = date.today()
            xsrf = session.cookies.get("XSRF-TOKEN", "")
            headers = {"X-XSRF-TOKEN": xsrf} if xsrf else {}

            r = session.post(CONSUMPTION_PROFILE_URL, json={
                "dimension": "ENERGY",
                "pods": [{
                    "contractAccountNumber": can,
                    "meterPointAdministrationNumber": mpan,
                    "type": "ACTIVE_CURRENT",
                    "timerange": {"from": (today - timedelta(days=7)).isoformat(), "to": today.isoformat()},
                    "bestAvailableGranularity": "DAY",
                }],
            }, headers=headers)
            print(f"  Profile API: {r.status_code}")
            if r.status_code == 200:
                profile = r.json()
                if profile:
                    p = profile[0]
                    print(f"  Contract Power: {p.get('contractPower')} kW")
                    print(f"  Weekly Sum: {p.get('sum', {}).get('value')} kWh")
                    for pv in p.get("profileValues", []):
                        print(f"    {pv['datetime']}: {pv['value']} kWh ({pv['status']})")

        # Energy communities
        ec_data = contract.get("energyCommunityData", {})
        for ts in ec_data.get("timeslices", []):
            if ts.get("status") == "ACTIVE":
                print(f"  Energy Community: {ts['energyCommunityName']} ({ts['status']})")

    # Invoices
    for inv in ca.get("invoices", []):
        print(f"  Invoice {inv['invoiceNumber']}: {inv['total']} EUR ({inv['invoiceDate']})")

    # Installment
    inst = ca.get("installmentAgreement")
    if inst:
        print(f"  Installment: {inst['currentAmount']} EUR/{inst['cycle']}")
        for i in inst.get("installments", []):
            print(f"    Due: {i['dueDate']} - {i['amount']} EUR")

import requests
import json
import datetime

from homeassistant.util import Throttle

MIN_TIME_BETWEEN_UPDATES = datetime.timedelta(hours=1)

class EServiceApi:
    def __init__(self, username, password, base_url):
        self._logged_in = False
        self._username = username
        self._password = password
        self._base_url = base_url
        self._state = {}

    def login(self):
        response = requests.post(
            self._base_url + "/j_security_check",
            json={"j_username": self._username, "j_password": self._password},
        )

        self._logged_in = response.status_code == 200

        if self._logged_in:
            self._cookies = response.headers["Set-Cookie"]

        return self._logged_in

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        if not self._logged_in:
            self.login()

        headers = {"Cookie": self._cookies}

        response = requests.get(
            self._base_url + "/v1.0/dashboard",
            headers={"Cookie": self._cookies},
        )

        if response.status_code != 200:
            self._logged_in = False
            return

        dashboard = json.loads(response.text)

        business_partner_number = dashboard["businessPartners"][0][
            "businessPartnerNumber"
        ]

        meters = {}

        for account in dashboard["contractAccounts"]:
            if not account["active"]:
                continue

            contract_account_number = account["contractAccountNumber"]

            response = requests.get(
                self._base_url + "/v1.0/contract-accounts/"
                + business_partner_number
                + "/"
                + contract_account_number,
                headers=headers,
            )

            contracts = json.loads(response.text)["contracts"]

            for contract in contracts:
                last_reading = contract["pointOfDelivery"]["lastReadings"]["values"][0]
                meter = last_reading["meternumber"]
                value = last_reading["newResult"]["readingValue"]
                meters[meter] = float(value)

        self._state = meters

    @property
    def state(self):
        return self._state

import requests
import json


class EServiceApi:
    def __init__(self, username, password):
        self._session = None
        self._username = username
        self._password = password
        self._state = {}

    def login(self):
        self._session = requests.Session()

        response = self._session.post(
            "https://eservice.netzooe.at/service/j_security_check",
            json={"j_username": self._username, "j_password": self._password},
            headers={
                "client-id": "netzonline"
            }
        )

        ok = response.status_code == 200

        if not ok:
            self._session = None
        return ok

    def update(self):
        if self._session == None:
            self.login()
        
        if self._session == None:
            return
        
        response = self._session.get(
            "https://eservice.netzooe.at/service/v1.0/dashboard"
        )

        if response.status_code != 200:
            self._session = None
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

            response = self._session.get(
                "https://eservice.netzooe.at/service/v1.0/contract-accounts/"
                + business_partner_number
                + "/"
                + contract_account_number
            )

            if response.status_code != 200:
                continue

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

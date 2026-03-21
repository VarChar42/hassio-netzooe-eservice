"""Constants for the NetzOÖ eService integration."""

DOMAIN = "netzooe_eservice"

BASE_URL = "https://eservice.netzooe.at/service"
LOGIN_URL = f"{BASE_URL}/j_security_check"
DASHBOARD_URL = f"{BASE_URL}/v1.0/dashboard"
CONTRACT_ACCOUNT_URL = f"{BASE_URL}/v1.0/contract-accounts"
CONSUMPTION_PROFILE_URL = f"{BASE_URL}/v1.0/consumptions/profile/active"

CLIENT_ID_HEADER = {"client-id": "netzonline"}

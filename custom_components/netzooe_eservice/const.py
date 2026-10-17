"""Constants for the NetzOÖ eService integration."""

from datetime import timedelta
import logging

DOMAIN = "netzooe_eservice"
LOGGER = logging.getLogger(__package__)

MANUFACTURER = "Netz Oberösterreich"
PORTAL_URL = "https://eservice.netzooe.at/app/portal/dashboard"

CONF_SCAN_INTERVAL = "scan_interval"
DEFAULT_SCAN_INTERVAL = 60
MIN_SCAN_INTERVAL = 15
MAX_SCAN_INTERVAL = 1440

PROFILE_DAYS = timedelta(days=7)
COMMUNITY_PROFILE_DAYS = timedelta(days=3)

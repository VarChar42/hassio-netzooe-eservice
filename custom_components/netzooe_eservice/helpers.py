"""Shared helpers for NetzOÖ eService integration."""
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN


def device_info(meter: dict) -> DeviceInfo:
    """Create device info for a meter."""
    return DeviceInfo(
        identifiers={(DOMAIN, meter["meter_number"])},
        name=f"NetzOÖ Meter {meter['meter_number']}",
        manufacturer="Netz Oberösterreich",
        model=meter.get("smart_meter_type", "Unknown"),
        sw_version=meter.get("scale_type", ""),
        configuration_url="https://eservice.netzooe.at/app/portal/dashboard",
    )

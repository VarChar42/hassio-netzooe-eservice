# NetzOÖ eService for Home Assistant

[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz)
[![CI](https://github.com/VarChar42/hassio-netzooe-eservice/actions/workflows/ci.yml/badge.svg)](https://github.com/VarChar42/hassio-netzooe-eservice/actions/workflows/ci.yml)

Home Assistant integration for the [Netz Oberösterreich eService portal](https://eservice.netzooe.at/). It reads smart meter readings, consumption profiles, energy community data, invoices and installments from your NetzOÖ account.

## Installation

### HACS

[![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=VarChar42&repository=hassio-netzooe-eservice&category=integration)

1. Open HACS and add `https://github.com/VarChar42/hassio-netzooe-eservice` as a custom repository of type **Integration**.
2. Install **NetzOÖ eService** and restart Home Assistant.

### Manual

Copy `custom_components/netzooe_eservice` into your `config/custom_components` directory and restart Home Assistant.

## Setup

[![Add integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=netzooe_eservice)

**Settings → Devices & services → Add integration → NetzOÖ eService**, then sign in with your eService credentials.

The update interval (default 60 minutes, 15–1440) can be changed via **Configure**. When the password changes, Home Assistant asks for the new one.

## Entities

Each metering point (Zählpunkt) gets its own device. PV systems with separate consumption and feed-in metering points on the same meter therefore show up as two devices.

| Entity | Notes |
|---|---|
| Energy consumption | Meter counter (OBIS 1.8.x), `total_increasing`; use it in the Energy dashboard |
| Energy feed-in | Feed-in counter (OBIS 2.8.x), for PV systems |
| Register *x* | Individual tariff registers when a meter has more than one |
| Monthly peak power | Highest 15 min average power this month (OBIS 1.6.0) |
| Consumption yesterday / last 7 days | From the daily smart meter profile |
| Consumption last 30 days / previous 30 days / last 365 days | Trend values from the portal |
| Daily average | Average of the last 30 days |
| Billed consumption | Sum of all billing periods, details in attributes |
| *Community* own coverage / consumption | Per energy community (EEG), latest validated day |
| Last invoice amount / date, installment amount / next due date | When the portal provides them |
| Unread messages | Portal inbox |
| Smart meter active, disconnection notification, paperless billing, *community* active | Binary sensors |
| Supplier, smart meter type, grid traffic light, move-in date, address | Diagnostic (address disabled by default) |

The portal publishes smart meter data once per day, so values typically lag by one day.

## Diagnostics

**Settings → Devices & services → NetzOÖ eService → ⋮ → Download diagnostics** exports the parsed data with personal identifiers redacted.

## Upgrading from 2.x

Entities are now keyed by metering point instead of meter number, and existing entities are migrated automatically. The old **Meter reading** entity is not migrated. It reported whichever register came first, often the kW peak instead of the kWh counter. Remove it and switch the Energy dashboard to **Energy consumption**.

## Development

```bash
pip install -r requirements_test.txt
ruff check . && ruff format --check .
pytest
```

The Home Assistant test harness needs Linux or macOS. On Windows, run it in WSL or Docker.

To release, bump `version` in `manifest.json` and push to `main`. Once CI passes, it creates the tag and the GitHub release with the HACS zip attached.

# NetzOÖ eService Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

A Home Assistant custom integration for [Netz Oberösterreich](https://www.netzooe.at/) eService portal. Retrieves smart meter data, consumption profiles, invoices, installment plans, and energy community information from your NetzOÖ account.

Originally created by [@VarChar42](https://github.com/VarChar42/hassio-netzooe-eservice). This fork extends the integration with additional sensors and API coverage.

## Features

### Energy Sensors
| Sensor | Description |
|---|---|
| **Meter Reading** | Total meter counter value (kWh), usable with HA Energy Dashboard |
| **Daily Consumption** | Yesterday's energy usage from smart meter profile (kWh) |
| **Weekly Consumption** | Last 7 days total energy usage (kWh) |
| **Monthly Consumption** | Current 30-day period energy usage (kWh) |
| **Previous Month Consumption** | Previous 30-day period energy usage (kWh) |
| **Daily Average** | Average daily consumption for current period (kWh/day) |
| **Total Billing Consumption** | Total kWh for the current billing period, with per-period breakdown in attributes |
| **Contract Power** | Contracted power capacity (kW) |
| **Register {ref}** | Individual register readings for multi-tariff meters (HT/NT, e.g. 1.8.1, 1.8.2) |

### Financial Sensors
| Sensor | Description |
|---|---|
| **Last Invoice Amount** | Most recent invoice total (EUR), full invoice history in attributes |
| **Last Invoice Date** | Date of the most recent invoice |
| **Installment Amount** | Current monthly installment (EUR) |
| **Next Installment Date** | Next payment due date |

### Other Sensors
| Sensor | Description |
|---|---|
| **Unread Messages** | Number of unread partner messages in your inbox |

### Binary Sensors
| Sensor | Description |
|---|---|
| **Smart Meter Active** | Whether the smart meter is active |
| **Disconnection Notification** | Whether there is a disconnection notification |
| **Paperless Billing** | Whether paperless billing is enabled |
| **{Community} Active** | Whether the energy community membership is active |

### Diagnostic Sensors
| Sensor | Description |
|---|---|
| **Supplier** | Current energy supplier name |
| **Smart Meter Type** | Meter hardware type (e.g. Advanced Smart Meter) |
| **Grid Traffic Light** | Grid capacity indicator (RED / YELLOW / GREEN) |
| **Move-in Date** | Contract start date |
| **Address** | Supply point address |

### Energy Community Sensors (per community)
| Sensor | Description |
|---|---|
| **Own Coverage** | Energy covered by the community (kWh/day) |
| **Consumption** | Consumption per contribution factor (kWh/day) |

All sensors are grouped under a device per meter, with proper device info (manufacturer, model, link to portal).

## Requirements

- A [NetzOÖ eService](https://eservice.netzooe.at/) account
- A smart meter for consumption profile data (meter readings work without one)

## Installation

### HACS (recommended)

1. Open HACS in Home Assistant
2. Go to **Integrations** > **Custom repositories**
3. Add this repository URL and select **Integration** as the category
4. Search for **NetzOÖ eService** and install it
5. Restart Home Assistant

### Manual

1. Copy the `custom_components/netzooe_eservice` folder into your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant

## Configuration

1. Go to **Settings** > **Devices & Services** > **Add Integration**
2. Search for **NetzOÖ eService**
3. Enter your eService portal username and password
4. Credentials are validated during setup

### Options

After setup, click **Configure** on the integration to adjust:

- **Update interval** - polling frequency in minutes (default: 60, min: 15, max: 1440)

### Re-authentication

If your credentials expire, the integration will prompt you to re-enter them through the Home Assistant UI instead of silently failing.

### Diagnostics

Use **Settings > Devices & Services > NetzOÖ eService > Download diagnostics** to export a sanitized snapshot of your integration data for troubleshooting. All personal information is redacted.

## How It Works

The integration authenticates with the NetzOÖ eService API and polls the following endpoints:

- **Dashboard** - account and contract overview
- **Contract Accounts** - meter readings, monthly trends, invoices, installments, energy community memberships
- **Consumption Profiles** - daily smart meter readings (last 7 days)
- **Energy Community Profiles** - own coverage and consumption per community
- **Partner Messages** - inbox message count

## Translations

The integration is available in:
- English
- German (Deutsch)

## Credits

- **Original integration** by [@VarChar42](https://github.com/VarChar42) - [hassio-netzooe-eservice](https://github.com/VarChar42/hassio-netzooe-eservice)
- **Contributors** to the original: [@mbu147](https://github.com/mbu147), [@markus-gx](https://github.com/markus-gx)

## License

This project is provided as-is. See the original repository for license details.

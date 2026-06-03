# Portland General Electric Time-of-Day Price

A custom integration for Home Assistant that provides the current pricing period and cost for Portland General Electric's (PGE) [Time-of-Day](https://portlandgeneral.com/about/info/pricing-plans/time-of-day) pricing plan. This is an offline integration reliant only on configured prices, they are not requested over the network.

**NOTE:** _This is for Portland General Electric (Oregon), not Pacific Gas and Electric (California)_\
**NOTE:** _This project is not affiliated with Portland General Electric._

## Features

- Provides a sensor (`sensor.pge_pricing_period`) indicating the current period (`off-peak`, `mid-peak`, `on-peak`).
- Dynamically updates the `cost_per_kwh` attribute based on the time, day of the week, and holidays.
- Correctly accounts for PGE-recognized holidays and their observed weekend shift rules.

## Installation via HACS

1. Open HACS in Home Assistant.
2. Click the three dots in the top right corner and select "Custom repositories".
3. Add the URL of this repository and select "Integration" as the category.
4. Search for "Portland General Electric Time-of-Day Price" in HACS and install it.
5. Restart Home Assistant.

## Configuration

1. Go to **Settings** -> **Devices & Services**.
2. Click **Add Integration**.
3. Search for "PGE Time-of-Day Price".
4. Click to add it. You will be prompted to confirm or adjust the rates.

If your rates change in the future, click the "Configure" button on the integration to update them.

## Automations Example

You can use the `sensor.pge_pricing_period` to trigger heavy loads like EV charging or running the dishwasher only when electricity is cheap.

```yaml
alias: "Start EV Charging off-peak"
trigger:
  - platform: state
    entity_id: sensor.pge_pricing_period
    to: "off-peak"
action:
  - service: switch.turn_on
    target:
      entity_id: switch.ev_charger
```

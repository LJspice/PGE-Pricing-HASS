# Portland General Electric Time-of-Day Price

Home Assistant custom component to track Portland General Electric's (PGE) Time-of-Day pricing periods and current rates.

This integration creates a sensor that reflects whether you are currently in an `off-peak`, `mid-peak`, or `on-peak` period, and provides the current USD/kWh cost as an attribute. It automatically calculates PGE holidays, including weekend observed-holiday shifting, ensuring your rates are always accurate.

Set it up completely via the UI—no YAML required!

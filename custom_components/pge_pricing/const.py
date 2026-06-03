# SPDX-License-Identifier: MIT

"""Constants for the PGE Time-of-Day Price integration."""

import datetime
from typing import Final

DOMAIN: Final = "pge_pricing"

CONF_RATE_OFF_PEAK: Final = "rate_off_peak"
CONF_RATE_MID_PEAK: Final = "rate_mid_peak"
CONF_RATE_ON_PEAK: Final = "rate_on_peak"

DEFAULT_RATE_OFF_PEAK: Final = 0.0901
DEFAULT_RATE_MID_PEAK: Final = 0.1689
DEFAULT_RATE_ON_PEAK: Final = 0.4365

START_OF_MID_PEAK: Final = datetime.time(7, 0)
START_OF_ON_PEAK: Final = datetime.time(17, 0)
END_OF_ON_PEAK: Final = datetime.time(21, 0)
MIDNIGHT: Final = datetime.time(0, 0)

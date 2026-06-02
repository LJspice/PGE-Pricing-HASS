# SPDX-License-Identifier: MIT

"""Sensor platform for PGE Time-of-Day Pricing."""

from __future__ import annotations

import calendar
import datetime
import logging
from typing import Any, NamedTuple

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.util import dt as dt_util

from .const import (
    CONF_RATE_MID_PEAK,
    CONF_RATE_OFF_PEAK,
    CONF_RATE_ON_PEAK,
    DEFAULT_RATE_MID_PEAK,
    DEFAULT_RATE_OFF_PEAK,
    DEFAULT_RATE_ON_PEAK,
    DOMAIN,
    START_OF_MID_PEAK,
    START_OF_ON_PEAK,
    END_OF_ON_PEAK,
    MIDNIGHT,
)

_LOGGER = logging.getLogger(__name__)

# Fallback polling interval, in case scheduled updates are missed
SCAN_INTERVAL = datetime.timedelta(minutes=5)


class PGEPricingData(NamedTuple):
    """Data for PGE Pricing."""

    period: str
    cost: float
    is_holiday: bool
    is_weekend: bool


def get_observed_holiday(year: int, month: int, day: int) -> datetime.date:
    """Return the observed date for a fixed-date holiday."""
    dt = datetime.date(year, month, day)
    # If the holiday falls on a Saturday, it is observed on the preceding Friday
    if dt.weekday() == 5:
        return dt - datetime.timedelta(days=1)
    # If the holiday falls on a Sunday, it is observed on the following Monday
    elif dt.weekday() == 6:
        return dt + datetime.timedelta(days=1)
    return dt


def get_nth_weekday(year: int, month: int, nth: int, weekday: int) -> datetime.date:
    """Return the date of the nth weekday of a specific month."""
    c = calendar.Calendar(firstweekday=calendar.SUNDAY)
    monthcal = c.monthdatescalendar(year, month)
    # Get all dates in the month that match the weekday
    dates = [
        d
        for week in monthcal
        for d in week
        if d.month == month and d.weekday() == weekday
    ]
    if nth > 0:
        return dates[nth - 1]
    else:
        return dates[nth]


def get_holidays(year: int) -> set[datetime.date]:
    """Calculate the observed PGE holidays for a given year."""
    holidays = set()

    # New Year's Day (Jan 1)
    holidays.add(get_observed_holiday(year, 1, 1))

    # Memorial Day (Last Monday in May)
    holidays.add(get_nth_weekday(year, 5, -1, 0))  # 0 = Monday

    # Independence Day (July 4)
    holidays.add(get_observed_holiday(year, 7, 4))

    # Labor Day (First Monday in September)
    holidays.add(get_nth_weekday(year, 9, 1, 0))

    # Thanksgiving Day (Fourth Thursday in November)
    holidays.add(get_nth_weekday(year, 11, 4, 3))  # 3 = Thursday

    # Christmas Day (December 25)
    holidays.add(get_observed_holiday(year, 12, 25))

    # Edge case: Next year's Jan 1st is Saturday, so Dec 31 of current year is observed as holiday
    next_new_year = datetime.date(year + 1, 1, 1)
    if next_new_year.weekday() == 5:  # Saturday
        holidays.add(datetime.date(year, 12, 31))

    return holidays


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator = PGEPricingCoordinator(hass, entry)

    # Ensure it polls on startup immediately
    await coordinator.async_config_entry_first_refresh()

    async_add_entities(
        [
            PGEPricingPeriodSensor(coordinator, entry),
            PGEPricingPriceSensor(coordinator, entry),
        ]
    )


class PGEPricingCoordinator(DataUpdateCoordinator[PGEPricingData]):
    """Coordinator to manage PGE Pricing updates."""

    rate_off_peak: float
    rate_mid_peak: float
    rate_on_peak: float
    _unsub_next_transition: CALLBACK_TYPE | None
    _next_expected_transition: datetime.datetime | None
    _is_scheduled_update: bool

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        opts = entry.options if entry.options else entry.data
        self.rate_off_peak = float(opts.get(CONF_RATE_OFF_PEAK, DEFAULT_RATE_OFF_PEAK))
        self.rate_mid_peak = float(opts.get(CONF_RATE_MID_PEAK, DEFAULT_RATE_MID_PEAK))
        self.rate_on_peak = float(opts.get(CONF_RATE_ON_PEAK, DEFAULT_RATE_ON_PEAK))

        self._unsub_next_transition = None
        self._next_expected_transition = None
        self._is_scheduled_update = False

        _LOGGER.debug(
            "Initialized PGE Pricing Coordinator with rates: Off-Peak=$%s, Mid-Peak=$%s, On-Peak=$%s",
            self.rate_off_peak,
            self.rate_mid_peak,
            self.rate_on_peak,
        )

    async def _async_update_data(self) -> PGEPricingData:
        """Calculate the current pricing data and schedule next transition."""
        now = dt_util.now()
        data = self._calculate_data(now)

        # Detect missed transition
        if (
            self.data is not None
            and (data.period != self.data.period or data.cost != self.data.cost)
            and not self._is_scheduled_update
            and self._next_expected_transition is not None
            and now > self._next_expected_transition + datetime.timedelta(seconds=10)
        ):
            _LOGGER.warning(
                "Missed scheduled PGE transition at %s! Polling recovered state: %s -> %s (at %s)",
                self._next_expected_transition,
                self.data.period,
                data.period,
                now,
            )

        # Reset scheduled update flag
        self._is_scheduled_update = False

        # Cancel any pending transition track
        if self._unsub_next_transition:
            self._unsub_next_transition()

        # Schedule the next exact transition point
        self._next_expected_transition = self._get_next_transition(now)
        _LOGGER.debug(
            "Scheduling next PGE transition for %s", self._next_expected_transition
        )

        self._unsub_next_transition = async_track_point_in_time(
            self.hass, self._async_scheduled_update, self._next_expected_transition
        )

        return data

    async def _async_scheduled_update(self, _now: datetime.datetime) -> None:
        """Triggered at a specific transition point."""
        _LOGGER.debug("PGE Scheduled transition triggered")
        self._is_scheduled_update = True
        await self.async_refresh()

    def _get_next_transition(self, now: datetime.datetime) -> datetime.datetime:
        """Calculate the next time the pricing period will change."""
        today = now.date()
        transition_times = [
            MIDNIGHT,
            START_OF_MID_PEAK,
            START_OF_ON_PEAK,
            END_OF_ON_PEAK,
        ]

        for t in transition_times:
            transition = dt_util.as_local(datetime.datetime.combine(today, t))
            if transition > now:
                return transition

        # No more transitions today, next is tomorrow at midnight
        tomorrow = today + datetime.timedelta(days=1)
        return dt_util.as_local(
            datetime.datetime.combine(tomorrow, transition_times[0])
        )

    def _calculate_data(self, now: datetime.datetime) -> PGEPricingData:
        """Calculate the current pricing data based on the schedule."""
        current_date = now.date()
        current_time = now.time()

        holidays = get_holidays(current_date.year)

        # Determine if today is a weekend or holiday
        is_weekend = current_date.weekday() in (5, 6)  # 5 = Saturday, 6 = Sunday
        is_holiday = current_date in holidays

        if is_weekend or is_holiday:
            period = "off-peak"
            cost = self.rate_off_peak
        else:
            # Weekday non-holiday schedule
            if START_OF_ON_PEAK <= current_time < END_OF_ON_PEAK:
                period = "on-peak"
                cost = self.rate_on_peak
            elif START_OF_MID_PEAK <= current_time < START_OF_ON_PEAK:
                period = "mid-peak"
                cost = self.rate_mid_peak
            else:
                period = "off-peak"
                cost = self.rate_off_peak

        return PGEPricingData(period, cost, is_holiday, is_weekend)


class PGEPricingBaseEntity(CoordinatorEntity[PGEPricingCoordinator], SensorEntity):
    """Base representation of a PGE Pricing entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: PGEPricingCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Portland General Electric Time-of-Day Pricing",
            manufacturer="Portland General Electric",
            entry_type=DeviceEntryType.SERVICE,
        )


class PGEPricingPeriodSensor(PGEPricingBaseEntity):
    """Representation of a PGE Pricing Period sensor."""

    _attr_translation_key = "period"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["off-peak", "mid-peak", "on-peak"]

    def __init__(self, coordinator: PGEPricingCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_period"

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.period

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        if not self.coordinator.data:
            return {}
        return {
            "is_holiday": self.coordinator.data.is_holiday,
            "is_weekend": self.coordinator.data.is_weekend,
        }

    @property
    def icon(self) -> str:
        """Return the icon based on the current period."""
        if not self.coordinator.data or self.coordinator.data.period == "off-peak":
            return "mdi:flash-outline"
        if self.coordinator.data.period == "on-peak":
            return "mdi:flash-alert"
        if self.coordinator.data.period == "mid-peak":
            return "mdi:flash"
        return "mdi:flash-outline"


class PGEPricingPriceSensor(PGEPricingBaseEntity):
    """Representation of a PGE Pricing Price sensor."""

    _attr_translation_key = "price"
    _attr_native_unit_of_measurement = "USD/kWh"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: PGEPricingCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_price"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.cost

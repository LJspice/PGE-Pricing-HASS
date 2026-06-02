# SPDX-License-Identifier: MIT

"""Config flow for PGE Time-of-Day Pricing integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    CONF_RATE_MID_PEAK,
    CONF_RATE_OFF_PEAK,
    CONF_RATE_ON_PEAK,
    DEFAULT_RATE_MID_PEAK,
    DEFAULT_RATE_OFF_PEAK,
    DEFAULT_RATE_ON_PEAK,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class PGEPricingConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for PGE Time-of-Day Price."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        # Only a single instance of the integration is allowed
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            return self.async_create_entry(
                title="PGE Time-of-Day Price", data=user_input
            )

        data_schema: vol.Schema = vol.Schema(
            {
                vol.Required(CONF_RATE_OFF_PEAK, default=DEFAULT_RATE_OFF_PEAK): float,
                vol.Required(CONF_RATE_MID_PEAK, default=DEFAULT_RATE_MID_PEAK): float,
                vol.Required(CONF_RATE_ON_PEAK, default=DEFAULT_RATE_ON_PEAK): float,
            }
        )

        return self.async_show_form(step_id="user", data_schema=data_schema)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return PGEPricingOptionsFlow(config_entry)


class PGEPricingOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for PGE Pricing."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = self._config_entry.options
        data = self._config_entry.data

        data_schema: vol.Schema = vol.Schema(
            {
                vol.Required(
                    CONF_RATE_OFF_PEAK,
                    default=options.get(
                        CONF_RATE_OFF_PEAK,
                        data.get(CONF_RATE_OFF_PEAK, DEFAULT_RATE_OFF_PEAK),
                    ),
                ): float,
                vol.Required(
                    CONF_RATE_MID_PEAK,
                    default=options.get(
                        CONF_RATE_MID_PEAK,
                        data.get(CONF_RATE_MID_PEAK, DEFAULT_RATE_MID_PEAK),
                    ),
                ): float,
                vol.Required(
                    CONF_RATE_ON_PEAK,
                    default=options.get(
                        CONF_RATE_ON_PEAK,
                        data.get(CONF_RATE_ON_PEAK, DEFAULT_RATE_ON_PEAK),
                    ),
                ): float,
            }
        )

        return self.async_show_form(step_id="init", data_schema=data_schema)

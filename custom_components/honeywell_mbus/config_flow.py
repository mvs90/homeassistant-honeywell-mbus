"""UI setup, safe reconfiguration and options for a direct M-Bus endpoint."""

from __future__ import annotations

from ipaddress import IPv6Address
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .api import HoneywellMbusClient, IdentityError, MbusError, UnsupportedMeterError
from .const import (
    CONF_ADDRESS,
    CONF_SCAN_INTERVAL,
    CONF_SERIAL,
    CONF_TIMEOUT,
    DEFAULT_ADDRESS,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    DOMAIN,
    MODEL,
)


def normalize_host(value: str) -> str:
    """Accept hostnames/IPs without URLs, ports or whitespace."""
    value = cv.string(value).strip().lower().rstrip(".")
    if (
        not value
        or any(char.isspace() for char in value)
        or any(char in value for char in "/?#@[]")
    ):
        raise vol.Invalid("Enter a hostname or IP address without a URL")
    if ":" in value:
        try:
            IPv6Address(value)
        except ValueError as error:
            raise vol.Invalid("Enter the port in its separate field") from error
    return value


def connection_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, vol.UNDEFINED)): cv.string,
            vol.Required(CONF_PORT, default=defaults.get(CONF_PORT, DEFAULT_PORT)): cv.port,
            vol.Required(
                CONF_ADDRESS, default=defaults.get(CONF_ADDRESS, DEFAULT_ADDRESS)
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=250)),
        }
    )


async def validate_connection(
    data: dict[str, Any], *, expected_serial: str | None = None
) -> dict[str, str]:
    """Probe only the selected address and always release the temporary socket."""
    client = HoneywellMbusClient(
        data[CONF_HOST], data[CONF_PORT], data[CONF_ADDRESS], expected_serial=expected_serial
    )
    try:
        sample = await client.async_read()
        return {CONF_SERIAL: sample.reading.serial, "unique_id": sample.reading.unique_id}
    finally:
        await client.async_close()


class HoneywellConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure one supported meter per TCP bridge; never scan the whole bus."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input = connection_schema()(user_input)
            try:
                user_input[CONF_HOST] = normalize_host(user_input[CONF_HOST])
            except vol.Invalid:
                return self.async_show_form(
                    step_id="user",
                    data_schema=connection_schema(user_input),
                    errors={CONF_HOST: "invalid_host"},
                )
            # One reader per gateway prevents independent sockets fighting over
            # a shared serial bus. Multiple meters/bridge are not a v0.1 feature.
            self._async_abort_entries_match(
                {CONF_HOST: user_input[CONF_HOST], CONF_PORT: user_input[CONF_PORT]}
            )
            try:
                found = await validate_connection(user_input)
            except UnsupportedMeterError:
                errors["base"] = "unsupported_meter"
            except MbusError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(found["unique_id"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=MODEL, data={**user_input, CONF_SERIAL: found[CONF_SERIAL]}
                )
        return self.async_show_form(
            step_id="user", data_schema=connection_schema(user_input), errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input = connection_schema()(user_input)
            try:
                user_input[CONF_HOST] = normalize_host(user_input[CONF_HOST])
            except vol.Invalid:
                return self.async_show_form(
                    step_id="reconfigure",
                    data_schema=connection_schema(user_input),
                    errors={CONF_HOST: "invalid_host"},
                )
            for existing in self._async_current_entries():
                if (
                    existing.entry_id != entry.entry_id
                    and existing.data[CONF_HOST] == user_input[CONF_HOST]
                    and existing.data[CONF_PORT] == user_input[CONF_PORT]
                ):
                    return self.async_abort(reason="already_configured")
            try:
                found = await validate_connection(
                    user_input, expected_serial=entry.data[CONF_SERIAL]
                )
            except IdentityError:
                errors["base"] = "wrong_meter"
            except UnsupportedMeterError:
                errors["base"] = "unsupported_meter"
            except MbusError:
                errors["base"] = "cannot_connect"
            else:
                if found["unique_id"] != entry.unique_id:
                    errors["base"] = "wrong_meter"
                else:
                    return self.async_update_reload_and_abort(entry, data_updates=user_input)
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=connection_schema(user_input or dict(entry.data)),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> HoneywellOptionsFlow:
        return HoneywellOptionsFlow()


class HoneywellOptionsFlow(config_entries.OptionsFlowWithReload):
    """Change polling and response timeout; no UART or meter writes."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=self.config_entry.options.get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=3600)),
                vol.Required(
                    CONF_TIMEOUT,
                    default=self.config_entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
                ): vol.All(vol.Coerce(float), vol.Range(min=0.5, max=30)),
            }
        )
        if user_input is not None:
            return self.async_create_entry(title="", data=schema(user_input))
        return self.async_show_form(step_id="init", data_schema=schema)

"""Config flow for the Acer Projector integration."""

import logging
import os
from pathlib import Path
from typing import Any

import serial
import serial.tools.list_ports
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TYPE, UnitOfTime
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from .const import (
    CONF_BAUD_RATE,
    CONF_CONNECTION_TYPE,
    CONF_DEFAULT_INTERVAL,
    CONF_INTERVAL,
    CONF_MODEL,
    CONF_SERIAL_PORT,
    CONF_TYPE_SERIAL,
    CONF_TYPE_TCP,
    DEFAULT_BAUD_RATE,
    DEFAULT_PORT,
    DOMAIN,
)
from .projector import AcerProjectorSerial, AcerProjectorTcp

_LOGGER = logging.getLogger(__name__)

MODELS = ["H6546Ki", "default"]


class AcerProjectorConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Acer Projector."""

    VERSION = 1

    _step_setup_serial_schema = None

    _step_setup_tcp_schema = vol.Schema(
        {
            vol.Required(CONF_HOST): TextSelector(),
            vol.Required(CONF_PORT, default=DEFAULT_PORT): NumberSelector(
                NumberSelectorConfig(min=1, max=65535, mode=NumberSelectorMode.BOX)
            ),
            vol.Optional(CONF_MODEL): SelectSelector(
                SelectSelectorConfig(
                    options=MODELS,
                    mode=SelectSelectorMode.DROPDOWN,
                    custom_value=True,
                )
            ),
        }
    )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["setup_serial", "setup_tcp"],
        )

    async def async_step_setup_serial(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the setup serial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            title, data, options = await self.validate_input_setup_serial(
                user_input, errors
            )
            if not errors:
                return self.async_create_entry(title=title, data=data, options=options)

        ports = await self.hass.async_add_executor_job(serial.tools.list_ports.comports)
        list_of_ports = {}
        for port in ports:
            list_of_ports[port.device] = (
                f"{port}, s/n: {port.serial_number or 'n/a'}"
                + (f" - {port.manufacturer}" if port.manufacturer else "")
            )

        self._step_setup_serial_schema = vol.Schema(
            {
                vol.Required(CONF_SERIAL_PORT, default=""): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(value=k, label=v)
                            for k, v in list_of_ports.items()
                        ],
                        mode=SelectSelectorMode.DROPDOWN,
                        custom_value=True,
                        sort=True,
                    )
                ),
                vol.Required(CONF_BAUD_RATE, default=DEFAULT_BAUD_RATE): vol.In(
                    AcerProjectorSerial.BAUD_RATES
                ),
                vol.Optional(CONF_MODEL): SelectSelector(
                    SelectSelectorConfig(
                        options=MODELS,
                        mode=SelectSelectorMode.DROPDOWN,
                        custom_value=True,
                    )
                ),
            }
        )

        if user_input is not None:
            data_schema = self.add_suggested_values_to_schema(
                self._step_setup_serial_schema, user_input
            )
        else:
            data_schema = self._step_setup_serial_schema

        return self.async_show_form(
            step_id="setup_serial",
            data_schema=data_schema,
            errors=errors,
        )

    async def validate_input_setup_serial(
        self, data: dict[str, Any], errors: dict[str, str]
    ) -> tuple[str, dict[str, Any], dict[str, Any] | None]:
        """Validate serial setup input."""
        self._step_setup_serial_schema(data)

        model = data.get(CONF_MODEL)
        serial_port = data.get(CONF_SERIAL_PORT)
        baud_rate = data[CONF_BAUD_RATE]
        unique_id = None

        if serial_port is None:
            raise vol.error.RequiredFieldInvalid("No serial port configured")

        serial_port = await self.hass.async_add_executor_job(
            get_serial_by_id, serial_port
        )

        if not Path(serial_port).exists():
            errors[CONF_SERIAL_PORT] = "nonexisting_serial_port"

        if errors.get(CONF_SERIAL_PORT) is None:
            try:
                projector = AcerProjectorSerial(serial_port, baud_rate, model)
                if not await projector.connect():
                    errors["base"] = "cannot_connect"
                else:
                    _LOGGER.info("Device %s available", serial_port)
                    model = projector.model
                    unique_id = projector.unique_id
                await projector.disconnect()
            except serial.SerialException:
                errors["base"] = "cannot_connect"

        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        return (
            f"Acer {model or 'Projector'}",
            {
                CONF_MODEL: model,
                CONF_CONNECTION_TYPE: CONF_TYPE_SERIAL,
                CONF_SERIAL_PORT: serial_port,
                CONF_BAUD_RATE: baud_rate,
            },
            None,
        )

    async def async_step_setup_tcp(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step when setting up TCP configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            title, data, options = await self.validate_input_setup_tcp(
                user_input, errors
            )
            if not errors:
                return self.async_create_entry(title=title, data=data, options=options)

        return self.async_show_form(
            step_id="setup_tcp",
            data_schema=self._step_setup_tcp_schema,
            errors=errors,
        )

    async def validate_input_setup_tcp(
        self, data: dict[str, Any], errors: dict[str, str]
    ) -> tuple[str, dict[str, Any], dict[str, Any] | None]:
        """Validate TCP setup input."""
        self._step_setup_tcp_schema(data)

        model = data.get(CONF_MODEL)
        host = data[CONF_HOST]
        port = int(data[CONF_PORT])
        unique_id = None

        projector = AcerProjectorTcp(host, port, model)
        if not await projector.connect():
            errors["base"] = "cannot_connect"
        else:
            _LOGGER.info("Device on %s:%s available", host, port)
            model = projector.model
            unique_id = projector.unique_id

        await projector.disconnect()

        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        return (
            f"Acer {model or 'Projector'}",
            {
                CONF_MODEL: model,
                CONF_CONNECTION_TYPE: CONF_TYPE_TCP,
                CONF_HOST: host,
                CONF_PORT: port,
            },
            None,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Create the options flow."""
        return AcerProjectorOptionsFlowHandler()


class AcerProjectorOptionsFlowHandler(OptionsFlow):
    _OPTIONS_SCHEMA = vol.Schema(
        {
            vol.Optional(CONF_INTERVAL, default=CONF_DEFAULT_INTERVAL): NumberSelector(
                NumberSelectorConfig(
                    min=5,
                    mode=NumberSelectorMode.BOX,
                    unit_of_measurement=UnitOfTime.SECONDS,
                )
            ),
        }
    )

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._OPTIONS_SCHEMA(user_input)
            return self.async_create_entry(title="", data=user_input)

        data_schema = self.add_suggested_values_to_schema(
            self._OPTIONS_SCHEMA, self.config_entry.options
        )

        return self.async_show_form(
            step_id="init", data_schema=data_schema, errors=errors
        )


def get_serial_by_id(dev_path: str) -> str:
    """Return a /dev/serial/by-id match for given device if available."""
    by_id = "/dev/serial/by-id"
    if not Path(by_id).is_dir():
        return dev_path

    for path in (entry.path for entry in os.scandir(by_id) if entry.is_symlink()):
        if os.path.realpath(path) == dev_path:
            return path
    return dev_path

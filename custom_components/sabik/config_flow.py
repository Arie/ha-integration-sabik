"""Config flow for the Sabik integration."""

from __future__ import annotations

import glob
import os
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import section
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)
from serial.tools.list_ports import comports

from . import modbus
from .const import (
    CONF_BAUDRATE,
    CONF_HOST,
    CONF_PARITY,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_SLAVE,
    CONF_TCP_PORT,
    CONF_TRANSPORT,
    DEFAULT_BAUDRATE,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLAVE,
    DEFAULT_TCP_PORT,
    DOMAIN,
)
from .coordinator import settings_from_entry
from .modbus import ReadBlock, SabikModbusError

CONF_PROTOCOL = "protocol"
SECTION_ADVANCED = "advanced"

BAUDRATES = ["4800", "9600", "19200", "38400"]
PARITY_TO_CODE = {"even": "E", "odd": "O", "none": "N"}
PROTOCOLS = ["rtu_over_tcp", "tcp"]


def _by_id_labels(
    devices: list[tuple[str, str]], by_id_links: dict[str, str]
) -> dict[str, str]:
    """Map (device, description) pairs to by-id paths where one resolves to them.

    by_id_links maps each /dev/serial/by-id path to its resolved device.
    """
    ports: dict[str, str] = {}
    for device, description in devices:
        path = next(
            (link for link, target in sorted(by_id_links.items()) if target == device),
            device,
        )
        ports[path] = f"{description} ({path})"
    return ports


async def async_list_serial_ports(hass: HomeAssistant) -> dict[str, str]:
    """Return serial ports as {value: label}, preferring stable by-id paths."""

    def _list() -> dict[str, str]:
        devices = [(p.device, p.description) for p in comports()]
        links = {
            link: os.path.realpath(link)
            for link in glob.glob("/dev/serial/by-id/*")
        }
        return _by_id_labels(devices, links)

    return await hass.async_add_executor_job(_list)


def _number(minimum: int, maximum: int, unit: str | None = None) -> NumberSelector:
    config = NumberSelectorConfig(
        min=minimum, max=maximum, step=1, mode=NumberSelectorMode.BOX
    )
    if unit:
        config["unit_of_measurement"] = unit
    return NumberSelector(config)


def _select(options: list[str], translation_key: str | None = None) -> SelectSelector:
    config = SelectSelectorConfig(options=options, mode=SelectSelectorMode.DROPDOWN)
    if translation_key:
        config["translation_key"] = translation_key
    return SelectSelector(config)


def _common_advanced() -> dict[Any, Any]:
    return {
        vol.Required(CONF_SLAVE, default=DEFAULT_SLAVE): _number(1, 247),
        vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): _number(
            2, 60, "s"
        ),
    }


def _network_schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_HOST): TextSelector(),
            vol.Required(CONF_TCP_PORT, default=DEFAULT_TCP_PORT): _number(1, 65535),
            vol.Required(CONF_PROTOCOL, default="rtu_over_tcp"): _select(
                PROTOCOLS, "protocol"
            ),
            vol.Required(SECTION_ADVANCED): section(
                vol.Schema(_common_advanced()), {"collapsed": True}
            ),
        }
    )


class SabikConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return self.async_show_menu(step_id="user", menu_options=["serial", "network"])

    async def async_step_serial(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        ports = await async_list_serial_ports(self.hass)

        if user_input is not None:
            advanced = user_input[SECTION_ADVANCED]
            data = {
                CONF_TRANSPORT: "serial",
                CONF_PORT: user_input[CONF_PORT],
                CONF_BAUDRATE: int(advanced[CONF_BAUDRATE]),
                CONF_PARITY: PARITY_TO_CODE[advanced[CONF_PARITY]],
                CONF_SLAVE: int(advanced[CONF_SLAVE]),
                CONF_SCAN_INTERVAL: int(advanced[CONF_SCAN_INTERVAL]),
            }
            await self.async_set_unique_id(f"{data[CONF_PORT]}:{data[CONF_SLAVE]}")
            self._abort_if_unique_id_configured()
            if error := await self._async_test(data):
                errors["base"] = error
            else:
                return self.async_create_entry(title="Sabik", data=data)
        elif not ports:
            errors["base"] = "no_ports"

        schema = vol.Schema(
            {
                vol.Required(CONF_PORT): SelectSelector(
                    SelectSelectorConfig(
                        options=[{"value": k, "label": v} for k, v in ports.items()],
                        custom_value=True,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(SECTION_ADVANCED): section(
                    vol.Schema(
                        {
                            vol.Required(
                                CONF_BAUDRATE, default=str(DEFAULT_BAUDRATE)
                            ): _select(BAUDRATES),
                            vol.Required(CONF_PARITY, default="even"): _select(
                                list(PARITY_TO_CODE), "parity"
                            ),
                            **_common_advanced(),
                        }
                    ),
                    {"collapsed": True},
                ),
            }
        )
        return self.async_show_form(
            step_id="serial",
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
        )

    async def async_step_network(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            advanced = user_input[SECTION_ADVANCED]
            data = {
                CONF_TRANSPORT: user_input[CONF_PROTOCOL],
                CONF_HOST: user_input[CONF_HOST],
                CONF_TCP_PORT: int(user_input[CONF_TCP_PORT]),
                CONF_SLAVE: int(advanced[CONF_SLAVE]),
                CONF_SCAN_INTERVAL: int(advanced[CONF_SCAN_INTERVAL]),
            }
            await self.async_set_unique_id(
                f"{data[CONF_HOST]}:{data[CONF_TCP_PORT]}:{data[CONF_SLAVE]}"
            )
            self._abort_if_unique_id_configured()
            if error := await self._async_test(data):
                errors["base"] = error
            else:
                return self.async_create_entry(title="Sabik", data=data)

        return self.async_show_form(
            step_id="network",
            data_schema=self.add_suggested_values_to_schema(
                _network_schema(), user_input
            ),
            errors=errors,
        )

    async def _async_test(self, data: dict[str, Any]) -> str | None:
        """Read one input register; return an error key on failure."""
        client = modbus.create_client(settings_from_entry(data))
        try:
            await client.async_read([ReadBlock("ir", 90, 1)])
        except SabikModbusError:
            return "cannot_connect"
        finally:
            await client.async_close()
        return None

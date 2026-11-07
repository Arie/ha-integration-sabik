"""Tests for the Sabik config flow."""

from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.sabik import config_flow
from custom_components.sabik.const import (
    CONF_BAUDRATE,
    CONF_HOST,
    CONF_PARITY,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_SLAVE,
    CONF_TCP_PORT,
    CONF_TRANSPORT,
    DOMAIN,
)

from .fake_client import FakeSabikClient

_REAL_LISTER = config_flow.async_list_serial_ports
BY_ID = "/dev/serial/by-id/usb-FTDI_TEST-if00-port0"


@pytest.fixture(autouse=True)
def ports():
    with patch(
        "custom_components.sabik.config_flow.async_list_serial_ports",
        return_value={BY_ID: f"FT232R USB UART ({BY_ID})"},
    ) as mock:
        yield mock


@pytest.fixture
def client(fake_client: FakeSabikClient):
    with patch(
        "custom_components.sabik.modbus.create_client", return_value=fake_client
    ) as mock:
        yield mock


async def _start(hass: HomeAssistant, step: str) -> str:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == ["serial", "network"]
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": step}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == step
    return result["flow_id"]


async def test_serial_flow_creates_entry(hass: HomeAssistant, client) -> None:
    flow_id = await _start(hass, "serial")
    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_PORT: BY_ID, "advanced": {}}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Sabik"
    assert result["data"] == {
        CONF_TRANSPORT: "serial",
        CONF_PORT: BY_ID,
        CONF_BAUDRATE: 19200,
        CONF_PARITY: "E",
        CONF_SLAVE: 1,
        CONF_SCAN_INTERVAL: 5,
    }


async def test_serial_parity_none_saved_as_n(hass: HomeAssistant, client) -> None:
    flow_id = await _start(hass, "serial")
    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {CONF_PORT: BY_ID, "advanced": {CONF_PARITY: "none", CONF_BAUDRATE: "9600"}},
    )
    assert result["data"][CONF_PARITY] == "N"
    assert result["data"][CONF_BAUDRATE] == 9600


async def test_network_flow_creates_entry(
    hass: HomeAssistant, client, fake_client: FakeSabikClient
) -> None:
    flow_id = await _start(hass, "network")
    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {
            CONF_HOST: "192.168.1.50",
            CONF_TCP_PORT: 4001,
            "protocol": "rtu_over_tcp",
            "advanced": {},
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_TRANSPORT: "rtu_over_tcp",
        CONF_HOST: "192.168.1.50",
        CONF_TCP_PORT: 4001,
        CONF_SLAVE: 1,
        CONF_SCAN_INTERVAL: 5,
    }
    assert fake_client.closed


async def test_no_response_shows_error(
    hass: HomeAssistant, client, fake_client: FakeSabikClient
) -> None:
    flow_id = await _start(hass, "serial")
    fake_client.fail = True
    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_PORT: BY_ID, "advanced": {}}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert fake_client.closed

    fake_client.fail = False
    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_PORT: BY_ID, "advanced": {}}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_duplicate_aborts(hass: HomeAssistant, client) -> None:
    for expected in (FlowResultType.CREATE_ENTRY, FlowResultType.ABORT):
        flow_id = await _start(hass, "serial")
        result = await hass.config_entries.flow.async_configure(
            flow_id, {CONF_PORT: BY_ID, "advanced": {}}
        )
        assert result["type"] is expected
    assert result["reason"] == "already_configured"


async def test_no_ports_error_but_typed_path_accepted(
    hass: HomeAssistant, client, ports
) -> None:
    ports.return_value = {}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "serial"}
    )
    assert result["errors"] == {"base": "no_ports"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PORT: "/dev/ttyUSB7", "advanced": {}}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_PORT] == "/dev/ttyUSB7"


async def test_by_id_preferred(hass: HomeAssistant) -> None:
    class Device:
        device = "/dev/ttyUSB0"
        description = "FT232R USB UART"

    with (
        patch(
            "custom_components.sabik.config_flow.comports", return_value=[Device()]
        ),
        patch(
            "custom_components.sabik.config_flow.glob.glob",
            return_value=["/dev/serial/by-id/usb-FTDI_X", "/dev/serial/by-id/other"],
        ),
        patch(
            "custom_components.sabik.config_flow.os.path.realpath",
            side_effect=lambda p: "/dev/ttyUSB0" if p.endswith("usb-FTDI_X") else p,
        ),
    ):
        ports = await _REAL_LISTER(hass)
    assert ports == {
        "/dev/serial/by-id/usb-FTDI_X": "FT232R USB UART (/dev/serial/by-id/usb-FTDI_X)"
    }

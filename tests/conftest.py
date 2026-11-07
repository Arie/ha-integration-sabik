"""Shared test fixtures."""

from collections.abc import Awaitable, Callable
from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sabik.const import (
    CONF_BAUDRATE,
    CONF_PARITY,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_SLAVE,
    CONF_TRANSPORT,
    DOMAIN,
)

from .fake_client import FakeSabikClient


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Allow Home Assistant to load the custom integration under test."""


@pytest.fixture
def fake_client() -> FakeSabikClient:
    return FakeSabikClient()


@pytest.fixture
def setup_integration(
    hass: HomeAssistant, fake_client: FakeSabikClient
) -> Callable[[], Awaitable[MockConfigEntry]]:
    """Return a coroutine that sets up the entry; adjust fake_client first."""

    async def _setup() -> MockConfigEntry:
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Sabik",
            data={
                CONF_TRANSPORT: "serial",
                CONF_PORT: "/dev/serial/by-id/usb-FTDI_TEST-if00-port0",
                CONF_BAUDRATE: 19200,
                CONF_PARITY: "E",
                CONF_SLAVE: 1,
                CONF_SCAN_INTERVAL: 5,
            },
        )
        entry.add_to_hass(hass)
        with patch(
            "custom_components.sabik.modbus.create_client", return_value=fake_client
        ):
            await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()
        return entry

    return _setup

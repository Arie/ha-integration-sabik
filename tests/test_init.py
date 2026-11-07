"""Entry setup, device registration and unload."""

from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from custom_components.sabik.const import DOMAIN


async def test_integration_loads(hass: HomeAssistant) -> None:
    assert await async_setup_component(hass, DOMAIN, {})


async def test_setup_creates_device(hass: HomeAssistant, setup_integration) -> None:
    entry = await setup_integration()

    assert entry.state is ConfigEntryState.LOADED
    devices = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    assert len(devices) == 1
    assert devices[0].name == "Sabik"
    assert devices[0].manufacturer == "S&P"
    assert devices[0].model == "Sabik 350"


async def test_setup_retries_when_unit_unreachable(
    setup_integration, fake_client
) -> None:
    fake_client.fail = True
    entry = await setup_integration()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert fake_client.closed


async def test_unload_closes_client(
    hass: HomeAssistant, setup_integration, fake_client
) -> None:
    entry = await setup_integration()

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert fake_client.closed


async def test_client_closed_if_platform_setup_fails(
    setup_integration, fake_client
) -> None:
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
        side_effect=RuntimeError("boom"),
    ):
        entry = await setup_integration()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert fake_client.closed


async def test_failed_migration_check_does_not_break_setup(
    hass: HomeAssistant, setup_integration, fake_client, caplog
) -> None:
    with patch(
        "custom_components.sabik.async_check_migration",
        side_effect=RuntimeError("boom"),
    ):
        entry = await setup_integration()

    assert entry.state is ConfigEntryState.LOADED
    assert not fake_client.closed
    assert "Could not check for the Sabik MQTT bridge" in caplog.text

"""Entry setup, device registration and unload."""

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

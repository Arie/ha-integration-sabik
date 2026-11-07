"""Polling coordinator behavior."""

from datetime import timedelta

from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed


async def test_poll_decodes(setup_integration) -> None:
    entry = await setup_integration()

    assert entry.runtime_data.data.extract_air_temperature == 21.5


async def test_connection_loss_and_recovery(
    hass, setup_integration, fake_client
) -> None:
    entry = await setup_integration()
    coordinator = entry.runtime_data
    # Polling only runs while something listens; no platforms exist yet.
    unsub = coordinator.async_add_listener(lambda: None)

    fake_client.fail = True
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=6))
    await hass.async_block_till_done()
    assert coordinator.last_update_success is False

    fake_client.fail = False
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=12))
    await hass.async_block_till_done()
    assert coordinator.last_update_success is True
    unsub()

"""Tests for the Sabik buttons."""

from homeassistant.core import HomeAssistant


async def _press(hass: HomeAssistant, entity_id: str) -> None:
    await hass.services.async_call(
        "button", "press", {"entity_id": entity_id}, blocking=True
    )


async def test_sync_clock(
    hass: HomeAssistant, setup_integration, fake_client, freezer
) -> None:
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    freezer.move_to("2026-11-07 14:03:09+01:00")
    await setup_integration()

    async def forbidden(*args, **kwargs):
        raise AssertionError("multi-register write must never be used")

    # The unit never replies to FC16, which corrupts the next read.
    fake_client.async_write_registers = forbidden

    await _press(hass, "button.sabik_sync_clock")

    assert fake_client.writes == [
        ("hr", 48 + i, v) for i, v in enumerate([7, 11, 2026, 14, 3, 9])
    ]


async def test_reset_filter_alarm(
    hass: HomeAssistant, setup_integration, fake_client
) -> None:
    await setup_integration()

    await _press(hass, "button.sabik_reset_filter_alarm")

    assert fake_client.writes == [("coil", 0, True)]

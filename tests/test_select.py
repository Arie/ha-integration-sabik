"""Tests for the fan speed select."""

from homeassistant.core import HomeAssistant

ENTITY = "select.sabik_fan_speed"


async def _select(hass: HomeAssistant, option: str) -> None:
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": ENTITY, "option": option},
        blocking=True,
    )


async def test_select_high_writes_like_bridge(
    hass: HomeAssistant, setup_integration, fake_client
) -> None:
    await setup_integration()

    await _select(hass, "high")

    assert fake_client.writes == [("coil", 17, False), ("coil", 25, False), ("hr", 132, 2)]
    assert hass.states.get(ENTITY).state == "high"


async def test_select_auto_keeps_work_mode(
    hass: HomeAssistant, setup_integration, fake_client
) -> None:
    await setup_integration()

    await _select(hass, "auto")

    assert fake_client.writes == [("coil", 17, False), ("hr", 132, 3)]


async def test_unknown_air_volume_is_unknown(
    hass: HomeAssistant, setup_integration, fake_client
) -> None:
    fake_client.hr[132] = 9
    await setup_integration()

    assert hass.states.get(ENTITY).state == "unknown"


async def test_snooze_reads_as_unknown(
    hass: HomeAssistant, setup_integration, fake_client
) -> None:
    fake_client.hr[132] = 4
    await setup_integration()

    assert hass.states.get(ENTITY).state == "unknown"

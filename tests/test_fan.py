"""Tests for the main fan entity."""

from homeassistant.core import HomeAssistant

ENTITY = "fan.sabik"


async def _call(hass: HomeAssistant, service: str, **data) -> None:
    await hass.services.async_call(
        "fan", service, {"entity_id": ENTITY, **data}, blocking=True
    )


async def test_entity_id_is_fan_sabik(
    hass: HomeAssistant, setup_integration
) -> None:
    await setup_integration()

    assert hass.states.get(ENTITY) is not None


async def test_entity_id_is_fan_sabik_on_dutch_instance(
    hass: HomeAssistant, setup_integration
) -> None:
    hass.config.language = "nl"
    await setup_integration()

    assert hass.states.get(ENTITY) is not None


async def test_turn_off_snoozes(
    hass: HomeAssistant, setup_integration, fake_client
) -> None:
    await setup_integration()

    await _call(hass, "turn_off")

    assert fake_client.writes == [("coil", 17, True)]
    assert hass.states.get(ENTITY).state == "off"
    assert hass.states.get(ENTITY).attributes["preset_mode"] == "snooze"


async def test_turn_on_plain_unsnoozes(
    hass: HomeAssistant, setup_integration, fake_client
) -> None:
    fake_client.coil[17] = True
    await setup_integration()
    assert hass.states.get(ENTITY).state == "off"

    await _call(hass, "turn_on")

    assert fake_client.writes == [("coil", 17, False)]
    assert hass.states.get(ENTITY).state == "on"


async def test_turn_on_with_preset_low(
    hass: HomeAssistant, setup_integration, fake_client
) -> None:
    await setup_integration()

    await _call(hass, "turn_on", preset_mode="low")

    assert fake_client.writes == [("coil", 17, False), ("coil", 25, False), ("hr", 132, 0)]


async def test_set_preset_mode(
    hass: HomeAssistant, setup_integration, fake_client
) -> None:
    await setup_integration()

    await _call(hass, "set_preset_mode", preset_mode="auto")

    assert fake_client.writes == [("coil", 17, False), ("hr", 132, 3)]


async def test_preset_reflects_air_volume(
    hass: HomeAssistant, setup_integration, fake_client
) -> None:
    fake_client.hr[132] = 3
    await setup_integration()

    assert hass.states.get(ENTITY).attributes["preset_mode"] == "auto"


async def test_snooze_register_without_coil_has_no_preset(
    hass: HomeAssistant, setup_integration, fake_client
) -> None:
    fake_client.hr[132] = 4
    await setup_integration()

    assert hass.states.get(ENTITY).attributes["preset_mode"] is None

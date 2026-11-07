"""Tests for the Sabik switches and the write commands behind them."""

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError


async def _switch(hass: HomeAssistant, entity_id: str, on: bool) -> None:
    await hass.services.async_call(
        "switch",
        "turn_on" if on else "turn_off",
        {"entity_id": entity_id},
        blocking=True,
    )


async def test_boost_unsnoozes_first(
    hass: HomeAssistant, setup_integration, fake_client
) -> None:
    await setup_integration()

    await _switch(hass, "switch.sabik_boost", True)

    assert fake_client.writes == [("coil", 17, False), ("coil", 16, True)]
    assert hass.states.get("switch.sabik_boost").state == "on"


async def test_boost_off(hass: HomeAssistant, setup_integration, fake_client) -> None:
    fake_client.coil[16] = True
    await setup_integration()

    await _switch(hass, "switch.sabik_boost", False)

    assert fake_client.writes == [("coil", 16, False)]
    assert hass.states.get("switch.sabik_boost").state == "off"


async def test_bypass_blocked_by_outdoor_temp(
    hass: HomeAssistant, setup_integration, fake_client
) -> None:
    await setup_integration()  # outdoor 9.5, minimum 13.0

    with pytest.raises(ServiceValidationError) as err:
        await _switch(hass, "switch.sabik_manual_bypass", True)

    assert str(err.value) == (
        "Outdoor temperature 9.5 °C is below the bypass minimum of 13.0 °C"
    )
    assert fake_client.writes == []


async def test_bypass_blocked_by_extract_temp(
    hass: HomeAssistant, setup_integration, fake_client
) -> None:
    fake_client.ir[27] = 150
    fake_client.ir[25] = 215  # 21.5 < 23.0
    await setup_integration()

    with pytest.raises(ServiceValidationError) as err:
        await _switch(hass, "switch.sabik_manual_bypass", True)

    assert str(err.value) == (
        "Extract temperature 21.5 °C is below the bypass minimum of 23.0 °C"
    )
    assert fake_client.writes == []


async def test_bypass_difference_too_small(
    hass: HomeAssistant, setup_integration, fake_client
) -> None:
    fake_client.ir[27] = 215
    fake_client.ir[25] = 230  # difference 1.5 < 3.0
    await setup_integration()

    with pytest.raises(ServiceValidationError) as err:
        await _switch(hass, "switch.sabik_manual_bypass", True)

    assert str(err.value) == (
        "Temperature difference 1.5 °C is below the bypass minimum of 3.0 °C"
    )
    assert fake_client.writes == []


async def test_bypass_at_exact_thresholds_allowed(
    hass: HomeAssistant, setup_integration, fake_client
) -> None:
    fake_client.ir[27] = 130
    fake_client.ir[25] = 230
    fake_client.hr[67] = 100  # difference 10.0 equals the minimum
    await setup_integration()

    await _switch(hass, "switch.sabik_manual_bypass", True)

    assert fake_client.writes == [("coil", 7, True)]


async def test_bypass_off_skips_preconditions(
    hass: HomeAssistant, setup_integration, fake_client
) -> None:
    fake_client.coil[7] = True
    await setup_integration()  # outdoor far below minimum

    await _switch(hass, "switch.sabik_manual_bypass", False)

    assert fake_client.writes == [("coil", 7, False)]


async def test_summer_blocked_by_outdoor_temp(
    hass: HomeAssistant, setup_integration, fake_client
) -> None:
    await setup_integration()

    with pytest.raises(ServiceValidationError) as err:
        await _switch(hass, "switch.sabik_summer_mode", True)

    assert str(err.value) == (
        "Outdoor temperature 9.5 °C is below the summer mode minimum of 13.0 °C"
    )
    assert fake_client.writes == []


async def test_summer_allowed_at_minimum(
    hass: HomeAssistant, setup_integration, fake_client
) -> None:
    fake_client.ir[27] = 130
    await setup_integration()

    await _switch(hass, "switch.sabik_summer_mode", True)

    assert fake_client.writes == [("coil", 9, True)]


@pytest.mark.parametrize(
    ("entity_id", "coil"),
    [
        ("switch.sabik_allow_automatic_bypass", 8),
        ("switch.sabik_snooze", 17),
        ("switch.sabik_automatic_work_mode", 25),
    ],
)
@pytest.mark.parametrize("on", [True, False])
async def test_simple_coils(
    hass: HomeAssistant, setup_integration, fake_client, entity_id, coil, on
) -> None:
    await setup_integration()

    await _switch(hass, entity_id, on)

    assert fake_client.writes == [("coil", coil, on)]
    assert hass.states.get(entity_id).state == ("on" if on else "off")


async def test_write_failure_raises(
    hass: HomeAssistant, setup_integration, fake_client
) -> None:
    await setup_integration()
    fake_client.fail = True

    with pytest.raises(HomeAssistantError) as err:
        await _switch(hass, "switch.sabik_snooze", True)

    assert str(err.value) == "Could not reach the Sabik unit"

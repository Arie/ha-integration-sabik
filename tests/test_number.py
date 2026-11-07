"""Tests for the Sabik bypass threshold numbers."""

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError


async def _set(hass: HomeAssistant, entity_id: str, value: float) -> None:
    await hass.services.async_call(
        "number", "set_value", {"entity_id": entity_id, "value": value}, blocking=True
    )


@pytest.mark.parametrize(("value", "raw"), [(3.0, 30), (6.0, 60)])
async def test_difference_accepts_bounds(
    hass: HomeAssistant, setup_integration, fake_client, value, raw
) -> None:
    await setup_integration()

    await _set(hass, "number.sabik_min_temperature_difference_for_bypass", value)

    assert fake_client.writes == [("hr", 67, raw)]


async def test_out_of_range_rejected(
    hass: HomeAssistant, setup_integration, fake_client
) -> None:
    await setup_integration()

    with pytest.raises(ServiceValidationError):
        await _set(hass, "number.sabik_min_temperature_difference_for_bypass", 6.1)

    assert fake_client.writes == []


async def test_outdoor_threshold_write(
    hass: HomeAssistant, setup_integration, fake_client
) -> None:
    await setup_integration()

    await _set(hass, "number.sabik_min_outdoor_temperature_for_bypass", 13.5)

    assert fake_client.writes == [("hr", 63, 135)]
    assert float(hass.states.get("number.sabik_min_outdoor_temperature_for_bypass").state) == 13.5


async def test_extract_threshold_write(
    hass: HomeAssistant, setup_integration, fake_client
) -> None:
    await setup_integration()

    await _set(hass, "number.sabik_min_extract_temperature_for_bypass", 24.2)

    assert fake_client.writes == [("hr", 65, 242)]


async def test_bypass_timer(
    hass: HomeAssistant, setup_integration, fake_client
) -> None:
    await setup_integration()

    await _set(hass, "number.sabik_manual_bypass_timer", 4)

    assert fake_client.writes == [("hr", 56, 4)]

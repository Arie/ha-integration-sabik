"""Tests for the Sabik binary sensors."""

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_registry import RegistryEntryDisabler

OLD_BINARY_SENSOR_IDS = [
    "binary_sensor.sabik_filter_alarm",
    "binary_sensor.sabik_extract_fan_alarm",
    "binary_sensor.sabik_supply_fan_alarm",
    "binary_sensor.sabik_summer_mode",
    "binary_sensor.sabik_boost_status",
]


@pytest.mark.parametrize("entity_id", OLD_BINARY_SENSOR_IDS)
async def test_entity_ids_match_bridge(
    hass: HomeAssistant, setup_integration, entity_id: str
) -> None:
    await setup_integration()

    assert hass.states.get(entity_id) is not None


async def test_boost_status_true_state(
    hass: HomeAssistant, setup_integration, fake_client
) -> None:
    fake_client.di[29] = False  # register doc: 0 = boost active
    await setup_integration()

    assert hass.states.get("binary_sensor.sabik_boost_status").state == "on"


async def test_alarm_is_problem_class(
    hass: HomeAssistant, setup_integration, fake_client
) -> None:
    fake_client.di[1] = True
    await setup_integration()

    state = hass.states.get("binary_sensor.sabik_filter_alarm")
    assert state.state == "on"
    assert state.attributes["device_class"] == "problem"


async def test_fault_diagnostics_disabled_by_default(
    hass: HomeAssistant, setup_integration
) -> None:
    await setup_integration()

    registry = er.async_get(hass)
    for key in (
        "active_alarms",
        "extract_air_sensor_fault",
        "exhaust_air_sensor_fault",
        "outdoor_air_sensor_fault",
        "supply_air_sensor_fault",
    ):
        reg = registry.async_get(f"binary_sensor.sabik_{key}")
        assert reg is not None, key
        assert reg.disabled_by is RegistryEntryDisabler.INTEGRATION

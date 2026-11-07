"""Tests for the Sabik sensors."""

from datetime import timedelta
from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_registry import RegistryEntryDisabler
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

OLD_SENSOR_IDS = [
    "sensor.sabik_extract_air_temperature",
    "sensor.sabik_exhaust_air_temperature",
    "sensor.sabik_outdoor_air_temperature",
    "sensor.sabik_supply_air_temperature",
    "sensor.sabik_rh_extract_air",
    "sensor.sabik_rh_exhaust_air",
    "sensor.sabik_rh_outdoor_air",
    "sensor.sabik_rh_supply_air",
    "sensor.sabik_voltage_extract_motor",
    "sensor.sabik_voltage_supply_motor",
    "sensor.sabik_rpm_extract_motor",
    "sensor.sabik_rpm_supply_motor",
    "sensor.sabik_bypass_valve_position",
    "sensor.sabik_current_work_mode",
    "sensor.sabik_defrost_status",
    "sensor.sabik_selected_air_volume",
    "sensor.sabik_min_outdoor_temperature_for_bypass",
    "sensor.sabik_min_extract_temperature_for_bypass",
    "sensor.sabik_min_temperature_difference_for_bypass",
]


@pytest.mark.parametrize("entity_id", OLD_SENSOR_IDS)
async def test_entity_ids_match_bridge(
    hass: HomeAssistant, setup_integration, entity_id: str
) -> None:
    await setup_integration()

    assert hass.states.get(entity_id) is not None


async def test_entity_ids_english_on_dutch_instance(
    hass: HomeAssistant, setup_integration
) -> None:
    hass.config.language = "nl"
    await setup_integration()

    state = hass.states.get("sensor.sabik_extract_air_temperature")
    assert state is not None
    assert state.attributes["friendly_name"] == "Sabik Afvoerluchttemperatuur"
    assert hass.states.get("binary_sensor.sabik_filter_alarm") is not None


async def test_states_and_units(
    hass: HomeAssistant, setup_integration, fake_client
) -> None:
    fake_client.ir[27] = 65531
    fake_client.ir[59] = 45
    fake_client.ir[90] = 12
    await setup_integration()

    state = hass.states.get("sensor.sabik_extract_air_temperature")
    assert state.state == "21.5"
    assert state.attributes["unit_of_measurement"] == "°C"
    assert hass.states.get("sensor.sabik_outdoor_air_temperature").state == "-0.5"
    rpm = hass.states.get("sensor.sabik_rpm_extract_motor")
    assert rpm.state == "1200"
    assert rpm.attributes["unit_of_measurement"] == "RPM"
    volt = hass.states.get("sensor.sabik_voltage_extract_motor")
    assert volt.state == "4.5"
    assert volt.attributes["unit_of_measurement"] == "V"
    assert hass.states.get("sensor.sabik_current_work_mode").state == "week_program_4"
    assert hass.states.get("sensor.sabik_selected_air_volume").state == "1"
    assert "unit_of_measurement" not in hass.states.get(
        "sensor.sabik_selected_air_volume"
    ).attributes


async def test_diagnostics_disabled_by_default(
    hass: HomeAssistant, setup_integration
) -> None:
    entry = await setup_integration()

    registry = er.async_get(hass)
    for key in ("communication_error", "unit_clock"):
        reg = registry.async_get(f"sensor.sabik_{key}")
        assert reg is not None, key
        assert reg.config_entry_id == entry.entry_id
        assert reg.disabled_by is RegistryEntryDisabler.INTEGRATION


async def test_unit_clock_is_local_time(
    hass: HomeAssistant, setup_integration, fake_client
) -> None:
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    entry = await setup_integration()
    registry = er.async_get(hass)
    reg = registry.async_get("sensor.sabik_unit_clock")
    registry.async_update_entity(reg.entity_id, disabled_by=None)
    with patch("custom_components.sabik.modbus.create_client", return_value=fake_client):
        await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    # Fake clock is 2026-11-07 12:30:00 local (CET, UTC+1).
    assert hass.states.get("sensor.sabik_unit_clock").state == "2026-11-07T11:30:00+00:00"


async def test_unavailable_on_connection_loss(
    hass: HomeAssistant, setup_integration, fake_client
) -> None:
    await setup_integration()
    fake_client.fail = True
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=6))
    await hass.async_block_till_done()

    assert hass.states.get("sensor.sabik_extract_air_temperature").state == "unavailable"

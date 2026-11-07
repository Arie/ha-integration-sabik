"""Migration from the Ruby/MQTT bridge: detection and registry rewrite."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import json
from unittest.mock import patch

import pytest
from homeassistant.const import EVENT_COMPONENT_LOADED
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_mqtt_message,
)
from pytest_homeassistant_custom_component.typing import MqttMockHAClient

from custom_components.sabik import migration
from custom_components.sabik.const import DOMAIN
from custom_components.sabik.migration import (
    ISSUE_ID,
    async_check_migration,
    async_migrate,
)

# (old entity_id, old MQTT unique_id), straight from the bridge.
OLD_ENTITIES: list[tuple[str, str]] = [
    ("sensor.sabik_extract_air_temperature", "sabik_350_extract_air_temperature"),
    ("sensor.sabik_exhaust_air_temperature", "sabik_350_exhaust_air_temperature"),
    ("sensor.sabik_outdoor_air_temperature", "sabik_350_outdoor_air_temperature"),
    ("sensor.sabik_supply_air_temperature", "sabik_350_supply_air_temperature"),
    ("sensor.sabik_rh_extract_air", "sabik_350_rh_extract_air"),
    ("sensor.sabik_rh_exhaust_air", "sabik_350_rh_exhaust_air"),
    ("sensor.sabik_rh_outdoor_air", "sabik_350_rh_outdoor_air"),
    ("sensor.sabik_rh_supply_air", "sabik_350_rh_supply_air"),
    ("sensor.sabik_voltage_extract_motor", "sabik_350_control_voltage_extract_motor"),
    ("sensor.sabik_voltage_supply_motor", "sabik_350_control_voltage_supply_motor"),
    ("sensor.sabik_rpm_extract_motor", "sabik_350_rpm_extract_motor"),
    ("sensor.sabik_rpm_supply_motor", "sabik_350_rpm_supply_motor"),
    ("sensor.sabik_bypass_valve_position", "sabik_350_bypass_valve_position"),
    ("sensor.sabik_current_work_mode", "sabik_350_current_work_mode"),
    ("sensor.sabik_defrost_status", "sabik_350_defrost_status"),
    ("sensor.sabik_selected_air_volume", "sabik_350_selected_air_volume"),
    ("sensor.sabik_min_outdoor_temperature_for_bypass", "sabik_350_min_oda_for_bypass"),
    ("sensor.sabik_min_extract_temperature_for_bypass", "sabik_350_min_eta_for_bypass"),
    (
        "sensor.sabik_min_temperature_difference_for_bypass",
        "sabik_350_min_eta_oda_for_bypass",
    ),
    ("binary_sensor.sabik_filter_alarm", "sabik_350_filter_alarm"),
    ("binary_sensor.sabik_extract_fan_alarm", "sabik_350_extract_air_fan_status"),
    ("binary_sensor.sabik_supply_fan_alarm", "sabik_350_supply_air_fan_status"),
    ("binary_sensor.sabik_summer_mode", "sabik_350_summer_mode_status"),
    ("binary_sensor.sabik_boost_status", "sabik_350_boost_status"),
]
CLIMATE_ID = "climate.sabik_ventilation"

# The mocked MQTT client leaves its periodic timers scheduled at teardown.
pytestmark = pytest.mark.parametrize("expected_lingering_timers", [True])

SetupFn = Callable[[], Awaitable[MockConfigEntry]]


def seed_old_entities(
    hass: HomeAssistant,
    mqtt_entry: MockConfigEntry | None,
    overrides: dict[str, str] | None = None,
) -> None:
    """Register the bridge's entities and devices as MQTT discovery left them."""
    overrides = overrides or {}
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    entry_id = mqtt_entry.entry_id if mqtt_entry else None
    sabik_dev = ventilation_dev = None
    if entry_id:
        sabik_dev = dev_reg.async_get_or_create(
            config_entry_id=entry_id, identifiers={("mqtt", "sabik")}, name="sabik"
        ).id
        ventilation_dev = dev_reg.async_get_or_create(
            config_entry_id=entry_id,
            identifiers={("mqtt", "sabik_ventilation")},
            name="Sabik Ventilation",
        ).id
    for entity_id, unique_id in OLD_ENTITIES:
        domain, object_id = entity_id.split(".")
        object_id = overrides.get(unique_id, object_id)
        created = ent_reg.async_get_or_create(
            domain,
            "mqtt",
            unique_id,
            suggested_object_id=object_id,
            config_entry=mqtt_entry,
            device_id=sabik_dev,
        )
        assert created.entity_id == f"{domain}.{object_id}"
    ent_reg.async_get_or_create(
        "climate",
        "mqtt",
        "sabik_ventilation",
        suggested_object_id="sabik_ventilation",
        config_entry=mqtt_entry,
        device_id=ventilation_dev,
    )


def issue(hass: HomeAssistant) -> ir.IssueEntry | None:
    return ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_ID)


async def test_no_issue_without_mqtt(
    hass: HomeAssistant, setup_integration: SetupFn
) -> None:
    seed_old_entities(hass, None)
    await setup_integration()

    assert issue(hass) is None


async def test_issue_raised(
    hass: HomeAssistant, mqtt_entry: MockConfigEntry, setup_integration: SetupFn
) -> None:
    seed_old_entities(hass, mqtt_entry)
    entry = await setup_integration()

    found = issue(hass)
    assert found is not None
    assert found.is_fixable
    assert not found.is_persistent
    assert found.severity is ir.IssueSeverity.WARNING
    assert found.data == {"entry_id": entry.entry_id}


async def test_no_issue_with_mqtt_but_no_old_entities(
    hass: HomeAssistant, mqtt_entry: MockConfigEntry, setup_integration: SetupFn
) -> None:
    await setup_integration()

    assert issue(hass) is None


async def test_issue_raised_when_mqtt_not_loaded(
    hass: HomeAssistant, setup_integration: SetupFn
) -> None:
    mqtt_entry = MockConfigEntry(domain="mqtt")
    mqtt_entry.add_to_hass(hass)
    seed_old_entities(hass, mqtt_entry)
    await setup_integration()

    assert issue(hass) is not None


async def test_check_runs_again_when_mqtt_loads(
    hass: HomeAssistant, setup_integration: SetupFn
) -> None:
    seed_old_entities(hass, None)
    entry = await setup_integration()
    assert issue(hass) is None
    MockConfigEntry(domain="mqtt").add_to_hass(hass)

    hass.bus.async_fire(EVENT_COMPONENT_LOADED, {"component": "light"})
    await hass.async_block_till_done()
    assert issue(hass) is None

    hass.bus.async_fire(EVENT_COMPONENT_LOADED, {"component": "mqtt"})
    await hass.async_block_till_done()
    assert issue(hass) is not None

    ir.async_delete_issue(hass, DOMAIN, ISSUE_ID)
    assert await hass.config_entries.async_unload(entry.entry_id)
    hass.bus.async_fire(EVENT_COMPONENT_LOADED, {"component": "mqtt"})
    await hass.async_block_till_done()
    assert issue(hass) is None


async def test_issue_deleted_when_nothing_left(
    hass: HomeAssistant, mqtt_entry: MockConfigEntry, setup_integration: SetupFn
) -> None:
    seed_old_entities(hass, mqtt_entry)
    entry = await setup_integration()
    assert issue(hass) is not None

    ent_reg = er.async_get(hass)
    for old in migration.find_old_entities(hass):
        ent_reg.async_remove(old.entity_id)
    await async_check_migration(hass, entry)

    assert issue(hass) is None


async def test_new_entities_wait_on_2_before_migration(
    hass: HomeAssistant, mqtt_entry: MockConfigEntry, setup_integration: SetupFn
) -> None:
    seed_old_entities(hass, mqtt_entry)
    entry = await setup_integration()
    assert hass.states.get("sensor.sabik_extract_air_temperature_2") is not None

    await async_migrate(hass, entry)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.sabik_extract_air_temperature_2") is None
    assert hass.states.get("sensor.sabik_extract_air_temperature") is not None


async def test_migrate_renames_to_old_ids(
    hass: HomeAssistant, mqtt_entry: MockConfigEntry, setup_integration: SetupFn
) -> None:
    seed_old_entities(hass, mqtt_entry)
    entry = await setup_integration()

    result = await async_migrate(hass, entry)
    await hass.async_block_till_done()

    ent_reg = er.async_get(hass)
    for entity_id, _ in OLD_ENTITIES:
        reg = ent_reg.async_get(entity_id)
        assert reg is not None, entity_id
        assert reg.platform == DOMAIN
        key = entity_id.split(".")[1].removeprefix("sabik_")
        assert reg.unique_id == f"{entry.entry_id}_{key}"
        assert hass.states.get(entity_id) is not None
    assert not [
        e.entity_id
        for e in er.async_entries_for_config_entry(ent_reg, entry.entry_id)
        if e.entity_id.endswith("_2")
    ]
    assert ent_reg.async_get(CLIMATE_ID) is None
    assert not [e for e in ent_reg.entities.values() if e.platform == "mqtt"]
    assert len(result.renamed) == 24
    assert len(result.removed) == 25
    assert CLIMATE_ID in result.removed
    assert result.skipped == []
    assert result.discovery_cleared


async def test_migrate_removes_only_bridge_devices(
    hass: HomeAssistant, mqtt_entry: MockConfigEntry, setup_integration: SetupFn
) -> None:
    dev_reg = dr.async_get(hass)
    other = dev_reg.async_get_or_create(
        config_entry_id=mqtt_entry.entry_id, identifiers={("mqtt", "something_else")}
    )
    seed_old_entities(hass, mqtt_entry)
    entry = await setup_integration()

    await async_migrate(hass, entry)

    assert not dev_reg.async_get_devices(identifiers={("mqtt", "sabik")})
    assert not dev_reg.async_get_devices(identifiers={("mqtt", "sabik_ventilation")})
    assert dev_reg.async_get(other.id) is not None
    assert dev_reg.async_get_devices(identifiers={(DOMAIN, entry.entry_id)})


async def test_migrate_keeps_bridge_device_with_other_entities(
    hass: HomeAssistant, mqtt_entry: MockConfigEntry, setup_integration: SetupFn
) -> None:
    seed_old_entities(hass, mqtt_entry)
    dev_reg = dr.async_get(hass)
    [device] = dev_reg.async_get_devices(identifiers={("mqtt", "sabik")})
    er.async_get(hass).async_get_or_create(
        "sensor", "mqtt", "user_added", config_entry=mqtt_entry, device_id=device.id
    )
    entry = await setup_integration()

    await async_migrate(hass, entry)

    assert dev_reg.async_get(device.id) is not None


async def test_migrate_uses_actual_old_entity_id(
    hass: HomeAssistant, mqtt_entry: MockConfigEntry, setup_integration: SetupFn
) -> None:
    seed_old_entities(
        hass,
        mqtt_entry,
        overrides={"sabik_350_extract_air_temperature": "living_room_extract"},
    )
    entry = await setup_integration()

    result = await async_migrate(hass, entry)
    await hass.async_block_till_done()

    reg = er.async_get(hass).async_get("sensor.living_room_extract")
    assert reg is not None
    assert reg.unique_id == f"{entry.entry_id}_extract_air_temperature"
    assert ("sensor.sabik_extract_air_temperature", "sensor.living_room_extract") in (
        result.renamed
    )
    assert hass.states.get("sensor.living_room_extract") is not None


async def test_migrate_clears_discovery(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    mqtt_entry: MockConfigEntry,
    setup_integration: SetupFn,
) -> None:
    seed_old_entities(hass, mqtt_entry)
    entry = await setup_integration()
    mqtt_mock.async_publish.reset_mock()

    await async_migrate(hass, entry)

    published = [c.args[:4] for c in mqtt_mock.async_publish.call_args_list]
    assert (
        "homeassistant/sensor/sabik/sabik_control_voltage_extract_motor/config",
        "",
        0,
        True,
    ) in published
    assert (
        "homeassistant/binary_sensor/sabik/sabik_boost_status/config",
        "",
        0,
        True,
    ) in (published)
    assert ("homeassistant/climate/sabik/config", "", 0, True) in published
    assert len(published) == 25
    assert len(set(published)) == 25


async def test_migrate_without_mqtt_loaded(
    hass: HomeAssistant, setup_integration: SetupFn
) -> None:
    mqtt_entry = MockConfigEntry(domain="mqtt")
    mqtt_entry.add_to_hass(hass)
    seed_old_entities(hass, mqtt_entry)
    entry = await setup_integration()

    result = await async_migrate(hass, entry)
    await hass.async_block_till_done()

    assert not result.discovery_cleared
    assert len(result.renamed) == 24
    assert er.async_get(hass).async_get("sensor.sabik_rh_supply_air").platform == DOMAIN
    assert er.async_get(hass).async_get(CLIMATE_ID) is None


async def test_migrate_twice_is_harmless(
    hass: HomeAssistant, mqtt_entry: MockConfigEntry, setup_integration: SetupFn
) -> None:
    seed_old_entities(hass, mqtt_entry)
    entry = await setup_integration()
    await async_migrate(hass, entry)
    await hass.async_block_till_done()

    again = await async_migrate(hass, entry)
    await hass.async_block_till_done()

    assert again.renamed == []
    assert again.removed == []
    assert again.skipped == []
    assert hass.states.get("sensor.sabik_extract_air_temperature") is not None


async def test_migrate_skips_taken_target(
    hass: HomeAssistant, mqtt_entry: MockConfigEntry, setup_integration: SetupFn
) -> None:
    seed_old_entities(hass, mqtt_entry)
    entry = await setup_integration()
    # A foreign state keeps the old ID busy after the old entry is gone.
    hass.states.async_set("sensor.sabik_rpm_extract_motor", "1200")

    with patch.object(migration, "REMOVAL_TIMEOUT", 0.05):
        result = await async_migrate(hass, entry)
    await hass.async_block_till_done()

    assert result.skipped == [
        ("sensor.sabik_rpm_extract_motor_2", "sensor.sabik_rpm_extract_motor")
    ]
    assert len(result.renamed) == 23
    reg = er.async_get(hass).async_get("sensor.sabik_rpm_extract_motor_2")
    assert reg is not None
    assert reg.platform == DOMAIN


async def test_rediscovered_old_entity_is_not_a_rename_target(
    hass: HomeAssistant, mqtt_entry: MockConfigEntry, setup_integration: SetupFn
) -> None:
    seed_old_entities(hass, mqtt_entry)
    entry = await setup_integration()
    await async_migrate(hass, entry)
    await hass.async_block_till_done()

    # Retained discovery that was never cleared brings an old entity back.
    back = er.async_get(hass).async_get_or_create(
        "sensor",
        "mqtt",
        "sabik_350_extract_air_temperature",
        suggested_object_id="sabik_extract_air_temperature",
        config_entry=mqtt_entry,
    )
    assert back.entity_id == "sensor.sabik_extract_air_temperature_2"

    result = await async_migrate(hass, entry)
    await hass.async_block_till_done()

    reg = er.async_get(hass).async_get("sensor.sabik_extract_air_temperature")
    assert reg is not None
    assert reg.platform == DOMAIN
    assert result.removed == ["sensor.sabik_extract_air_temperature_2"]
    assert result.renamed == []


async def test_migrate_live_mqtt_entities(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    mqtt_entry: MockConfigEntry,
    setup_integration: SetupFn,
) -> None:
    """Old entities that MQTT really discovered, with state, as on a live install."""
    device = {"identifiers": ["sabik"], "name": "sabik"}
    for key, name, unique_id in (
        (
            "sabik_extract_air_temperature",
            "Extract Air Temperature",
            "sabik_350_extract_air_temperature",
        ),
        ("sabik_boost_status", "Boost Status", "sabik_350_boost_status"),
    ):
        component = "binary_sensor" if key == "sabik_boost_status" else "sensor"
        async_fire_mqtt_message(
            hass,
            f"homeassistant/{component}/sabik/{key}/config",
            json.dumps(
                {
                    "name": name,
                    "state_topic": "homeassistant/sabik/sabikstatus",
                    "unique_id": unique_id,
                    "device": device,
                }
            ),
        )
    await hass.async_block_till_done()
    assert (
        er.async_get(hass).async_get("sensor.sabik_extract_air_temperature").platform
        == "mqtt"
    )
    assert hass.states.get("binary_sensor.sabik_boost_status") is not None
    entry = await setup_integration()
    assert issue(hass) is not None

    async def slow_publish(*_args, **_kwargs) -> None:
        await asyncio.sleep(0.01)

    # A real broker round trip delays MQTT's own removal of each entity.
    mqtt_mock.async_publish.side_effect = slow_publish
    result = await async_migrate(hass, entry)
    await hass.async_block_till_done()

    assert result.skipped == []
    assert sorted(result.renamed) == [
        ("binary_sensor.sabik_boost_status_2", "binary_sensor.sabik_boost_status"),
        (
            "sensor.sabik_extract_air_temperature_2",
            "sensor.sabik_extract_air_temperature",
        ),
    ]
    for entity_id in (
        "sensor.sabik_extract_air_temperature",
        "binary_sensor.sabik_boost_status",
    ):
        assert er.async_get(hass).async_get(entity_id).platform == DOMAIN
        assert hass.states.get(entity_id) is not None
    assert hass.states.get("sensor.sabik_extract_air_temperature_2") is None
    assert not dr.async_get(hass).async_get_devices(identifiers={("mqtt", "sabik")})

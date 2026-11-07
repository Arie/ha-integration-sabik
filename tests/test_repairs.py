"""The fix flow for the MQTT bridge migration."""

from __future__ import annotations

from datetime import timedelta

import pytest
from homeassistant.components.repairs import repairs_flow_manager
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_mqtt_message,
)

from custom_components.sabik.const import DOMAIN
from custom_components.sabik.migration import (
    BRIDGE_STATUS_TOPIC,
    DATA_MONITORS,
    ISSUE_ID,
)

from .test_migration import seed_old_entities

# The mocked MQTT client leaves its periodic timers scheduled at teardown.
pytestmark = pytest.mark.parametrize("expected_lingering_timers", [True])


@pytest.fixture(autouse=True)
async def setup_repairs(hass: HomeAssistant) -> None:
    assert await async_setup_component(hass, "repairs", {})


async def start_flow(hass: HomeAssistant) -> dict:
    manager = repairs_flow_manager(hass)
    assert manager is not None
    return await manager.async_init(DOMAIN, context={"issue_id": ISSUE_ID})


async def submit(hass: HomeAssistant, result: dict) -> dict:
    return await repairs_flow_manager(hass).async_configure(result["flow_id"], {})


async def test_fix_flow_blocks_while_bridge_running(
    hass: HomeAssistant, mqtt_entry: MockConfigEntry, setup_integration, freezer
) -> None:
    seed_old_entities(hass, mqtt_entry)
    await setup_integration()

    async_fire_mqtt_message(hass, BRIDGE_STATUS_TOPIC, "{}")
    await hass.async_block_till_done()

    result = await start_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert not result["errors"]

    result = await submit(hass, result)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["errors"] == {"base": "bridge_running"}

    freezer.tick(timedelta(seconds=31))
    result = await submit(hass, result)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"


async def test_fix_flow_end_to_end(
    hass: HomeAssistant, mqtt_entry: MockConfigEntry, setup_integration
) -> None:
    seed_old_entities(hass, mqtt_entry)
    entry = await setup_integration()
    assert entry.entry_id in hass.data[DATA_MONITORS]

    result = await start_flow(hass)
    assert result["step_id"] == "init"
    result = await submit(hass, result)
    assert result["step_id"] == "confirm"
    # Nothing changes before the user confirms.
    assert (
        er.async_get(hass).async_get("binary_sensor.sabik_filter_alarm").platform
        == "mqtt"
    )

    result = await submit(hass, result)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "done"
    assert result["description_placeholders"]["renamed"] == "24"
    assert result["description_placeholders"]["removed"] == "25"
    assert result["description_placeholders"]["skipped"] == "-"
    assert not result["errors"]

    result = await submit(hass, result)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    assert ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_ID) is None
    assert entry.entry_id not in hass.data[DATA_MONITORS]
    assert (
        er.async_get(hass).async_get("binary_sensor.sabik_filter_alarm").platform
        == DOMAIN
    )


async def test_fix_flow_without_mqtt_loaded(
    hass: HomeAssistant, setup_integration
) -> None:
    mqtt_entry = MockConfigEntry(domain="mqtt")
    mqtt_entry.add_to_hass(hass)
    seed_old_entities(hass, mqtt_entry)
    entry = await setup_integration()
    assert entry.entry_id not in hass.data.get(DATA_MONITORS, {})

    result = await start_flow(hass)
    result = await submit(hass, result)
    assert result["step_id"] == "confirm"
    result = await submit(hass, result)

    assert result["step_id"] == "done"
    assert result["errors"] == {"base": "discovery_not_cleared"}
    assert result["description_placeholders"]["renamed"] == "24"


async def test_monitor_stops_on_unload(
    hass: HomeAssistant, mqtt_entry: MockConfigEntry, setup_integration
) -> None:
    seed_old_entities(hass, mqtt_entry)
    entry = await setup_integration()
    assert entry.entry_id in hass.data[DATA_MONITORS]

    assert await hass.config_entries.async_unload(entry.entry_id)

    assert entry.entry_id not in hass.data[DATA_MONITORS]


async def test_removing_entry_deletes_issue(
    hass: HomeAssistant, mqtt_entry: MockConfigEntry, setup_integration
) -> None:
    seed_old_entities(hass, mqtt_entry)
    entry = await setup_integration()
    assert ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_ID) is not None

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    assert ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_ID) is None
    assert entry.entry_id not in hass.data[DATA_MONITORS]


async def test_removing_other_entry_keeps_issue(
    hass: HomeAssistant, mqtt_entry: MockConfigEntry, setup_integration
) -> None:
    seed_old_entities(hass, mqtt_entry)
    await setup_integration()
    other = MockConfigEntry(domain=DOMAIN, title="Sabik 2", data={})
    other.add_to_hass(hass)

    await hass.config_entries.async_remove(other.entry_id)
    await hass.async_block_till_done()

    assert ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_ID) is not None


async def test_monitor_survives_mqtt_reload(
    hass: HomeAssistant, mqtt_entry: MockConfigEntry, setup_integration, freezer
) -> None:
    seed_old_entities(hass, mqtt_entry)
    entry = await setup_integration()

    assert await hass.config_entries.async_reload(mqtt_entry.entry_id)
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, BRIDGE_STATUS_TOPIC, "{}")
    await hass.async_block_till_done()

    assert hass.data[DATA_MONITORS][entry.entry_id].bridge_running
    result = await start_flow(hass)
    result = await submit(hass, result)
    assert result["errors"] == {"base": "bridge_running"}

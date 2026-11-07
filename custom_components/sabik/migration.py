"""One-click migration from the Ruby/MQTT bridge."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    callback,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util import dt as dt_util
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

MQTT_DOMAIN = "mqtt"
ISSUE_ID = "migrate_mqtt_bridge"
BRIDGE_STATUS_TOPIC = "homeassistant/sabik/sabikstatus"
BRIDGE_ACTIVE_WINDOW = timedelta(seconds=30)
# How long to wait for removed MQTT entities to drop their state before renaming.
REMOVAL_TIMEOUT = 10.0

# Old MQTT unique_id -> (domain, new key). None: removed without a successor.
OLD_UNIQUE_IDS: dict[str, tuple[str, str] | None] = {
    "sabik_350_extract_air_temperature": ("sensor", "extract_air_temperature"),
    "sabik_350_exhaust_air_temperature": ("sensor", "exhaust_air_temperature"),
    "sabik_350_outdoor_air_temperature": ("sensor", "outdoor_air_temperature"),
    "sabik_350_supply_air_temperature": ("sensor", "supply_air_temperature"),
    "sabik_350_rh_extract_air": ("sensor", "rh_extract_air"),
    "sabik_350_rh_exhaust_air": ("sensor", "rh_exhaust_air"),
    "sabik_350_rh_outdoor_air": ("sensor", "rh_outdoor_air"),
    "sabik_350_rh_supply_air": ("sensor", "rh_supply_air"),
    "sabik_350_control_voltage_extract_motor": ("sensor", "voltage_extract_motor"),
    "sabik_350_control_voltage_supply_motor": ("sensor", "voltage_supply_motor"),
    "sabik_350_rpm_extract_motor": ("sensor", "rpm_extract_motor"),
    "sabik_350_rpm_supply_motor": ("sensor", "rpm_supply_motor"),
    "sabik_350_bypass_valve_position": ("sensor", "bypass_valve_position"),
    "sabik_350_current_work_mode": ("sensor", "current_work_mode"),
    "sabik_350_defrost_status": ("sensor", "defrost_status"),
    "sabik_350_selected_air_volume": ("sensor", "selected_air_volume"),
    "sabik_350_min_oda_for_bypass": ("sensor", "min_outdoor_temperature_for_bypass"),
    "sabik_350_min_eta_for_bypass": ("sensor", "min_extract_temperature_for_bypass"),
    "sabik_350_min_eta_oda_for_bypass": (
        "sensor",
        "min_temperature_difference_for_bypass",
    ),
    "sabik_350_filter_alarm": ("binary_sensor", "filter_alarm"),
    "sabik_350_extract_air_fan_status": ("binary_sensor", "extract_fan_alarm"),
    "sabik_350_supply_air_fan_status": ("binary_sensor", "supply_fan_alarm"),
    "sabik_350_summer_mode_status": ("binary_sensor", "summer_mode"),
    "sabik_350_boost_status": ("binary_sensor", "boost_status"),
    "sabik_ventilation": None,
}

_OLD_BINARY_SENSOR_KEYS = (
    "sabik_filter_alarm",
    "sabik_extract_fan_alarm",
    "sabik_supply_fan_alarm",
    "sabik_summer_mode",
    "sabik_boost_status",
)
_OLD_SENSOR_KEYS = (
    "sabik_defrost_status",
    "sabik_selected_air_volume",
    "sabik_current_work_mode",
    "sabik_bypass_valve_position",
    "sabik_extract_air_temperature",
    "sabik_supply_air_temperature",
    "sabik_exhaust_air_temperature",
    "sabik_outdoor_air_temperature",
    "sabik_min_oda_for_bypass",
    "sabik_min_eta_for_bypass",
    "sabik_min_eta_oda_for_bypass",
    "sabik_rpm_extract_motor",
    "sabik_rpm_supply_motor",
    "sabik_control_voltage_extract_motor",
    "sabik_control_voltage_supply_motor",
    "sabik_rh_extract_air",
    "sabik_rh_exhaust_air",
    "sabik_rh_outdoor_air",
    "sabik_rh_supply_air",
)
OLD_DISCOVERY_TOPICS: tuple[str, ...] = (
    *(
        f"homeassistant/binary_sensor/sabik/{key}/config"
        for key in _OLD_BINARY_SENSOR_KEYS
    ),
    *(f"homeassistant/sensor/sabik/{key}/config" for key in _OLD_SENSOR_KEYS),
    "homeassistant/climate/sabik/config",
)

# The MQTT integration stores discovery device identifiers as ("mqtt", <id>).
OLD_DEVICE_IDENTIFIERS = frozenset(
    {(MQTT_DOMAIN, "sabik"), (MQTT_DOMAIN, "sabik_ventilation")}
)


@dataclass
class MigrationResult:
    """What a migration run changed."""

    renamed: list[tuple[str, str]] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)
    discovery_cleared: bool = False


class BridgeActivityMonitor:
    """Remember when the bridge last published its status."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass
        self._unsubscribe: CALLBACK_TYPE | None = None
        self.last_seen: datetime | None = None

    async def async_start(self) -> None:
        from homeassistant.components import mqtt  # noqa: PLC0415

        self._unsubscribe = await mqtt.async_subscribe(
            self._hass, BRIDGE_STATUS_TOPIC, self._async_message_received
        )

    @callback
    def _async_message_received(self, _msg: object) -> None:
        self.last_seen = dt_util.utcnow()

    @callback
    def async_stop(self) -> None:
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None

    @property
    def bridge_running(self) -> bool:
        return (
            self.last_seen is not None
            and dt_util.utcnow() - self.last_seen < BRIDGE_ACTIVE_WINDOW
        )


DATA_MONITORS: HassKey[dict[str, BridgeActivityMonitor]] = HassKey(
    f"{DOMAIN}_bridge_monitors"
)


def _old_domain(unique_id: str) -> str:
    target = OLD_UNIQUE_IDS[unique_id]
    return target[0] if target else "climate"


def _mqtt_loaded(hass: HomeAssistant) -> bool:
    return bool(hass.config_entries.async_loaded_entries(MQTT_DOMAIN))


@callback
def find_old_entities(hass: HomeAssistant) -> list[er.RegistryEntry]:
    """Return the bridge's entities still in the entity registry."""
    return [
        entry
        for entry in er.async_get(hass).entities.values()
        if entry.platform == MQTT_DOMAIN
        and entry.unique_id in OLD_UNIQUE_IDS
        and entry.domain == _old_domain(entry.unique_id)
    ]


@callback
def async_get_monitor(
    hass: HomeAssistant, entry_id: str
) -> BridgeActivityMonitor | None:
    return hass.data.get(DATA_MONITORS, {}).get(entry_id)


@callback
def async_stop_monitor(hass: HomeAssistant, entry_id: str) -> None:
    if (
        monitor := hass.data.setdefault(DATA_MONITORS, {}).pop(entry_id, None)
    ) is not None:
        monitor.async_stop()


async def _async_start_monitor(hass: HomeAssistant, entry_id: str) -> None:
    monitors = hass.data.setdefault(DATA_MONITORS, {})
    if entry_id in monitors or not _mqtt_loaded(hass):
        return
    monitor = BridgeActivityMonitor(hass)
    try:
        await monitor.async_start()
    except HomeAssistantError as err:
        _LOGGER.debug("Cannot watch for the Sabik bridge: %s", err)
        return
    monitors[entry_id] = monitor


@callback
def async_clear_issue(hass: HomeAssistant, entry_id: str) -> None:
    ir.async_delete_issue(hass, DOMAIN, ISSUE_ID)
    async_stop_monitor(hass, entry_id)


async def async_check_migration(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Raise the migration issue while bridge entities remain and MQTT is configured."""
    if not hass.config_entries.async_entries(MQTT_DOMAIN) or not find_old_entities(
        hass
    ):
        async_clear_issue(hass, entry.entry_id)
        return
    ir.async_create_issue(
        hass,
        DOMAIN,
        ISSUE_ID,
        is_fixable=True,
        is_persistent=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key=ISSUE_ID,
        data={"entry_id": entry.entry_id},
    )
    await _async_start_monitor(hass, entry.entry_id)


async def _async_clear_discovery(hass: HomeAssistant) -> bool:
    if not _mqtt_loaded(hass):
        return False
    from homeassistant.components import mqtt  # noqa: PLC0415

    try:
        for topic in OLD_DISCOVERY_TOPICS:
            await mqtt.async_publish(hass, topic, "", 0, True)
    except HomeAssistantError as err:
        _LOGGER.warning("Could not clear the old Sabik discovery topics: %s", err)
        return False
    return True


async def _async_wait_states_removed(
    hass: HomeAssistant, entity_ids: list[str]
) -> None:
    """Wait until removed entities have dropped their state, or time out.

    A live MQTT entity removes itself in a task after its registry entry goes;
    renaming onto its ID before then would fail or race with that removal.
    """
    pending = {entity_id for entity_id in entity_ids if hass.states.get(entity_id)}
    if not pending:
        return
    done = asyncio.Event()

    @callback
    def _state_changed(event: Event[EventStateChangedData]) -> None:
        if event.data["new_state"] is None:
            pending.discard(event.data["entity_id"])
            if not pending:
                done.set()

    unsubscribe = async_track_state_change_event(hass, list(pending), _state_changed)
    try:
        async with asyncio.timeout(REMOVAL_TIMEOUT):
            await done.wait()
    except TimeoutError:
        _LOGGER.warning("Old Sabik entities still have a state: %s", sorted(pending))
    finally:
        unsubscribe()


def _is_collision_suffix(old_id: str, new_id: str) -> bool:
    """Whether old_id is new_id plus HA's "_2"-style collision suffix.

    That happens when uncleared discovery brings an old entity back after a
    migration: our entity already holds the real ID, so don't move it.
    """
    suffix = old_id.removeprefix(f"{new_id}_")
    return suffix != old_id and suffix.isdigit()


@callback
def _async_remove_orphan_bridge_devices(hass: HomeAssistant) -> None:
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    for device in list(dev_reg.devices.values()):
        if not device.identifiers or not device.identifiers <= OLD_DEVICE_IDENTIFIERS:
            continue
        if er.async_entries_for_device(
            ent_reg, device.id, include_disabled_entities=True
        ):
            continue
        dev_reg.async_remove_device(device.id)


async def async_migrate(hass: HomeAssistant, entry: ConfigEntry) -> MigrationResult:
    """Clear the bridge's discovery, drop its entities and take over their IDs."""
    result = MigrationResult()
    ent_reg = er.async_get(hass)

    # Recorded before publishing: an echoed empty discovery payload makes MQTT
    # delete the entries itself, and their entity_ids would be lost.
    old_entries = find_old_entities(hass)

    result.discovery_cleared = await _async_clear_discovery(hass)

    for old in old_entries:
        current = ent_reg.async_get(old.entity_id)
        if current is not None and current.id == old.id:
            ent_reg.async_remove(old.entity_id)
        result.removed.append(old.entity_id)
    _async_remove_orphan_bridge_devices(hass)
    await _async_wait_states_removed(hass, result.removed)

    for old in old_entries:
        if (target := OLD_UNIQUE_IDS[old.unique_id]) is None:
            continue
        domain, key = target
        new_id = ent_reg.async_get_entity_id(domain, DOMAIN, f"{entry.entry_id}_{key}")
        if new_id is None:
            _LOGGER.warning("No Sabik entity to take over %s", old.entity_id)
            continue
        if new_id == old.entity_id or _is_collision_suffix(old.entity_id, new_id):
            continue
        try:
            ent_reg.async_update_entity(new_id, new_entity_id=old.entity_id)
        except ValueError as err:
            _LOGGER.warning("Cannot rename %s to %s: %s", new_id, old.entity_id, err)
            result.skipped.append((new_id, old.entity_id))
            continue
        result.renamed.append((new_id, old.entity_id))
    return result

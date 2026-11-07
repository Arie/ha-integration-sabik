"""The Sabik integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import (
    SIGNAL_CONFIG_ENTRY_CHANGED,
    ConfigEntry,
    ConfigEntryChange,
    ConfigEntryState,
)
from homeassistant.const import EVENT_COMPONENT_LOADED
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.setup import EventComponentLoaded

from . import modbus
from .const import DOMAIN, PLATFORMS
from .coordinator import SabikConfigEntry, SabikCoordinator, settings_from_entry
from .entity import device_info
from .frontend import async_register_card
from .migration import (
    ISSUE_ID,
    MQTT_DOMAIN,
    async_check_migration,
    async_stop_monitor,
)

_LOGGER = logging.getLogger(__name__)


CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    await async_register_card(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: SabikConfigEntry) -> bool:
    client = modbus.create_client(settings_from_entry(entry.data))
    coordinator = SabikCoordinator(hass, entry, client)
    try:
        await coordinator.async_config_entry_first_refresh()
        entry.runtime_data = coordinator

        # Registered explicitly so the device exists before any entity does.
        dr.async_get(hass).async_get_or_create(
            config_entry_id=entry.entry_id, **device_info(entry.entry_id)
        )
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except BaseException:
        await client.async_close()
        raise

    entry.async_on_unload(lambda: async_stop_monitor(hass, entry.entry_id))
    await _async_check_migration(hass, entry)

    @callback
    def _is_mqtt(data: EventComponentLoaded) -> bool:
        return data["component"] == MQTT_DOMAIN

    @callback
    def _mqtt_loaded(event: Event[EventComponentLoaded]) -> None:
        entry.async_create_task(hass, _async_check_migration(hass, entry))

    # The issue also needs raising when MQTT sets up after us.
    entry.async_on_unload(
        hass.bus.async_listen(EVENT_COMPONENT_LOADED, _mqtt_loaded, event_filter=_is_mqtt)
    )

    @callback
    def _mqtt_entry_changed(change: ConfigEntryChange, changed: ConfigEntry) -> None:
        if changed.domain == MQTT_DOMAIN and changed.state is ConfigEntryState.LOADED:
            entry.async_create_task(
                hass, _async_check_migration(hass, entry, resubscribe=True)
            )

    # A reloaded MQTT entry has a new client that doesn't know the bridge monitor.
    entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_CONFIG_ENTRY_CHANGED, _mqtt_entry_changed)
    )
    return True


async def _async_check_migration(
    hass: HomeAssistant, entry: SabikConfigEntry, *, resubscribe: bool = False
) -> None:
    # The migration is optional; a failure here must not take the unit down.
    try:
        await async_check_migration(hass, entry, resubscribe=resubscribe)
    except Exception:  # noqa: BLE001
        _LOGGER.exception("Could not check for the Sabik MQTT bridge")


async def async_unload_entry(hass: HomeAssistant, entry: SabikConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.client.async_close()
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: SabikConfigEntry) -> None:
    async_stop_monitor(hass, entry.entry_id)
    issue = ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_ID)
    if issue is not None and (issue.data or {}).get("entry_id") == entry.entry_id:
        ir.async_delete_issue(hass, DOMAIN, ISSUE_ID)

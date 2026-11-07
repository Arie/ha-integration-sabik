"""The Sabik integration."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import modbus
from .const import PLATFORMS
from .coordinator import SabikConfigEntry, SabikCoordinator, settings_from_entry
from .entity import device_info


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    return True


async def async_setup_entry(hass: HomeAssistant, entry: SabikConfigEntry) -> bool:
    client = modbus.create_client(settings_from_entry(entry.data))
    coordinator = SabikCoordinator(hass, entry, client)
    try:
        await coordinator.async_config_entry_first_refresh()
    except BaseException:
        await client.async_close()
        raise
    entry.runtime_data = coordinator

    # Registered explicitly so the device exists before any entity does.
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id, **device_info(entry.entry_id)
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SabikConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.client.async_close()
    return unloaded

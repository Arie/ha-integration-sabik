"""Base entity for Sabik."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SabikCoordinator

DEVICE_NAME = "Sabik"
DEVICE_MANUFACTURER = "S&P"
DEVICE_MODEL = "Sabik 350"


def device_info(entry_id: str) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry_id)},
        name=DEVICE_NAME,
        manufacturer=DEVICE_MANUFACTURER,
        model=DEVICE_MODEL,
    )


class SabikEntity(CoordinatorEntity[SabikCoordinator]):
    """Entity attached to the single Sabik device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SabikCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry_id = coordinator.config_entry.entry_id
        self._attr_translation_key = key
        self._attr_unique_id = f"{entry_id}_{key}"
        self._attr_device_info = device_info(entry_id)

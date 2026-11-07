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

    @property
    def suggested_object_id(self) -> str | None:
        """Build entity_ids from the English name on every instance language.

        HA derives object ids from the instance language when it has native
        ids for it (for example Dutch), which would break the stable ids.
        """
        platform_data = self.platform_data
        if platform_data is not None and self._name_translation_key:
            name = platform_data.default_language_platform_translations.get(
                self._name_translation_key
            )
            if name:
                return name
        return super().suggested_object_id

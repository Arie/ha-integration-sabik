"""Fan speed select for the Sabik unit."""

from __future__ import annotations

from typing import Literal, cast

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SabikConfigEntry, SabikCoordinator
from .entity import SabikEntity

PARALLEL_UPDATES = 1

# Snooze is a separate switch, so it is not offered as an option.
OPTIONS = ["low", "medium", "high", "auto"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SabikConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([SabikFanSpeedSelect(entry.runtime_data)])


class SabikFanSpeedSelect(SabikEntity, SelectEntity):
    _attr_options = OPTIONS

    def __init__(self, coordinator: SabikCoordinator) -> None:
        super().__init__(coordinator, "fan_speed")

    @property
    def current_option(self) -> str | None:
        speed = self.coordinator.data.fan_speed
        return speed if speed in OPTIONS else None

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_set_fan_speed(
            cast(Literal["low", "medium", "high", "auto"], option)
        )

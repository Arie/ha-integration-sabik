"""Main fan control for the Sabik unit."""

from __future__ import annotations

from typing import Any, Literal, cast

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SabikConfigEntry, SabikCoordinator
from .entity import SabikEntity
from .registers import COIL_SNOOZE

PARALLEL_UPDATES = 1

PRESET_MODES = ["low", "medium", "high", "auto", "snooze"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SabikConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([SabikFan(entry.runtime_data)])


class SabikFan(SabikEntity, FanEntity):
    _attr_name = None
    _attr_supported_features = (
        FanEntityFeature.PRESET_MODE
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )
    _attr_preset_modes = PRESET_MODES

    def __init__(self, coordinator: SabikCoordinator) -> None:
        super().__init__(coordinator, "ventilation")

    @property
    def is_on(self) -> bool:
        return not self.coordinator.data.snooze

    @property
    def preset_mode(self) -> str | None:
        data = self.coordinator.data
        if data.snooze:
            return "snooze"
        # HR 132 keeps "snooze" only while the coil is set; without it the speed is unknown.
        return data.fan_speed if data.fan_speed in PRESET_MODES[:4] else None

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        if preset_mode is None:
            # Un-snoozing resumes the previous speed; HR 132 is kept while snoozed.
            await self.coordinator.async_write_coil(COIL_SNOOZE, False)
        else:
            await self.async_set_preset_mode(preset_mode)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_fan_speed("snooze")

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        await self.coordinator.async_set_fan_speed(
            cast(Literal["low", "medium", "high", "auto", "snooze"], preset_mode)
        )

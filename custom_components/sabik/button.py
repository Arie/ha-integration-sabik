"""Buttons for the Sabik unit."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import SabikConfigEntry, SabikCoordinator
from .entity import SabikEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class SabikButtonEntityDescription(ButtonEntityDescription):
    """Button description with its command."""

    press_fn: Callable[[SabikCoordinator], Awaitable[None]]


BUTTONS: tuple[SabikButtonEntityDescription, ...] = (
    SabikButtonEntityDescription(
        key="reset_filter_alarm",
        press_fn=lambda coordinator: coordinator.async_reset_filter_alarm(),
    ),
    SabikButtonEntityDescription(
        key="sync_clock",
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda coordinator: coordinator.async_sync_clock(dt_util.now()),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SabikConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(SabikButton(coordinator, desc) for desc in BUTTONS)


class SabikButton(SabikEntity, ButtonEntity):
    entity_description: SabikButtonEntityDescription

    def __init__(
        self, coordinator: SabikCoordinator, description: SabikButtonEntityDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    async def async_press(self) -> None:
        await self.entity_description.press_fn(self.coordinator)

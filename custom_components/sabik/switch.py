"""Switches for the Sabik unit."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SabikConfigEntry, SabikCoordinator
from .entity import SabikEntity
from .registers import (
    COIL_ALLOW_AUTO_BYPASS,
    COIL_SNOOZE,
    COIL_WORK_MODE_AUTO,
    SabikData,
)

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class SabikSwitchEntityDescription(SwitchEntityDescription):
    """Switch description with state lookup and command."""

    is_on_fn: Callable[[SabikData], bool]
    set_fn: Callable[[SabikCoordinator, bool], Awaitable[None]]


def _coil(key: str, address: int) -> SabikSwitchEntityDescription:
    return SabikSwitchEntityDescription(
        key=key,
        is_on_fn=lambda data: getattr(data, key),
        set_fn=lambda coordinator, on: coordinator.async_write_coil(address, on),
    )


SWITCHES: tuple[SabikSwitchEntityDescription, ...] = (
    SabikSwitchEntityDescription(
        key="boost",
        is_on_fn=lambda data: data.boost,
        set_fn=lambda coordinator, on: coordinator.async_set_boost(on),
    ),
    SabikSwitchEntityDescription(
        key="manual_bypass",
        is_on_fn=lambda data: data.manual_bypass,
        set_fn=lambda coordinator, on: coordinator.async_set_manual_bypass(on),
    ),
    _coil("allow_automatic_bypass", COIL_ALLOW_AUTO_BYPASS),
    SabikSwitchEntityDescription(
        key="summer_mode",
        is_on_fn=lambda data: data.summer_mode,
        set_fn=lambda coordinator, on: coordinator.async_set_summer_mode(on),
    ),
    _coil("snooze", COIL_SNOOZE),
    _coil("work_mode_auto", COIL_WORK_MODE_AUTO),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SabikConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(SabikSwitch(coordinator, desc) for desc in SWITCHES)


class SabikSwitch(SabikEntity, SwitchEntity):
    entity_description: SabikSwitchEntityDescription

    def __init__(
        self, coordinator: SabikCoordinator, description: SabikSwitchEntityDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        return self.entity_description.is_on_fn(self.coordinator.data)

    async def async_turn_on(self, **kwargs) -> None:
        await self.entity_description.set_fn(self.coordinator, True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.entity_description.set_fn(self.coordinator, False)

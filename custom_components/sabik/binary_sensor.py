"""Binary sensors for the Sabik unit."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SabikConfigEntry, SabikCoordinator
from .entity import SabikEntity
from .registers import SabikData

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class SabikBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Binary sensor description with a lookup on the decoded data."""

    is_on_fn: Callable[[SabikData], bool]


def _problem(key: str, *, diagnostic: bool = False) -> SabikBinarySensorEntityDescription:
    return SabikBinarySensorEntityDescription(
        key=key,
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC if diagnostic else None,
        entity_registry_enabled_default=not diagnostic,
        is_on_fn=lambda data: getattr(data, key),
    )


BINARY_SENSORS: tuple[SabikBinarySensorEntityDescription, ...] = (
    _problem("filter_alarm"),
    _problem("extract_fan_alarm"),
    _problem("supply_fan_alarm"),
    SabikBinarySensorEntityDescription(
        key="summer_mode", is_on_fn=lambda data: data.summer_mode
    ),
    SabikBinarySensorEntityDescription(
        key="boost_status", is_on_fn=lambda data: data.boost_active
    ),
    _problem("active_alarms", diagnostic=True),
    _problem("extract_sensor_fault", diagnostic=True),
    _problem("exhaust_sensor_fault", diagnostic=True),
    _problem("outdoor_sensor_fault", diagnostic=True),
    _problem("supply_sensor_fault", diagnostic=True),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SabikConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(SabikBinarySensor(coordinator, desc) for desc in BINARY_SENSORS)


class SabikBinarySensor(SabikEntity, BinarySensorEntity):
    entity_description: SabikBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: SabikCoordinator,
        description: SabikBinarySensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        return self.entity_description.is_on_fn(self.coordinator.data)

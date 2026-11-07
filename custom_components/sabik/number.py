"""Numbers for the Sabik unit: bypass thresholds and manual bypass timer."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SabikConfigEntry, SabikCoordinator
from .entity import SabikEntity
from .registers import (
    HR_BYPASS_TIMER,
    HR_MIN_ETA,
    HR_MIN_ETA_ODA,
    HR_MIN_ODA,
    SabikData,
    celsius_to_raw,
)

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class SabikNumberEntityDescription(NumberEntityDescription):
    """Number description with value lookup and register write."""

    value_fn: Callable[[SabikData], float]
    address: int
    to_raw: Callable[[float], int]


def _threshold(
    key: str, address: int, minimum: float, maximum: float, device_class
) -> SabikNumberEntityDescription:
    return SabikNumberEntityDescription(
        key=key,
        device_class=device_class,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_min_value=minimum,
        native_max_value=maximum,
        native_step=0.1,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda data: getattr(data, key),
        address=address,
        to_raw=celsius_to_raw,
    )


NUMBERS: tuple[SabikNumberEntityDescription, ...] = (
    _threshold(
        "min_outdoor_temperature_for_bypass",
        HR_MIN_ODA,
        12.0,
        20.0,
        NumberDeviceClass.TEMPERATURE,
    ),
    _threshold(
        "min_extract_temperature_for_bypass",
        HR_MIN_ETA,
        21.0,
        30.0,
        NumberDeviceClass.TEMPERATURE,
    ),
    # No device class: a difference must not be unit-converted like an absolute.
    _threshold(
        "min_temperature_difference_for_bypass", HR_MIN_ETA_ODA, 3.0, 6.0, None
    ),
    SabikNumberEntityDescription(
        key="manual_bypass_timer",
        device_class=NumberDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        native_min_value=1,
        native_max_value=8,
        native_step=1,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda data: data.manual_bypass_timer,
        address=HR_BYPASS_TIMER,
        to_raw=int,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SabikConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(SabikNumber(coordinator, desc) for desc in NUMBERS)


class SabikNumber(SabikEntity, NumberEntity):
    entity_description: SabikNumberEntityDescription

    def __init__(
        self, coordinator: SabikCoordinator, description: SabikNumberEntityDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float:
        return self.entity_description.value_fn(self.coordinator.data)

    async def async_set_native_value(self, value: float) -> None:
        # The unit silently ignores out-of-range writes; HA's number service
        # already rejects them against native_min/max_value.
        desc = self.entity_description
        await self.coordinator.async_set_register(desc.address, desc.to_raw(value))

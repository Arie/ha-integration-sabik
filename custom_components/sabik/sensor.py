"""Sensors for the Sabik unit."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from .coordinator import SabikConfigEntry, SabikCoordinator
from .entity import SabikEntity
from .registers import (
    BYPASS_POSITIONS,
    COMMUNICATION_ERRORS,
    DEFROST_STATUSES,
    WORK_MODES,
    SabikData,
)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class SabikSensorEntityDescription(SensorEntityDescription):
    """Sensor description with a value lookup on the decoded data."""

    value_fn: Callable[[SabikData], StateType | datetime]


def _attr(name: str) -> Callable[[SabikData], StateType]:
    return lambda data: getattr(data, name)


def _local_clock(data: SabikData) -> datetime | None:
    # The unit stores wall-clock time without a zone; interpret it as HA local time.
    if data.unit_clock is None:
        return None
    return dt_util.as_utc(
        data.unit_clock.replace(tzinfo=dt_util.get_default_time_zone())
    )


def _temperature(key: str, **kwargs) -> SabikSensorEntityDescription:
    return SabikSensorEntityDescription(
        key=key,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_attr(key),
        **kwargs,
    )


def _humidity(key: str) -> SabikSensorEntityDescription:
    return SabikSensorEntityDescription(
        key=key,
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_attr(key),
    )


def _voltage(key: str) -> SabikSensorEntityDescription:
    return SabikSensorEntityDescription(
        key=key,
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=1,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_attr(key),
    )


def _rpm(key: str) -> SabikSensorEntityDescription:
    # Literal "RPM" keeps the old statistics; HA's own unit is lowercase.
    return SabikSensorEntityDescription(
        key=key,
        native_unit_of_measurement="RPM",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_attr(key),
    )


def _enum(
    key: str, options: list[str], **kwargs
) -> SabikSensorEntityDescription:
    return SabikSensorEntityDescription(
        key=key,
        device_class=SensorDeviceClass.ENUM,
        options=options,
        value_fn=_attr(key),
        **kwargs,
    )


SENSORS: tuple[SabikSensorEntityDescription, ...] = (
    _temperature("extract_air_temperature"),
    _temperature("exhaust_air_temperature"),
    _temperature("outdoor_air_temperature"),
    _temperature("supply_air_temperature"),
    _humidity("rh_extract_air"),
    _humidity("rh_exhaust_air"),
    _humidity("rh_outdoor_air"),
    _humidity("rh_supply_air"),
    _voltage("voltage_extract_motor"),
    _voltage("voltage_supply_motor"),
    _rpm("rpm_extract_motor"),
    _rpm("rpm_supply_motor"),
    _enum("bypass_valve_position", [*BYPASS_POSITIONS.values(), "unknown"]),
    _enum("current_work_mode", [*WORK_MODES.values(), "unknown"]),
    _enum("defrost_status", [*DEFROST_STATUSES.values(), "unknown"]),
    SabikSensorEntityDescription(
        key="selected_air_volume", value_fn=_attr("selected_air_volume")
    ),
    _temperature("min_outdoor_temperature_for_bypass"),
    _temperature("min_extract_temperature_for_bypass"),
    _temperature("min_temperature_difference_for_bypass"),
    _enum(
        "communication_error",
        list(COMMUNICATION_ERRORS.values()),
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SabikSensorEntityDescription(
        key="unit_clock",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_local_clock,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SabikConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(SabikSensor(coordinator, desc) for desc in SENSORS)


class SabikSensor(SabikEntity, SensorEntity):
    entity_description: SabikSensorEntityDescription

    def __init__(
        self, coordinator: SabikCoordinator, description: SabikSensorEntityDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> StateType | datetime:
        return self.entity_description.value_fn(self.coordinator.data)

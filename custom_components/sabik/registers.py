"""Sabik register map and decoding."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .modbus import RawRegisters, ReadBlock

# Same blocks the original bridge reads, so behavior on the wire is identical.
READ_PLAN: tuple[ReadBlock, ...] = (
    ReadBlock("di", 0, 2),
    ReadBlock("di", 6, 6),
    ReadBlock("di", 15, 1),
    ReadBlock("di", 28, 2),
    ReadBlock("coil", 0, 1),
    ReadBlock("coil", 7, 3),
    ReadBlock("coil", 16, 2),
    ReadBlock("coil", 25, 1),
    ReadBlock("ir", 4, 2),
    ReadBlock("ir", 25, 8),
    ReadBlock("ir", 59, 5),
    ReadBlock("ir", 90, 1),
    ReadBlock("hr", 0, 3),
    ReadBlock("hr", 48, 6),
    ReadBlock("hr", 56, 1),
    ReadBlock("hr", 63, 1),
    ReadBlock("hr", 65, 1),
    ReadBlock("hr", 67, 1),
    ReadBlock("hr", 132, 1),
)

COIL_RESET_FILTER = 0
COIL_MANUAL_BYPASS = 7
COIL_ALLOW_AUTO_BYPASS = 8
COIL_SUMMER_MODE = 9
COIL_BOOST = 16
COIL_SNOOZE = 17
COIL_WORK_MODE_AUTO = 25

# The unit applies FC16 writes but never replies; write the clock as six FC6 writes.
HR_CLOCK = 48
HR_BYPASS_TIMER = 56
HR_MIN_ODA = 63
HR_MIN_ETA = 65
HR_MIN_ETA_ODA = 67
HR_AIR_VOLUME = 132

# Hardware-dependent, checked on the real unit.
# Observed: DI 29 = 1 while boost is active; this contradicts the register doc.
BOOST_ACTIVE_WHEN_DI29_IS: bool = True
VOLTAGE_SCALE: float = 0.1  # dV, confirmed on the unit

WORK_MODES: dict[int, str] = dict(
    enumerate(
        (
            "snooze",
            "low",
            "medium",
            "high",
            "boost",
            "auto_humidity",
            "auto_voc",
            "auto_0_10v_control",
            "auto_boost",
            "week_program_1",
            "week_program_2",
            "week_program_3",
            "week_program_4",
        )
    )
)
DEFROST_STATUSES: dict[int, str] = dict(
    enumerate(
        ("inactive", "active_fireplace", "active_preheater", "active_unbalanced_airvolume")
    )
)
BYPASS_POSITIONS: dict[int, str] = dict(enumerate(("closed", "open", "error")))
COMMUNICATION_ERRORS: dict[int, str] = {0: "none", 1: "remote_control", 4: "modbus_rtu"}
FAN_SPEEDS: dict[int, str] = dict(enumerate(("low", "medium", "high", "auto", "snooze")))
FAN_SPEED_VALUES: dict[str, int] = {v: k for k, v in FAN_SPEEDS.items()}


@dataclass(frozen=True)
class SabikData:
    """Decoded unit state."""

    active_alarms: bool
    filter_alarm: bool
    extract_sensor_fault: bool
    exhaust_sensor_fault: bool
    outdoor_sensor_fault: bool
    supply_sensor_fault: bool
    extract_fan_alarm: bool
    supply_fan_alarm: bool
    automatic_bypass: bool
    boost_contact: bool
    boost_active: bool
    manual_bypass: bool
    allow_automatic_bypass: bool
    summer_mode: bool
    boost: bool
    snooze: bool
    work_mode_auto: bool
    communication_error: str | None
    defrost_status: str
    current_work_mode: str
    bypass_valve_position: str
    extract_air_temperature: float
    exhaust_air_temperature: float
    outdoor_air_temperature: float
    supply_air_temperature: float
    rh_extract_air: int
    rh_exhaust_air: int
    rh_outdoor_air: int
    rh_supply_air: int
    voltage_extract_motor: float
    voltage_supply_motor: float
    rpm_extract_motor: int
    rpm_supply_motor: int
    manual_bypass_timer: int
    min_outdoor_temperature_for_bypass: float
    min_extract_temperature_for_bypass: float
    min_temperature_difference_for_bypass: float
    selected_air_volume: int
    fan_speed: str | None
    unit_clock: datetime | None


def to_signed(raw: int) -> int:
    """Interpret a 16-bit register as signed."""
    return raw - 65536 if raw > 32767 else raw


def celsius_to_raw(value: float) -> int:
    """Convert degrees Celsius to the unit's deci-degree register value."""
    return round(value * 10)


def _temp(raw: int) -> float:
    return to_signed(raw) / 10


def _clock(hr: dict[int, int]) -> datetime | None:
    try:
        return datetime(
            hr[HR_CLOCK + 2],
            hr[HR_CLOCK + 1],
            hr[HR_CLOCK],
            hr[HR_CLOCK + 3],
            hr[HR_CLOCK + 4],
            hr[HR_CLOCK + 5],
        )
    except ValueError:
        return None


def decode(raw: RawRegisters) -> SabikData:
    """Decode a full READ_PLAN result into SabikData."""
    di, coil, ir, hr = raw.di, raw.coil, raw.ir, raw.hr
    return SabikData(
        active_alarms=di[0],
        filter_alarm=di[1],
        extract_sensor_fault=di[6],
        exhaust_sensor_fault=di[7],
        outdoor_sensor_fault=di[8],
        supply_sensor_fault=di[9],
        extract_fan_alarm=di[10],
        supply_fan_alarm=di[11],
        automatic_bypass=di[15],
        boost_contact=di[28],
        boost_active=di[29] == BOOST_ACTIVE_WHEN_DI29_IS,
        manual_bypass=coil[COIL_MANUAL_BYPASS],
        allow_automatic_bypass=coil[COIL_ALLOW_AUTO_BYPASS],
        summer_mode=coil[COIL_SUMMER_MODE],
        boost=coil[COIL_BOOST],
        snooze=coil[COIL_SNOOZE],
        work_mode_auto=coil[COIL_WORK_MODE_AUTO],
        communication_error=COMMUNICATION_ERRORS.get(ir[4]),
        defrost_status=DEFROST_STATUSES.get(ir[5], "unknown"),
        current_work_mode=WORK_MODES.get(ir[90], "unknown"),
        bypass_valve_position=BYPASS_POSITIONS.get(ir[63], "unknown"),
        extract_air_temperature=_temp(ir[25]),
        exhaust_air_temperature=_temp(ir[26]),
        outdoor_air_temperature=_temp(ir[27]),
        supply_air_temperature=_temp(ir[28]),
        rh_extract_air=ir[29],
        rh_exhaust_air=ir[30],
        rh_outdoor_air=ir[31],
        rh_supply_air=ir[32],
        voltage_extract_motor=round(ir[59] * VOLTAGE_SCALE, 1),
        voltage_supply_motor=round(ir[60] * VOLTAGE_SCALE, 1),
        rpm_extract_motor=ir[61],
        rpm_supply_motor=ir[62],
        manual_bypass_timer=hr[HR_BYPASS_TIMER],
        # Unsigned in the doc ranges, so no sign conversion.
        min_outdoor_temperature_for_bypass=hr[HR_MIN_ODA] / 10,
        min_extract_temperature_for_bypass=hr[HR_MIN_ETA] / 10,
        min_temperature_difference_for_bypass=hr[HR_MIN_ETA_ODA] / 10,
        selected_air_volume=hr[HR_AIR_VOLUME],
        fan_speed=FAN_SPEEDS.get(hr[HR_AIR_VOLUME]),
        unit_clock=_clock(hr),
    )

"""Tests for the Sabik register map and decoding."""

from datetime import datetime

import pytest

from custom_components.sabik.modbus import RawRegisters, ReadBlock
from custom_components.sabik.registers import (
    READ_PLAN,
    WORK_MODES,
    decode,
)


def raw_fixture() -> RawRegisters:
    raw = RawRegisters(di={}, coil={}, ir={}, hr={})
    for block in READ_PLAN:
        target = getattr(raw, block.kind)
        for addr in range(block.address, block.address + block.count):
            target[addr] = False if block.kind in ("di", "coil") else 0
    raw.di[29] = True
    raw.hr[48], raw.hr[49], raw.hr[50] = 1, 1, 2026
    return raw


def test_read_plan_matches_bridge():
    expected = (
        [ReadBlock("di", a, c) for a, c in ((0, 2), (6, 6), (15, 1), (28, 2))]
        + [ReadBlock("coil", a, c) for a, c in ((0, 1), (7, 3), (16, 2), (25, 1))]
        + [ReadBlock("ir", a, c) for a, c in ((4, 2), (25, 8), (59, 5), (90, 1))]
        + [
            ReadBlock("hr", a, c)
            for a, c in ((0, 3), (48, 6), (56, 1), (63, 1), (65, 1), (67, 1), (132, 1))
        ]
    )
    assert list(READ_PLAN) == expected
    assert len(READ_PLAN) == 19


def test_signed_temperature():
    raw = raw_fixture()
    raw.ir[27] = 65531
    raw.ir[25] = 215
    data = decode(raw)
    assert data.outdoor_air_temperature == -0.5
    assert data.extract_air_temperature == 21.5


def test_thresholds_are_celsius():
    raw = raw_fixture()
    raw.hr[63], raw.hr[65], raw.hr[67] = 130, 230, 30
    data = decode(raw)
    assert data.min_outdoor_temperature_for_bypass == 13.0
    assert data.min_extract_temperature_for_bypass == 23.0
    assert data.min_temperature_difference_for_bypass == 3.0


def test_voltage_scale():
    raw = raw_fixture()
    raw.ir[59] = 45
    assert decode(raw).voltage_extract_motor == 4.5


def test_work_mode_mapping():
    raw = raw_fixture()
    for value, name in WORK_MODES.items():
        raw.ir[90] = value
        assert decode(raw).current_work_mode == name
    raw.ir[90] = 12
    assert decode(raw).current_work_mode == "week_program_4"
    raw.ir[90] = 13
    assert decode(raw).current_work_mode == "unknown"


def test_enum_fallbacks():
    raw = raw_fixture()
    raw.ir[63] = 7
    raw.ir[5] = 9
    raw.ir[4] = 2
    data = decode(raw)
    assert data.bypass_valve_position == "unknown"
    assert data.defrost_status == "unknown"
    assert data.communication_error is None


def test_fan_speed_unknown_is_none():
    raw = raw_fixture()
    for value, name in enumerate(["low", "medium", "high", "auto", "snooze"]):
        raw.hr[132] = value
        assert decode(raw).fan_speed == name
    raw.hr[132] = 9
    assert decode(raw).fan_speed is None


def test_boost_polarity():
    raw = raw_fixture()
    raw.di[29] = False
    assert decode(raw).boost_active is True
    raw.di[29] = True
    assert decode(raw).boost_active is False


def test_unit_clock():
    raw = raw_fixture()
    for addr, val in zip(range(48, 54), (7, 11, 2026, 14, 3, 9)):
        raw.hr[addr] = val
    assert decode(raw).unit_clock == datetime(2026, 11, 7, 14, 3, 9)
    raw.hr[48] = 0
    assert decode(raw).unit_clock is None

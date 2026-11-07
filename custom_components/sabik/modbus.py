"""Modbus client types for the Sabik integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ReadBlock:
    """One contiguous Modbus read."""

    kind: Literal["di", "coil", "ir", "hr"]
    address: int
    count: int


@dataclass
class RawRegisters:
    """Raw values keyed by Modbus address, per register type."""

    di: dict[int, bool]
    coil: dict[int, bool]
    ir: dict[int, int]
    hr: dict[int, int]

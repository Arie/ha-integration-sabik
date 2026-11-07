"""In-memory stand-in for SabikClient."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from custom_components.sabik.modbus import RawRegisters, ReadBlock, SabikModbusError
from custom_components.sabik.registers import READ_PLAN

# Realistic running state; anything not listed reads as 0/False.
_IR = {4: 0, 25: 215, 26: 180, 27: 95, 28: 200, 29: 45, 30: 50, 31: 70, 32: 40,
       59: 50, 60: 52, 61: 1200, 62: 1250, 63: 0, 90: 2}
_HR = {48: 7, 49: 11, 50: 2026, 51: 12, 52: 30, 53: 0, 56: 0,
       63: 130, 65: 230, 67: 30, 132: 1}


class FakeSabikClient:
    """Same async surface as SabikClient, backed by dicts."""

    def __init__(self) -> None:
        self.di: dict[int, bool] = {}
        self.coil: dict[int, bool] = {}
        self.ir: dict[int, int] = {}
        self.hr: dict[int, int] = {}
        for block in READ_PLAN:
            store = getattr(self, block.kind)
            for addr in range(block.address, block.address + block.count):
                store[addr] = False if block.kind in ("di", "coil") else 0
        self.di[29] = True  # boost not active
        self.ir.update(_IR)
        self.hr.update(_HR)
        self.writes: list[tuple[str, int, Any]] = []
        self.closed = False
        self.fail = False

    def _check(self) -> None:
        if self.fail:
            raise SabikModbusError("No response from the unit")

    async def async_read(self, plan: Iterable[ReadBlock]) -> RawRegisters:
        self._check()
        raw = RawRegisters(di={}, coil={}, ir={}, hr={})
        for block in plan:
            store = getattr(self, block.kind)
            for addr in range(block.address, block.address + block.count):
                getattr(raw, block.kind)[addr] = store.get(
                    addr, False if block.kind in ("di", "coil") else 0
                )
        return raw

    async def async_write_coil(self, address: int, value: bool) -> None:
        self._check()
        self.coil[address] = value
        self.writes.append(("coil", address, value))

    async def async_write_register(self, address: int, value: int) -> None:
        self._check()
        self.hr[address] = value
        self.writes.append(("hr", address, value))

    async def async_write_registers(self, address: int, values: list[int]) -> None:
        self._check()
        for offset, value in enumerate(values):
            self.hr[address + offset] = value
            self.writes.append(("hr", address + offset, value))

    async def async_close(self) -> None:
        self.closed = True

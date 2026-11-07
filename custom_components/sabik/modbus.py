"""Modbus client types for the Sabik integration."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Literal

from pymodbus import FramerType
from pymodbus.client import AsyncModbusSerialClient, AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException

TIMEOUT = 2
RETRIES = 1


class SabikModbusError(Exception):
    """A Modbus operation failed; the message is safe to show to users."""


@dataclass(frozen=True)
class ConnectionSettings:
    """How to reach the unit."""

    transport: Literal["serial", "rtu_over_tcp", "tcp"]
    port: str | None = None
    host: str | None = None
    tcp_port: int | None = None
    baudrate: int = 19200
    parity: Literal["E", "O", "N"] = "E"
    slave: int = 1


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


class SabikClient:
    """Serialized, lazily connecting wrapper around one pymodbus client."""

    def __init__(self, settings: ConnectionSettings) -> None:
        self._settings = settings
        self._client: Any = None
        self._lock = asyncio.Lock()

    def _build(self) -> Any:
        cfg = self._settings
        # reconnect_delay=0 turns off pymodbus' background reconnect; we
        # reconnect lazily on the next call instead.
        common = {"timeout": TIMEOUT, "retries": RETRIES, "reconnect_delay": 0}
        if cfg.transport == "serial":
            return AsyncModbusSerialClient(
                cfg.port,
                framer=FramerType.RTU,
                baudrate=cfg.baudrate,
                bytesize=8,
                parity=cfg.parity,
                stopbits=2 if cfg.parity == "N" else 1,
                **common,
            )
        framer = FramerType.RTU if cfg.transport == "rtu_over_tcp" else FramerType.SOCKET
        return AsyncModbusTcpClient(
            cfg.host, port=cfg.tcp_port or 502, framer=framer, **common
        )

    def _drop(self) -> None:
        client, self._client = self._client, None
        if client is not None:
            try:
                client.close()
            except Exception:  # noqa: BLE001 - already failing, close best-effort
                pass

    async def _ensure(self) -> Any:
        if self._client is None:
            self._client = self._build()
        if not self._client.connected and not await self._client.connect():
            self._drop()
            raise SabikModbusError("Could not connect to the unit")
        return self._client

    async def _call(self, method: str, *args: Any, **kwargs: Any) -> Any:
        """Run one request, mapping every failure to SabikModbusError."""
        try:
            client = await self._ensure()
            # pymodbus 3.10+ calls the unit address device_id (was slave).
            response = await getattr(client, method)(
                *args, device_id=self._settings.slave, **kwargs
            )
        except SabikModbusError:
            raise
        except (ModbusException, OSError, asyncio.TimeoutError):
            self._drop()
            raise SabikModbusError("No response from the unit") from None
        if response.isError():
            self._drop()
            raise SabikModbusError("The unit returned an error")
        return response

    async def async_read(self, plan: Iterable[ReadBlock]) -> RawRegisters:
        """Read every block in the plan."""
        methods = {
            "di": "read_discrete_inputs",
            "coil": "read_coils",
            "ir": "read_input_registers",
            "hr": "read_holding_registers",
        }
        raw = RawRegisters(di={}, coil={}, ir={}, hr={})
        async with self._lock:
            for block in plan:
                response = await self._call(
                    methods[block.kind], block.address, count=block.count
                )
                # Bit reads come back padded to a multiple of 8.
                values = (
                    response.bits if block.kind in ("di", "coil") else response.registers
                )[: block.count]
                getattr(raw, block.kind).update(
                    zip(range(block.address, block.address + block.count), values)
                )
        return raw

    async def async_write_coil(self, address: int, value: bool) -> None:
        async with self._lock:
            await self._call("write_coil", address, value)

    async def async_write_register(self, address: int, value: int) -> None:
        async with self._lock:
            await self._call("write_register", address, value)

    async def async_write_registers(self, address: int, values: list[int]) -> None:
        async with self._lock:
            await self._call("write_registers", address, values)

    async def async_close(self) -> None:
        async with self._lock:
            self._drop()


def create_client(settings: ConnectionSettings) -> SabikClient:
    """Factory used by the rest of the integration (patched in tests)."""
    return SabikClient(settings)

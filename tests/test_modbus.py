"""Tests for the pymodbus client wrapper, against an in-process server."""

from __future__ import annotations

import asyncio
import socket
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pymodbus.framer import FramerType
from pymodbus.server import ModbusTcpServer
from pymodbus.simulator import DataType, SimData, SimDevice

from custom_components.sabik import modbus
from custom_components.sabik.modbus import ConnectionSettings, SabikClient, SabikModbusError
from custom_components.sabik.registers import READ_PLAN

SERVER_FRAMERS = {"rtu_over_tcp": FramerType.RTU, "tcp": FramerType.SOCKET}


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _device() -> SimDevice:
    # Non-shared blocks, in pymodbus order: coils, discrete inputs, holding, input.
    coils = [SimData(0, values=[n == 9 for n in range(200)], datatype=DataType.BITS)]
    discrete = [SimData(0, count=200, values=False, datatype=DataType.BITS)]
    holding = [
        SimData(0, count=132, values=0, datatype=DataType.REGISTERS),
        SimData(132, values=1, datatype=DataType.REGISTERS),
        SimData(133, count=67, values=0, datatype=DataType.REGISTERS),
    ]
    inputs = [
        SimData(0, count=25, values=0, datatype=DataType.REGISTERS),
        SimData(25, values=215, datatype=DataType.REGISTERS),
        SimData(26, count=174, values=0, datatype=DataType.REGISTERS),
    ]
    return SimDevice(1, simdata=(coils, discrete, holding, inputs))


class Server:
    """Start and stop a pymodbus TCP server on a fixed local port."""

    def __init__(self, transport: str, port: int) -> None:
        self.transport = transport
        self.port = port
        self._server: ModbusTcpServer | None = None

    async def start(self) -> None:
        self._server = ModbusTcpServer(
            _device(),
            framer=SERVER_FRAMERS[self.transport],
            address=("127.0.0.1", self.port),
        )
        await self._server.serve_forever(background=True)

    async def stop(self) -> None:
        if self._server is not None:
            await self._server.shutdown()
            self._server = None
            await asyncio.sleep(0.1)


@pytest.fixture(params=["rtu_over_tcp", "tcp"])
async def server(request, socket_enabled):
    srv = Server(request.param, _free_port())
    await srv.start()
    yield srv
    await srv.stop()


@pytest.fixture
async def client(server):
    settings = ConnectionSettings(
        transport=server.transport, host="127.0.0.1", tcp_port=server.port, port=None
    )
    sabik = SabikClient(settings)
    yield sabik
    await sabik.async_close()


async def test_read_plan(client):
    raw = await client.async_read(READ_PLAN)
    assert raw.ir[25] == 215
    assert raw.coil[9] is True
    assert raw.hr[132] == 1
    for block in READ_PLAN:
        values = getattr(raw, block.kind)
        for address in range(block.address, block.address + block.count):
            assert address in values


async def test_writes_round_trip(client):
    await client.async_write_coil(17, True)
    await client.async_write_register(132, 3)
    await client.async_write_registers(48, [7, 11, 2026, 14, 3, 9])
    raw = await client.async_read(READ_PLAN)
    assert raw.coil[17] is True
    assert raw.hr[132] == 3
    assert [raw.hr[a] for a in range(48, 54)] == [7, 11, 2026, 14, 3, 9]


async def test_concurrent_calls_serialized(client):
    jobs = [client.async_read(READ_PLAN) for _ in range(10)]
    jobs += [client.async_write_register(132, n) for n in range(10)]
    results = await asyncio.gather(*jobs)
    assert len(results) == 20


async def test_server_down_raises_then_recovers(server, client):
    await client.async_read(READ_PLAN)
    await server.stop()
    with pytest.raises(SabikModbusError):
        await client.async_read(READ_PLAN)
    await server.start()
    raw = await client.async_read(READ_PLAN)
    assert raw.ir[25] == 215


async def test_serial_settings():
    fake = MagicMock()
    fake.connected = False
    fake.connect = AsyncMock(return_value=False)
    with patch.object(modbus, "AsyncModbusSerialClient", return_value=fake) as cls:
        sabik = SabikClient(
            ConnectionSettings(transport="serial", port="/dev/ttyUSB0", host=None, tcp_port=None, parity="N")
        )
        with pytest.raises(SabikModbusError):
            await sabik.async_write_register(1, 1)
    kwargs = cls.call_args.kwargs
    assert cls.call_args.args == ("/dev/ttyUSB0",) or kwargs.get("port") == "/dev/ttyUSB0"
    assert kwargs["baudrate"] == 19200
    assert kwargs["parity"] == "N"
    assert kwargs["stopbits"] == 2
    assert kwargs["bytesize"] == 8

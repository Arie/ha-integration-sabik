"""The hardware probe CLI, run against the in-process server."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import sabik_probe  # noqa: E402

from .test_modbus import Server, _free_port  # noqa: E402


@pytest.fixture
async def tcp_server(socket_enabled):
    srv = Server("tcp", _free_port())
    await srv.start()
    yield srv
    await srv.stop()


def _argv(srv, *cmd):
    return ["--transport", "tcp", "--host", "127.0.0.1", "--tcp-port", str(srv.port), *cmd]


async def test_read_and_writes(tcp_server, capsys):
    args = sabik_probe._parser().parse_args(_argv(tcp_server, "read"))
    await sabik_probe._run(args)
    out = capsys.readouterr().out
    assert "outdoor_air_temperature" in out and "full pass:" in out

    for cmd in (("coil", "16", "1"), ("reg", "67", "30"), ("regs", "48", "7", "11", "2026", "14", "3", "9")):
        await sabik_probe._run(sabik_probe._parser().parse_args(_argv(tcp_server, *cmd)))
    out = capsys.readouterr().out
    assert "read back coil 16 = 1" in out
    assert "read back hr 67 = 30" in out
    assert "[7, 11, 2026, 14, 3, 9]" in out

"""Hardware probe for the Sabik unit; reads and writes single items over Modbus."""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from custom_components.sabik.modbus import (  # noqa: E402
    ConnectionSettings,
    ReadBlock,
    SabikModbusError,
    create_client,
)
from custom_components.sabik.registers import READ_PLAN, decode  # noqa: E402

WATCH_INTERVAL = 5


def _compact(values: dict) -> str:
    """Render ``{addr: value}`` as ``addr=value`` pairs, with runs collapsed."""
    items = sorted(values.items())
    out: list[str] = []
    i = 0
    while i < len(items):
        j = i
        while j + 1 < len(items) and items[j + 1][0] == items[j][0] + 1:
            j += 1
        chunk = [int(v) for _, v in items[i : j + 1]]
        start = items[i][0]
        out.append(f"{start}..{items[j][0]}={chunk}" if j > i else f"{start}={chunk[0]}")
        i = j + 1
    return " ".join(out)


async def _read(client):
    start = time.monotonic()
    raw = await client.async_read(READ_PLAN)
    return raw, time.monotonic() - start


async def cmd_read(client, args) -> None:
    raw, elapsed = await _read(client)
    for kind in ("di", "coil", "ir", "hr"):
        print(f"{kind.upper():4} {_compact(getattr(raw, kind))}")
    print()
    data = decode(raw)
    for field in dataclasses.fields(data):
        print(f"{field.name}: {getattr(data, field.name)}")
    print(f"\nfull pass: {elapsed:.2f} s")


async def cmd_watch(client, args) -> None:
    previous: dict | None = None
    while True:
        raw, _ = await _read(client)
        current = dataclasses.asdict(decode(raw))
        stamp = datetime.now().strftime("%H:%M:%S")
        if previous is None:
            print(f"{stamp} watching (baseline taken)")
        else:
            for name, value in current.items():
                if value != previous[name]:
                    print(f"{stamp} {name}: {previous[name]} -> {value}")
        previous = current
        await asyncio.sleep(WATCH_INTERVAL)


async def _read_back(client, kind: str, address: int, count: int = 1) -> list:
    raw = await client.async_read([ReadBlock(kind, address, count)])
    return [int(v) for v in getattr(raw, kind).values()]


async def cmd_coil(client, args) -> None:
    await client.async_write_coil(args.addr, bool(args.value))
    print(f"wrote coil {args.addr} = {args.value}")
    print(f"read back coil {args.addr} = {(await _read_back(client, 'coil', args.addr))[0]}")


async def cmd_reg(client, args) -> None:
    await client.async_write_register(args.addr, args.value)
    print(f"wrote hr {args.addr} = {args.value}")
    print(f"read back hr {args.addr} = {(await _read_back(client, 'hr', args.addr))[0]}")


async def cmd_regs(client, args) -> None:
    await client.async_write_registers(args.addr, args.values)
    print(f"wrote hr {args.addr}..{args.addr + len(args.values) - 1} = {args.values}")
    print(f"read back hr {args.addr} = {await _read_back(client, 'hr', args.addr, len(args.values))}")


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Probe a Sabik unit over Modbus.")
    p.add_argument("--port", help="serial device path (selects the serial transport)")
    p.add_argument("--host")
    p.add_argument("--tcp-port", type=int, default=502)
    p.add_argument("--transport", choices=("rtu_over_tcp", "tcp"), default="rtu_over_tcp")
    p.add_argument("--slave", type=int, default=1)
    p.add_argument("--baudrate", type=int, default=19200)
    p.add_argument("--parity", choices=("E", "O", "N"), default="E")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("read").set_defaults(func=cmd_read)
    sub.add_parser("watch").set_defaults(func=cmd_watch)
    c = sub.add_parser("coil")
    c.add_argument("addr", type=int)
    c.add_argument("value", type=int, choices=(0, 1))
    c.set_defaults(func=cmd_coil)
    r = sub.add_parser("reg")
    r.add_argument("addr", type=int)
    r.add_argument("value", type=int)
    r.set_defaults(func=cmd_reg)
    rs = sub.add_parser("regs")
    rs.add_argument("addr", type=int)
    rs.add_argument("values", type=int, nargs="+")
    rs.set_defaults(func=cmd_regs)
    return p


async def _run(args) -> None:
    if args.port:
        settings = ConnectionSettings(
            transport="serial", port=args.port, baudrate=args.baudrate,
            parity=args.parity, slave=args.slave,
        )
    elif args.host:
        settings = ConnectionSettings(
            transport=args.transport, host=args.host, tcp_port=args.tcp_port,
            slave=args.slave,
        )
    else:
        raise SabikModbusError("give --port or --host")
    client = create_client(settings)
    try:
        await args.func(client, args)
    finally:
        await client.async_close()


def main() -> int:
    args = _parser().parse_args()
    try:
        asyncio.run(_run(args))
    except KeyboardInterrupt:
        return 0
    except (SabikModbusError, OSError) as err:
        print(f"error: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Poll all known MIoT properties of chunmi.mfcp.c3os and append them to a JSONL file.

Read-only: only sends `get_properties`. Run it alongside every test cook.

    python tools/prop_logger.py -o research/private/logs/e1.jsonl

IP and token come from --ip/--token or OC_DEVICE_IP/OC_DEVICE_TOKEN.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from miio import Device

from opencook.drivers.xiaomi_c3os.protocol import device_id, read_properties


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ip", default=os.environ.get("OC_DEVICE_IP"))
    parser.add_argument("--token", default=os.environ.get("OC_DEVICE_TOKEN"))
    parser.add_argument("-i", "--interval", type=float, default=1.0, help="seconds between polls")
    parser.add_argument(
        "-o", "--output", type=Path, help="JSONL file to append to (default: stdout)"
    )
    parser.add_argument(
        "-n", "--count", type=int, default=0, help="stop after N polls (0 = forever)"
    )
    parser.add_argument(
        "--changes-only", action="store_true", help="only write a line when a value changed"
    )
    args = parser.parse_args()
    if not args.ip or not args.token:
        parser.error(
            "device IP and token are required (--ip/--token or OC_DEVICE_IP/OC_DEVICE_TOKEN)"
        )
    return args


def main() -> int:
    args = parse_args()
    device = Device(args.ip, args.token)
    did = device_id(device)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
    out = args.output.open("a", encoding="utf-8") if args.output else sys.stdout

    previous: dict[str, Any] | None = None
    polls = 0
    try:
        while not args.count or polls < args.count:
            started = time.monotonic()
            record: dict[str, Any] = {"ts": datetime.now(UTC).isoformat(timespec="milliseconds")}
            try:
                record["props"] = read_properties(device, did)
            # python-miio raises TypeError instead of DeviceException on undecodable replies.
            except Exception as exc:
                record["error"] = repr(exc)
            polls += 1

            props = record.get("props")
            if not args.changes_only or props is None or props != previous:
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
                out.flush()
            if props is not None:
                previous = props

            time.sleep(max(0.0, args.interval - (time.monotonic() - started)))
    except KeyboardInterrupt:
        pass
    finally:
        if args.output:
            out.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

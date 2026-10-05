"""Read-only miIO access to chunmi.mfcp.c3os. See docs/protocol/xiaomi-c3os.md.

Only `get_properties` is sent. Writes and actions are acknowledged by the device but have no
effect (experiment E6), so this module deliberately offers none.
"""

from __future__ import annotations

from typing import Any

from miio import Device

# (siid, piid) of every readable property, including the reserved siid 4 piid 6-9.
PROPERTIES: tuple[tuple[int, int], ...] = (
    *((2, piid) for piid in (1, 2, 3, 4, 5, 10)),
    (3, 1),
    (3, 2),
    *((4, piid) for piid in range(3, 15)),
)
CHUNK_SIZE = 10


def device_id(device: Device) -> str:
    """The device rejects every property request (-4007) unless `did` is its real device id."""
    raw = device.send_handshake().header.value.device_id
    return str(int.from_bytes(raw, "big"))


def read_properties(device: Device, did: str, retry_count: int = 1) -> dict[str, Any]:
    """Return all properties keyed as "siid.piid"; failed reads map to {"code": <error>}."""
    values: dict[str, Any] = {}
    for start in range(0, len(PROPERTIES), CHUNK_SIZE):
        chunk = PROPERTIES[start : start + CHUNK_SIZE]
        request = [{"did": did, "siid": siid, "piid": piid} for siid, piid in chunk]
        for item in device.send("get_properties", request, retry_count=retry_count):
            key = f"{item['siid']}.{item['piid']}"
            values[key] = item["value"] if item.get("code") == 0 else {"code": item.get("code")}
    return values

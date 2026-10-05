from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from miio import Device, DeviceException

from opencook.drivers.base import CookerState
from opencook.drivers.xiaomi_c3os.protocol import device_id, read_properties

STATUS_LABELS = {
    0: "Standby",
    1: "Cooking",
    3: "Paused",
    6: "Sleep",
    8: "Error",
    11: "Complete",
}
MODE_LABELS = {0: "Stop", 1: "Stir-fry", 2: "Steam", 3: "Stew", 4: "Warm", 5: "Other"}
COOK_TYPE_LABELS = {0: "Official", 1: "Single", 2: "Mutable", 4: "Recipe"}


def _int(props: dict[str, Any], key: str) -> int | None:
    value = props.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def state_from_props(props: dict[str, Any], updated_at: datetime) -> CookerState:
    status = _int(props, "2.1")
    mode = _int(props, "2.2")
    cook_type = _int(props, "4.4")
    cook_name = props.get("4.5")
    return CookerState(
        reachable=True,
        updated_at=updated_at,
        status=status,
        status_label=STATUS_LABELS.get(status) if status is not None else None,
        mode=mode,
        mode_label=MODE_LABELS.get(mode) if mode is not None else None,
        # 2.3 left-time stays 0; 4.14 is the one that counts down (experiments E1/E4).
        remaining_s=_int(props, "4.14"),
        fault=_int(props, "2.5"),
        cook_id=_int(props, "4.3"),
        cook_type=cook_type,
        cook_type_label=COOK_TYPE_LABELS.get(cook_type) if cook_type is not None else None,
        cook_name=cook_name if isinstance(cook_name, str) and cook_name else None,
        raw=props,
    )


class XiaomiC3osReader:
    """Polls the device read-only. In standby it leaves the WLAN, so unreachable is normal."""

    def __init__(self, ip: str, token: str, timeout: float = 3.0) -> None:
        self._device = Device(ip, token, timeout=timeout)
        self._did: str | None = None
        self._lock = asyncio.Lock()

    def _read_sync(self) -> dict[str, Any]:
        if self._did is None:
            self._did = device_id(self._device)
        return read_properties(self._device, self._did)

    async def read_state(self) -> CookerState:
        async with self._lock:
            try:
                props = await asyncio.to_thread(self._read_sync)
            except DeviceException:
                # Redo the handshake after the device comes back from standby.
                self._did = None
                return CookerState(reachable=False, updated_at=datetime.now(UTC))
        return state_from_props(props, datetime.now(UTC))

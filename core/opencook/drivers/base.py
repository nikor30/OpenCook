"""Driver-neutral types. The full CookerDriver protocol follows in phase 4 (KICKSTART.md)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

from pydantic import BaseModel


class CookerState(BaseModel):
    reachable: bool
    updated_at: datetime
    status: int | None = None
    status_label: str | None = None
    mode: int | None = None
    mode_label: str | None = None
    remaining_s: int | None = None
    fault: int | None = None
    cook_id: int | None = None
    cook_type: int | None = None
    cook_type_label: str | None = None
    cook_name: str | None = None
    raw: dict[str, Any] = {}


class CookerReader(Protocol):
    """Read-only view of a cooker; it cannot change anything on the device."""

    async def read_state(self) -> CookerState: ...

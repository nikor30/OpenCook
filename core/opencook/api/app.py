"""Read-only status API and web view. Start with:

uvicorn --factory opencook.api.app:create_app --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import FastAPI
from fastapi.responses import FileResponse

from opencook.drivers.base import CookerReader, CookerState
from opencook.history import HistoryStore, SessionTracker, Stats

STATIC_DIR = Path(__file__).parent / "static"
log = logging.getLogger(__name__)
# Cooking time of an open session is persisted at most this often (spares the SD card).
CHECKPOINT_INTERVAL = timedelta(seconds=60)


class StatePoller:
    def __init__(
        self,
        reader: CookerReader,
        store: HistoryStore,
        interval_s: float,
        offline_interval_s: float,
    ) -> None:
        self._reader = reader
        self._store = store
        self._tracker = SessionTracker(store.open_session())
        self._last_checkpoint = datetime.now(UTC)
        self._interval_s = interval_s
        self._offline_interval_s = offline_interval_s
        self.latest = CookerState(reachable=False, updated_at=datetime.now(UTC))

    async def poll_once(self) -> CookerState:
        self.latest = await self._reader.read_state()
        self._record(self.latest)
        return self.latest

    def _record(self, state: CookerState) -> None:
        changed = self._tracker.update(state)
        current = self._tracker.current
        if current is not None and state.updated_at - self._last_checkpoint > CHECKPOINT_INTERVAL:
            changed.append(current)
        for session in {id(s): s for s in changed}.values():
            self._store.save(session)
            self._last_checkpoint = state.updated_at

    async def run(self) -> None:
        while True:
            try:
                state = await self.poll_once()
            except Exception:
                log.exception("polling the device failed")
                state = self.latest
            await asyncio.sleep(self._interval_s if state.reachable else self._offline_interval_s)


def _reader_from_env() -> CookerReader:
    from opencook.drivers.xiaomi_c3os import XiaomiC3osReader

    return XiaomiC3osReader(os.environ["OC_DEVICE_IP"], os.environ["OC_DEVICE_TOKEN"])


def _store_from_env() -> HistoryStore:
    db_path = os.environ.get("OC_DB_PATH")
    return HistoryStore.from_path(Path(db_path)) if db_path else HistoryStore.in_memory()


def create_app(reader: CookerReader | None = None, store: HistoryStore | None = None) -> FastAPI:
    store = store or _store_from_env()
    timezone = ZoneInfo(os.environ.get("OC_TIMEZONE", "Europe/Berlin"))
    poller = StatePoller(
        reader or _reader_from_env(),
        store,
        interval_s=float(os.environ.get("OC_POLL_INTERVAL", "1")),
        offline_interval_s=float(os.environ.get("OC_OFFLINE_POLL_INTERVAL", "10")),
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        task = asyncio.create_task(poller.run())
        try:
            yield
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    app = FastAPI(title="OpenCook", lifespan=lifespan)

    @app.get("/api/state")
    async def get_state() -> CookerState:
        return poller.latest

    @app.get("/api/stats")
    async def get_stats() -> Stats:
        return store.stats(timezone)

    @app.get("/api/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/stats", include_in_schema=False)
    async def stats_page() -> FileResponse:
        return FileResponse(STATIC_DIR / "stats.html")

    return app

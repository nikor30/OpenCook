"""Status API and web view. The cooker is only ever read; the only writable thing is the
local configuration (device address, token, UI options). Start with:

uvicorn --factory opencook.api.app:create_app --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
from collections.abc import AsyncIterator, Callable, Coroutine
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from opencook.drivers.base import CookerReader, CookerState
from opencook.history import HistoryStore, SessionTracker, Stats
from opencook.settings import DeviceSettings, SettingsStore, SettingsUpdate, SettingsView

STATIC_DIR = Path(__file__).parent / "static"
log = logging.getLogger(__name__)
# Cooking time of an open session is persisted at most this often (spares the SD card).
CHECKPOINT_INTERVAL = timedelta(seconds=60)

ReaderFactory = Callable[[DeviceSettings], CookerReader]


class UnconfiguredReader:
    """Used until a device address and token are set."""

    async def read_state(self) -> CookerState:
        return CookerState(reachable=False, updated_at=datetime.now(UTC))


def xiaomi_reader(settings: DeviceSettings) -> CookerReader:
    from opencook.drivers.xiaomi_c3os import XiaomiC3osReader

    return XiaomiC3osReader(settings.ip, settings.token)


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
        self._wake = asyncio.Event()
        self.latest = CookerState(reachable=False, updated_at=datetime.now(UTC))

    def set_reader(self, reader: CookerReader) -> None:
        self._reader = reader
        self._wake.set()

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
            delay = self._interval_s if state.reachable else self._offline_interval_s
            # A new reader (changed settings) is polled right away instead of after the delay.
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._wake.wait(), delay)
            self._wake.clear()


class SettingsResult(BaseModel):
    settings: SettingsView
    reachable: bool


def _store_from_env() -> HistoryStore:
    db_path = os.environ.get("OC_DB_PATH")
    return HistoryStore.from_path(Path(db_path)) if db_path else HistoryStore.in_memory()


def create_app(
    *,
    reader_factory: ReaderFactory = xiaomi_reader,
    store: HistoryStore | None = None,
    settings_store: SettingsStore | None = None,
) -> FastAPI:
    store = store or _store_from_env()
    settings_store = settings_store or SettingsStore.from_env()
    timezone = ZoneInfo(os.environ.get("OC_TIMEZONE", "Europe/Berlin"))

    def make_reader(settings: DeviceSettings) -> CookerReader:
        return reader_factory(settings) if settings.configured else UnconfiguredReader()

    poller = StatePoller(
        make_reader(settings_store.load()),
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
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/api/state")
    async def get_state() -> CookerState:
        return poller.latest

    @app.get("/api/stats")
    async def get_stats() -> Stats:
        return store.stats(timezone)

    @app.get("/api/settings")
    async def get_settings() -> SettingsView:
        return SettingsView.of(settings_store.load())

    @app.put("/api/settings")
    async def put_settings(update: SettingsUpdate) -> SettingsResult:
        settings, connection_changed = settings_store.apply(update)
        if connection_changed:
            reader = make_reader(settings)
            poller.set_reader(reader)
            # Report right away whether the new address and token work.
            state = await reader.read_state()
            reachable = state.reachable
        else:
            reachable = poller.latest.reachable
        return SettingsResult(settings=SettingsView.of(settings), reachable=reachable)

    @app.get("/api/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    pages = {"/": "index.html", "/stats": "stats.html", "/settings": "settings.html"}
    for path, filename in pages.items():
        app.add_api_route(path, _page(filename), include_in_schema=False, methods=["GET"])

    return app


def _page(filename: str) -> Callable[[], Coroutine[None, None, FileResponse]]:
    async def page() -> FileResponse:
        return FileResponse(STATIC_DIR / filename)

    return page

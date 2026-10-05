"""Turns the stream of polled states into cook sessions.

The device only reports *that* it runs (status 1 cooking, 3 paused) and which recipe is loaded,
so a session is: the device runs a recipe (or a manual "Handbuch" run) until it has been idle for
IDLE_GAP or a different recipe starts. Several machine steps of one recipe, and manual runs in
quick succession, therefore count as one session.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from opencook.drivers.base import CookerState

Outcome = Literal["running", "completed", "cancelled", "error"]

STATUS_COOKING = 1
STATUS_PAUSED = 3
STATUS_ERROR = 8
STATUS_COMPLETE = 11
RUNNING = {STATUS_COOKING, STATUS_PAUSED}

IDLE_GAP = timedelta(minutes=15)
# Polling gaps longer than this (device offline, core restarted) do not count as cooking time.
MAX_TICK = timedelta(seconds=10)


@dataclass
class CookSession:
    recipe_key: str
    name: str
    cook_id: int | None
    cook_type: int | None
    started_at: datetime
    last_running_at: datetime
    cooking_s: float = 0.0
    outcome: Outcome = "running"
    ended_at: datetime | None = None
    id: int | None = None


def recipe_key(state: CookerState) -> str:
    return f"{state.cook_type}:{state.cook_id}:{state.cook_name or ''}"


class SessionTracker:
    """Feed it every polled state; it returns the session that changed, if any."""

    def __init__(self, open_session: CookSession | None = None) -> None:
        self.current = open_session
        self._last_seen: datetime | None = None
        self._last_status: int | None = None

    def update(self, state: CookerState) -> list[CookSession]:
        now = state.updated_at
        changed: list[CookSession] = []
        running = state.reachable and state.status in RUNNING

        if running:
            if self.current is not None and self.current.recipe_key != recipe_key(state):
                changed.append(self._close(self.current))
            if self.current is None:
                self.current = CookSession(
                    recipe_key=recipe_key(state),
                    name=state.cook_name or "Unbekannt",
                    cook_id=state.cook_id,
                    cook_type=state.cook_type,
                    started_at=now,
                    last_running_at=now,
                )
                changed.append(self.current)
            session = self.current
            if (
                state.status == STATUS_COOKING
                and self._last_status == STATUS_COOKING
                and self._last_seen is not None
                and timedelta(0) < now - self._last_seen <= MAX_TICK
            ):
                session.cooking_s += (now - self._last_seen).total_seconds()
            session.last_running_at = now
            if session.outcome != "running":
                session.outcome = "running"
                changed.append(session)
        elif self.current is not None:
            session = self.current
            outcome = self._outcome_after_run(state)
            if outcome is not None and session.outcome != outcome:
                session.outcome = outcome
                changed.append(session)
            if now - session.last_running_at > IDLE_GAP:
                changed.append(self._close(session))

        self._last_seen = now
        self._last_status = state.status if state.reachable else None
        return list({id(s): s for s in changed}.values())  # dedupe, keep order

    def _outcome_after_run(self, state: CookerState) -> Outcome | None:
        if not state.reachable:
            return None
        if state.status == STATUS_COMPLETE:
            return "completed"
        if state.status == STATUS_ERROR:
            return "error"
        if self._last_status in RUNNING:
            # Straight from running to standby: stopped before the end.
            return "cancelled"
        return None

    def _close(self, session: CookSession) -> CookSession:
        if session.outcome == "running":
            session.outcome = "cancelled"
        session.ended_at = session.last_running_at
        self.current = None
        return session

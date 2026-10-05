"""Cook mode: walks through a recipe while the user operates the device.

The device cannot be started remotely, so for a machine step the user enters the shown settings
on the display and presses start. The run follows the device status: running → the step runs,
complete → the step is done and (with auto-advance) the next step is shown.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from opencook.drivers.base import CookerState
from opencook.recipes.models import MachineStep, Recipe, UserStep, WaitStep, WeighStep

Phase = Literal["ready", "running", "stopped", "done"]

STATUS_COOKING = 1
STATUS_PAUSED = 3
STATUS_STANDBY = 0
STATUS_COMPLETE = 11


class CookRun(BaseModel):
    recipe: Recipe
    started_at: datetime
    step_index: int = 0
    # ready: waiting for the user / device · running · stopped: device stopped early · done
    phase: Phase = "ready"
    phase_since: datetime
    auto_advance: bool = True
    finished: bool = False

    @classmethod
    def start(cls, recipe: Recipe, now: datetime) -> CookRun:
        run = cls(recipe=recipe, started_at=now, phase_since=now)
        run._enter_step(now)
        return run

    @property
    def step(self) -> MachineStep | UserStep | WeighStep | WaitStep:
        return self.recipe.steps[self.step_index]

    def _set_phase(self, phase: Phase, now: datetime) -> None:
        self.phase = phase
        self.phase_since = now

    def _enter_step(self, now: datetime) -> None:
        # A wait step's timer starts as soon as it is shown.
        self._set_phase("running" if isinstance(self.step, WaitStep) else "ready", now)

    def next(self, now: datetime) -> None:
        if self.step_index + 1 < len(self.recipe.steps):
            self.step_index += 1
            self._enter_step(now)
        else:
            self.finished = True
            self._set_phase("done", now)

    def back(self, now: datetime) -> None:
        self.finished = False
        self.step_index = max(0, self.step_index - 1)
        self._enter_step(now)

    def _complete_step(self, now: datetime) -> None:
        self._set_phase("done", now)
        if self.auto_advance:
            self.next(now)

    def update(self, state: CookerState, now: datetime) -> bool:
        """Follow the device; returns whether the run changed."""
        if self.finished:
            return False
        before = (self.step_index, self.phase, self.finished)
        step = self.step

        if isinstance(step, MachineStep) and state.reachable:
            running = state.status in (STATUS_COOKING, STATUS_PAUSED)
            if self.phase in ("ready", "stopped") and running:
                self._set_phase("running", now)
            elif self.phase == "running" and state.status == STATUS_COMPLETE:
                self._complete_step(now)
            elif self.phase == "running" and state.status == STATUS_STANDBY:
                # Stopped on the display before the end; the user decides how to go on.
                self._set_phase("stopped", now)
        elif isinstance(step, WaitStep) and self.phase == "running":
            if (now - self.phase_since).total_seconds() >= step.duration_s:
                self._complete_step(now)

        return before != (self.step_index, self.phase, self.finished)

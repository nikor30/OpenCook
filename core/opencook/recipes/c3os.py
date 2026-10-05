"""What a recipe means on the Xiaomi Smart Cooking Robot (chunmi.mfcp.c3os).

The device cannot be controlled remotely (experiments E6/E7), so machine steps are entered in its
manual mode by hand. These limits are those of the manual mode (KICKSTART.md §1) and are checked
before cooking; recipe data cannot override them.
"""

from __future__ import annotations

from pydantic import BaseModel

from opencook.recipes.models import MachineParams, MachineStep, Recipe

MIN_TEMP_C = 35
MAX_MANUAL_TEMP_C = 150
SPEED_LEVELS = 20
HOT_TEMP_C = 80
MAX_SPEED_WHEN_HOT = 6


class ManualSettings(BaseModel):
    """The values to enter on the device display for one machine step."""

    temp_c: int | None
    duration_s: int
    speed_level: int | None
    reverse: bool


def speed_level(params: MachineParams) -> int | None:
    """Map the recipe's speed scale to the device's 20 levels.

    Assumes the scales are linear; the real mapping is still open (Q4)."""
    if params.speed is None or params.speed.level == 0:
        return None
    return max(1, min(SPEED_LEVELS, round(params.speed.level / params.speed.of * SPEED_LEVELS)))


def manual_settings(step: MachineStep) -> ManualSettings:
    params = step.machine
    return ManualSettings(
        temp_c=params.temp_c or None,
        duration_s=params.duration_s,
        speed_level=speed_level(params),
        reverse=params.speed is not None and params.speed.direction == "reverse",
    )


def problems(recipe: Recipe) -> list[str]:
    """Reasons why the recipe cannot be cooked on this device, empty if it can."""
    found: list[str] = []
    for number, step in enumerate(recipe.steps, start=1):
        if not isinstance(step, MachineStep):
            continue
        settings = manual_settings(step)
        name = f"Schritt {number}"
        if settings.temp_c is not None and not MIN_TEMP_C <= settings.temp_c <= MAX_MANUAL_TEMP_C:
            found.append(
                f"{name}: {settings.temp_c} °C – im manuellen Modus sind "
                f"{MIN_TEMP_C}–{MAX_MANUAL_TEMP_C} °C möglich"
            )
        if (
            settings.temp_c is not None
            and settings.temp_c > HOT_TEMP_C
            and (settings.speed_level or 0) > MAX_SPEED_WHEN_HOT
        ):
            found.append(
                f"{name}: Stufe {settings.speed_level} – über {HOT_TEMP_C} °C "
                f"ist höchstens Stufe {MAX_SPEED_WHEN_HOT} erlaubt"
            )
    return found

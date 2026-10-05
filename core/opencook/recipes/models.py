"""OpenCook Recipe Format (ORF) v1 – the contract for drivers, converters, API and UI.

`schemas/orf-v1.json` is generated from these models (`python -m opencook.recipes.schema`).
Machine steps are device-neutral; device limits are checked separately (see `c3os.py`).
"""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

StepId = Annotated[str, Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")]


class OrfModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Ingredient(OrfModel):
    id: StepId
    name: str = Field(min_length=1, max_length=120)
    amount: float | None = Field(default=None, ge=0)
    unit: str | None = Field(default=None, max_length=20)


class Speed(OrfModel):
    """Stirring speed as `level` on a scale of `of` steps, so recipes from devices with other
    scales can be mapped (e.g. Thermomix 1–10, Bimbi 1–20)."""

    level: int = Field(ge=0, le=100)
    of: int = Field(default=20, ge=1, le=100)
    direction: Literal["forward", "reverse"] = "forward"

    @model_validator(mode="after")
    def _level_within_scale(self) -> Speed:
        if self.level > self.of:
            raise ValueError(f"Stufe {self.level} liegt über der Skala von {self.of}")
        return self


class MachineParams(OrfModel):
    temp_c: int | None = Field(default=None, ge=0, le=250, description="None: no heating")
    duration_s: int = Field(ge=1, le=14400)
    speed: Speed | None = None
    accessory: Literal["none", "whisk", "steamer", "basket"] = "none"


class StepBase(OrfModel):
    id: StepId
    title: str | None = Field(default=None, max_length=120)
    text: str | None = Field(default=None, max_length=2000)


class MachineStep(StepBase):
    kind: Literal["machine"] = "machine"
    machine: MachineParams


class UserStep(StepBase):
    kind: Literal["user"] = "user"


class WeighStep(StepBase):
    kind: Literal["weigh"] = "weigh"
    ingredient: StepId | None = None
    target_g: int = Field(ge=1, le=5000)


class WaitStep(StepBase):
    kind: Literal["wait"] = "wait"
    duration_s: int = Field(ge=1, le=86400)


Step = Annotated[MachineStep | UserStep | WeighStep | WaitStep, Field(discriminator="kind")]


class Source(OrfModel):
    type: Literal["manual", "converted"] = "manual"
    origin: str | None = None
    license: str | None = None


class Recipe(OrfModel):
    orf_version: Literal[1] = 1
    id: UUID = Field(default_factory=uuid4)
    title: str = Field(min_length=1, max_length=200)
    servings: int | None = Field(default=None, ge=1, le=100)
    tags: list[str] = []
    images: list[str] = []
    source: Source = Source()
    ingredients: list[Ingredient] = []
    steps: list[Step] = Field(min_length=1)

    @model_validator(mode="after")
    def _references_resolve(self) -> Recipe:
        for kind, ids in (
            ("Zutat", [i.id for i in self.ingredients]),
            ("Schritt", [s.id for s in self.steps]),
        ):
            duplicates = {i for i in ids if ids.count(i) > 1}
            if duplicates:
                raise ValueError(f"{kind}-ID mehrfach vergeben: {', '.join(sorted(duplicates))}")
        ingredient_ids = {i.id for i in self.ingredients}
        for step in self.steps:
            if (
                isinstance(step, WeighStep)
                and step.ingredient
                and step.ingredient not in ingredient_ids
            ):
                raise ValueError(f"Schritt {step.id}: unbekannte Zutat {step.ingredient}")
        return self

"""SQLite persistence for ORF recipes and the active cook run."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import Engine
from sqlmodel import Field, Session, SQLModel, col, select

from opencook.db import make_engine
from opencook.recipes.models import MachineStep, Recipe
from opencook.runner.run import CookRun


class RecipeRow(SQLModel, table=True):
    __tablename__ = "recipe"

    id: str = Field(primary_key=True)
    title: str = Field(index=True)
    body: str
    updated_at: datetime


class CookRunRow(SQLModel, table=True):
    """At most one active cook run (id 1)."""

    __tablename__ = "cook_run"

    id: int = Field(default=1, primary_key=True)
    body: str


class RecipeSummary(BaseModel):
    id: UUID
    title: str
    servings: int | None
    tags: list[str]
    steps: int
    machine_steps: int
    duration_s: int
    updated_at: datetime


def summarize(recipe: Recipe, updated_at: datetime) -> RecipeSummary:
    machine = [s for s in recipe.steps if isinstance(s, MachineStep)]
    return RecipeSummary(
        id=recipe.id,
        title=recipe.title,
        servings=recipe.servings,
        tags=recipe.tags,
        steps=len(recipe.steps),
        machine_steps=len(machine),
        duration_s=sum(s.machine.duration_s for s in machine),
        updated_at=updated_at if updated_at.tzinfo else updated_at.replace(tzinfo=UTC),
    )


class RecipeStore:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        SQLModel.metadata.create_all(engine)

    @classmethod
    def in_memory(cls) -> RecipeStore:
        return cls(make_engine(None))

    def list(self) -> list[RecipeSummary]:
        with Session(self._engine) as db:
            rows = db.exec(select(RecipeRow).order_by(col(RecipeRow.title))).all()
            return [summarize(Recipe.model_validate_json(r.body), r.updated_at) for r in rows]

    def get(self, recipe_id: UUID) -> Recipe | None:
        with Session(self._engine) as db:
            row = db.get(RecipeRow, str(recipe_id))
            return Recipe.model_validate_json(row.body) if row else None

    def put(self, recipe: Recipe) -> None:
        with Session(self._engine) as db:
            row = db.get(RecipeRow, str(recipe.id)) or RecipeRow(
                id=str(recipe.id), title="", body="", updated_at=datetime.now(UTC)
            )
            row.title = recipe.title
            row.body = recipe.model_dump_json()
            row.updated_at = datetime.now(UTC)
            db.add(row)
            db.commit()

    def delete(self, recipe_id: UUID) -> bool:
        with Session(self._engine) as db:
            row = db.get(RecipeRow, str(recipe_id))
            if row is None:
                return False
            db.delete(row)
            db.commit()
            return True

    def load_run(self) -> CookRun | None:
        with Session(self._engine) as db:
            row = db.get(CookRunRow, 1)
            return CookRun.model_validate_json(row.body) if row else None

    def save_run(self, run: CookRun | None) -> None:
        with Session(self._engine) as db:
            row = db.get(CookRunRow, 1)
            if run is None:
                if row is not None:
                    db.delete(row)
            else:
                row = row or CookRunRow(body="")
                row.body = run.model_dump_json()
                db.add(row)
            db.commit()

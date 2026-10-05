"""SQLite persistence for cook sessions and the statistics computed from them."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import UTC, date, datetime, timedelta, tzinfo
from pathlib import Path

from pydantic import BaseModel
from sqlalchemy import Engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Field, Session, SQLModel, col, create_engine, select

from opencook.history.tracker import CookSession, Outcome


class CookSessionRow(SQLModel, table=True):
    __tablename__ = "cook_session"

    id: int | None = Field(default=None, primary_key=True)
    recipe_key: str = Field(index=True)
    name: str
    cook_id: int | None = None
    cook_type: int | None = None
    started_at: datetime = Field(index=True)
    last_running_at: datetime
    ended_at: datetime | None = None
    cooking_s: float = 0.0
    outcome: str = "running"


class RecipeStats(BaseModel):
    name: str
    cook_id: int | None
    count: int
    completed: int
    cooking_s: float
    last_cooked_at: datetime


class DayCount(BaseModel):
    day: date
    count: int


class SessionOut(BaseModel):
    name: str
    cook_id: int | None
    started_at: datetime
    ended_at: datetime | None
    cooking_s: float
    outcome: str


class CleaningStats(BaseModel):
    total: int
    completed: int
    last_at: datetime | None
    cooks_since_last: int
    programs: list[RecipeStats]
    recent: list[SessionOut]


class Stats(BaseModel):
    """Cooking statistics; cleaning programs are only counted in `cleaning`."""

    total: int
    completed: int
    cooking_s: float
    recipes: list[RecipeStats]
    last_30_days: list[DayCount]
    by_hour: list[int]
    recent: list[SessionOut]
    cleaning: CleaningStats


# The device runs its cleaning programs like recipes (e.g. "Tiefenreinigung", cook-id 15,
# cook-type 0 like manual runs), so the name is the only way to tell them apart.
CLEANING_NAME_HINTS = ("reinig", "clean")


def is_cleaning(session: CookSession) -> bool:
    name = session.name.lower()
    return any(hint in name for hint in CLEANING_NAME_HINTS)


def _per_recipe(sessions: list[CookSession]) -> list[RecipeStats]:
    groups: dict[str, list[CookSession]] = defaultdict(list)
    for s in sessions:
        groups[s.recipe_key].append(s)
    return sorted(
        (
            RecipeStats(
                name=group[-1].name,
                cook_id=group[-1].cook_id,
                count=len(group),
                completed=sum(s.outcome == "completed" for s in group),
                cooking_s=sum(s.cooking_s for s in group),
                last_cooked_at=group[-1].started_at,
            )
            for group in groups.values()
        ),
        key=lambda r: (-r.count, -r.last_cooked_at.timestamp()),
    )


def _recent(sessions: list[CookSession], limit: int) -> list[SessionOut]:
    return [
        SessionOut(
            name=s.name,
            cook_id=s.cook_id,
            started_at=s.started_at,
            ended_at=s.ended_at,
            cooking_s=s.cooking_s,
            outcome=s.outcome,
        )
        for s in reversed(sessions[-limit:])
    ]


def _utc(value: datetime) -> datetime:
    # SQLite drops the timezone; everything is stored in UTC.
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _to_session(row: CookSessionRow) -> CookSession:
    return CookSession(
        id=row.id,
        recipe_key=row.recipe_key,
        name=row.name,
        cook_id=row.cook_id,
        cook_type=row.cook_type,
        started_at=_utc(row.started_at),
        last_running_at=_utc(row.last_running_at),
        ended_at=_utc(row.ended_at) if row.ended_at else None,
        cooking_s=row.cooking_s,
        outcome=row.outcome,  # type: ignore[arg-type]
    )


class HistoryStore:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        SQLModel.metadata.create_all(engine)

    @classmethod
    def from_path(cls, path: Path) -> HistoryStore:
        path.parent.mkdir(parents=True, exist_ok=True)
        return cls(create_engine(f"sqlite:///{path}"))

    @classmethod
    def in_memory(cls) -> HistoryStore:
        return cls(
            create_engine(
                "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
            )
        )

    def open_session(self) -> CookSession | None:
        with Session(self._engine) as db:
            row = db.exec(
                select(CookSessionRow)
                .where(col(CookSessionRow.ended_at).is_(None))
                .order_by(col(CookSessionRow.started_at).desc())
            ).first()
            return _to_session(row) if row else None

    def save(self, session: CookSession) -> None:
        with Session(self._engine) as db:
            row = db.get(CookSessionRow, session.id) if session.id is not None else None
            row = row or CookSessionRow(
                recipe_key=session.recipe_key,
                name=session.name,
                started_at=session.started_at,
                last_running_at=session.last_running_at,
            )
            row.cook_id = session.cook_id
            row.cook_type = session.cook_type
            row.last_running_at = session.last_running_at
            row.ended_at = session.ended_at
            row.cooking_s = session.cooking_s
            row.outcome = session.outcome
            db.add(row)
            db.commit()
            db.refresh(row)
            session.id = row.id

    def stats(self, tz: tzinfo = UTC, now: datetime | None = None) -> Stats:
        """Days and hours are counted in `tz` (the kitchen's local time)."""
        now = (now or datetime.now(UTC)).astimezone(tz)
        with Session(self._engine) as db:
            rows = list(db.exec(select(CookSessionRow).order_by(col(CookSessionRow.started_at))))
        all_sessions = [_to_session(r) for r in rows]
        sessions = [s for s in all_sessions if not is_cleaning(s)]
        cleanings = [s for s in all_sessions if is_cleaning(s)]
        local_starts = [s.started_at.astimezone(tz) for s in sessions]

        first_day = (now - timedelta(days=29)).date()
        per_day = Counter(d.date() for d in local_starts if d.date() >= first_day)
        by_hour = Counter(d.hour for d in local_starts)
        last_cleaning = cleanings[-1].started_at if cleanings else None

        return Stats(
            total=len(sessions),
            completed=sum(s.outcome == "completed" for s in sessions),
            cooking_s=sum(s.cooking_s for s in sessions),
            recipes=_per_recipe(sessions),
            last_30_days=[
                DayCount(day=first_day + timedelta(days=i), count=per_day[first_day + timedelta(i)])
                for i in range(30)
            ],
            by_hour=[by_hour[h] for h in range(24)],
            recent=_recent(sessions, 20),
            cleaning=CleaningStats(
                total=len(cleanings),
                completed=sum(s.outcome == "completed" for s in cleanings),
                last_at=last_cleaning,
                cooks_since_last=sum(
                    last_cleaning is None or s.started_at > last_cleaning for s in sessions
                ),
                programs=_per_recipe(cleanings),
                recent=_recent(cleanings, 10),
            ),
        )


__all__ = ["CleaningStats", "CookSessionRow", "HistoryStore", "Outcome", "Stats", "is_cleaning"]

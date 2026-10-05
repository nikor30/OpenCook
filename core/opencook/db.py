"""One SQLite database for history, recipes and the active cook run."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import Engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, create_engine


def make_engine(path: Path | None) -> Engine:
    """SQLite file at `path`, or an in-memory database shared across connections."""
    if path is None:
        engine = create_engine(
            "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
        )
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(f"sqlite:///{path}")
    SQLModel.metadata.create_all(engine)
    return engine

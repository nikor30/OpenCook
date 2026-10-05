import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from opencook.api.app import create_app
from opencook.drivers.base import CookerReader, CookerState
from opencook.history import HistoryStore
from opencook.recipes.models import Recipe
from opencook.recipes.store import RecipeStore
from opencook.runner.run import CookRun
from opencook.settings import DeviceSettings, SettingsStore

T0 = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)


def recipe(temp_c: int = 100) -> Recipe:
    return Recipe.model_validate(
        {
            "title": "Kartoffelsuppe",
            "steps": [
                {"id": "s1", "kind": "user", "text": "Kartoffeln in den Topf geben."},
                {
                    "id": "s2",
                    "kind": "machine",
                    "machine": {"temp_c": temp_c, "duration_s": 600, "speed": {"level": 2}},
                },
                {"id": "s3", "kind": "wait", "duration_s": 120},
                {"id": "s4", "kind": "user", "text": "Pürieren."},
            ],
        }
    )


def device(status: int | None, name: str = "Handbuch") -> CookerState:
    return CookerState(
        reachable=status is not None, updated_at=T0, status=status, cook_id=1, cook_name=name
    )


def at(seconds: float) -> datetime:
    return T0 + timedelta(seconds=seconds)


def test_machine_step_follows_the_device_and_advances() -> None:
    run = CookRun.start(recipe(), T0)
    run.next(at(1))  # user step done by hand
    assert (run.step_index, run.phase) == (1, "ready")

    assert run.update(device(1), at(10))
    assert run.phase == "running"
    assert not run.update(device(None), at(20))  # offline: keep running
    assert not run.update(device(3), at(30))  # paused is still running
    assert run.update(device(11), at(610))

    # complete → next step; a wait step's timer starts right away
    assert (run.step_index, run.phase) == (2, "running")
    assert not run.update(device(0), at(700))
    assert run.update(device(0), at(731))
    assert (run.step_index, run.phase) == (3, "ready")


def test_stopping_on_the_display_does_not_advance() -> None:
    run = CookRun.start(recipe(), T0)
    run.next(at(1))
    run.update(device(1), at(2))

    run.update(device(0), at(60))

    assert (run.step_index, run.phase) == (1, "stopped")
    run.update(device(1), at(70))
    assert run.phase == "running"


def test_without_auto_advance_the_step_waits_as_done() -> None:
    run = CookRun.start(recipe(), T0)
    run.auto_advance = False
    run.next(at(1))
    run.update(device(1), at(2))

    run.update(device(11), at(602))

    assert (run.step_index, run.phase) == (1, "done")


def test_last_step_finishes_the_run() -> None:
    run = CookRun.start(recipe(), T0)
    for i in range(4):
        run.next(at(i))

    assert run.finished
    assert not run.update(device(1), at(10))


class FakeReader:
    def __init__(self) -> None:
        self.state = device(0)

    async def read_state(self) -> CookerState:
        return self.state.model_copy(update={"updated_at": datetime.now(UTC)})


def client(tmp_path: Path, reader: FakeReader, history: HistoryStore | None = None) -> TestClient:
    settings = SettingsStore(tmp_path / "c.json", DeviceSettings(ip="192.0.2.1", token="ab" * 16))

    def factory(_: DeviceSettings) -> CookerReader:
        return reader

    return TestClient(
        create_app(
            reader_factory=factory,
            settings_store=settings,
            recipes=RecipeStore.in_memory(),
            store=history or HistoryStore.in_memory(),
        )
    )


def test_recipe_crud_and_cook_flow(tmp_path: Path) -> None:
    reader = FakeReader()
    body = recipe().model_dump(mode="json")

    with client(tmp_path, reader) as c:
        created = c.post("/api/recipes", json=body)
        recipe_id = body["id"]
        assert created.status_code == 201
        assert created.json()["problems"] == []
        assert c.post("/api/recipes", json=body).status_code == 409
        assert [r["title"] for r in c.get("/api/recipes").json()] == ["Kartoffelsuppe"]

        body["title"] = "Kartoffelsuppe mit Lauch"
        assert c.put(f"/api/recipes/{recipe_id}", json=body).status_code == 200

        assert c.get("/api/cook").json() is None
        started = c.post("/api/cook", json={"recipe_id": recipe_id}).json()
        assert started["run"]["step_index"] == 0
        assert c.post("/api/cook", json={"recipe_id": recipe_id}).status_code == 409

        view = c.post("/api/cook/next").json()
        assert view["settings"] == {
            "temp_c": 100,
            "duration_s": 600,
            "speed_level": 2,
            "reverse": False,
        }
        assert (
            c.put("/api/cook", json={"auto_advance": False}).json()["run"]["auto_advance"] is False
        )
        assert c.post("/api/cook/back").json()["run"]["step_index"] == 0

        assert c.delete("/api/cook").status_code == 204
        assert c.get("/api/cook").json() is None
        assert c.delete(f"/api/recipes/{recipe_id}").status_code == 204
        assert c.get(f"/api/recipes/{recipe_id}").status_code == 404


def test_cooking_refuses_recipes_outside_device_limits(tmp_path: Path) -> None:
    body = recipe(temp_c=170).model_dump(mode="json")

    with client(tmp_path, FakeReader()) as c:
        problems = c.post("/api/recipes", json=body).json()["problems"]
        response = c.post("/api/cook", json={"recipe_id": body["id"]})

    assert problems
    assert response.status_code == 409
    assert "170 °C" in response.json()["detail"]


def test_manual_runs_during_cook_mode_count_as_the_recipe(tmp_path: Path) -> None:
    reader = FakeReader()
    history = HistoryStore.in_memory()
    body = recipe().model_dump(mode="json")

    with client(tmp_path, reader, history) as c:
        c.post("/api/recipes", json=body)
        c.post("/api/cook", json={"recipe_id": body["id"]})
        c.post("/api/cook/next")
        reader.state = device(1)
        for _ in range(50):  # let the poller see the running device
            if c.get("/api/cook").json()["run"]["phase"] == "running":
                break
            time.sleep(0.1)

    assert [r.name for r in history.stats().recipes] == ["Kartoffelsuppe"]


def test_text_import_returns_a_preview_without_saving(tmp_path: Path) -> None:
    text = "Suppe\nZutaten\n500 ml Wasser\nZubereitung\n1. 10 Min./100°C/Stufe 1 kochen."

    with client(tmp_path, FakeReader()) as c:
        preview = c.post("/api/import/text", json={"text": text}).json()
        empty = c.post("/api/import/text", json={"text": " "})
        listed = c.get("/api/recipes").json()

    assert preview["recipe"]["title"] == "Suppe"
    assert preview["recipe"]["steps"][0]["machine"]["temp_c"] == 100
    assert preview["problems"] == []
    assert empty.status_code == 422
    assert listed == []

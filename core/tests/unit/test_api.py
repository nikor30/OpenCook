from datetime import UTC, datetime

from fastapi.testclient import TestClient

from opencook.api.app import create_app
from opencook.drivers.base import CookerState


class FakeReader:
    def __init__(self, state: CookerState) -> None:
        self.state = state
        self.calls = 0

    async def read_state(self) -> CookerState:
        self.calls += 1
        return self.state


def test_state_endpoint_returns_polled_state() -> None:
    state = CookerState(
        reachable=True,
        updated_at=datetime(2026, 10, 5, tzinfo=UTC),
        status=1,
        status_label="Cooking",
        remaining_s=42,
    )
    reader = FakeReader(state)

    with TestClient(create_app(reader)) as client:
        body = client.get("/api/state").json()

    assert reader.calls >= 1
    assert body["status_label"] == "Cooking"
    assert body["remaining_s"] == 42


def test_api_has_no_write_endpoints() -> None:
    app = create_app(FakeReader(CookerState(reachable=False, updated_at=datetime.now(UTC))))

    methods = {m for route in app.routes for m in getattr(route, "methods", set())}

    assert methods <= {"GET", "HEAD"}


def test_stats_endpoint_and_page() -> None:
    reader = FakeReader(
        CookerState(
            reachable=True,
            updated_at=datetime.now(UTC),
            status=1,
            cook_id=1577,
            cook_type=4,
            cook_name="Kartoffelbrei",
        )
    )

    with TestClient(create_app(reader)) as client:
        client.get("/api/state")
        stats = client.get("/api/stats").json()
        page = client.get("/stats")

    assert stats["total"] == 1
    assert stats["recipes"][0]["name"] == "Kartoffelbrei"
    assert page.status_code == 200


def test_index_is_served() -> None:
    reader = FakeReader(CookerState(reachable=False, updated_at=datetime.now(UTC)))

    with TestClient(create_app(reader)) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "Bimbi" in response.text

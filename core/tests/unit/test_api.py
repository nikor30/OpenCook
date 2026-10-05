import stat
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from opencook.api.app import create_app
from opencook.drivers.base import CookerReader, CookerState
from opencook.settings import DeviceSettings, SettingsStore

FAKE_KEY = "ab" * 16  # obviously fake device token


class FakeReader:
    def __init__(self, state: CookerState) -> None:
        self.state = state
        self.calls = 0

    async def read_state(self) -> CookerState:
        self.calls += 1
        return self.state


def cooking(name: str = "Kartoffelbrei") -> CookerState:
    return CookerState(
        reachable=True,
        updated_at=datetime.now(UTC),
        status=1,
        status_label="Cooking",
        remaining_s=42,
        cook_id=1577,
        cook_type=4,
        cook_name=name,
    )


def configured(tmp_path: Path) -> SettingsStore:
    return SettingsStore(tmp_path / "config.json", DeviceSettings(ip="192.0.2.10", token=FAKE_KEY))


def make_client(
    reader: CookerReader, settings_store: SettingsStore, built: list[DeviceSettings] | None = None
) -> TestClient:
    def factory(settings: DeviceSettings) -> CookerReader:
        if built is not None:
            built.append(settings)
        return reader

    return TestClient(create_app(reader_factory=factory, settings_store=settings_store))


def test_state_endpoint_returns_polled_state(tmp_path: Path) -> None:
    reader = FakeReader(cooking())

    with make_client(reader, configured(tmp_path)) as client:
        body = client.get("/api/state").json()

    assert reader.calls >= 1
    assert body["status_label"] == "Cooking"
    assert body["remaining_s"] == 42


def test_writable_routes_only_touch_local_data(tmp_path: Path) -> None:
    app = create_app(
        reader_factory=lambda _: FakeReader(cooking()), settings_store=configured(tmp_path)
    )

    writable = {
        (path, method.upper())
        for path, operations in app.openapi()["paths"].items()
        for method in operations
        if method not in {"get", "head"}
    }

    # Configuration, recipes and the cook-mode run. The cooker itself is never written to
    # (the driver only sends get_properties, see test_xiaomi_c3os_state).
    assert writable == {
        ("/api/settings", "PUT"),
        ("/api/recipes", "POST"),
        ("/api/recipes/{recipe_id}", "PUT"),
        ("/api/recipes/{recipe_id}", "DELETE"),
        ("/api/cook", "POST"),
        ("/api/cook", "PUT"),
        ("/api/cook", "DELETE"),
        ("/api/cook/next", "POST"),
        ("/api/cook/back", "POST"),
    }


def test_stats_endpoint_and_page(tmp_path: Path) -> None:
    with make_client(FakeReader(cooking()), configured(tmp_path)) as client:
        client.get("/api/state")
        stats = client.get("/api/stats").json()
        page = client.get("/stats")

    assert stats["total"] == 1
    assert stats["recipes"][0]["name"] == "Kartoffelbrei"
    assert page.status_code == 200


def test_pages_and_assets_are_served(tmp_path: Path) -> None:
    with make_client(FakeReader(cooking()), configured(tmp_path)) as client:
        responses = {
            path: client.get(path)
            for path in ["/", "/stats", "/settings", "/static/app.css", "/static/icons/stats.svg"]
        }

    assert {path: r.status_code for path, r in responses.items()} == dict.fromkeys(responses, 200)
    assert 'id="tabs"' in responses["/settings"].text


def test_settings_never_return_the_token(tmp_path: Path) -> None:
    with make_client(FakeReader(cooking()), configured(tmp_path)) as client:
        body = client.get("/api/settings").json()

    assert FAKE_KEY not in str(body)
    assert body == {
        "ip": "192.0.2.10",
        "token_set": True,
        "token_hint": "…abab",
        "show_debug": False,
        "configured": True,
    }


def test_changing_the_device_reconnects_and_persists(tmp_path: Path) -> None:
    store = configured(tmp_path)
    built: list[DeviceSettings] = []
    new_token = "f" * 32

    with make_client(FakeReader(cooking()), store, built) as client:
        response = client.put("/api/settings", json={"ip": "192.0.2.20", "token": new_token})

    assert response.status_code == 200
    assert response.json()["reachable"] is True
    assert built[-1] == DeviceSettings(ip="192.0.2.20", token=new_token)
    assert store.load().ip == "192.0.2.20"
    assert stat.S_IMODE((tmp_path / "config.json").stat().st_mode) == 0o600


def test_empty_token_keeps_the_stored_one(tmp_path: Path) -> None:
    store = configured(tmp_path)

    with make_client(FakeReader(cooking()), store) as client:
        client.put("/api/settings", json={"ip": "192.0.2.30", "token": ""})

    assert store.load() == DeviceSettings(ip="192.0.2.30", token=FAKE_KEY)


def test_invalid_token_is_rejected(tmp_path: Path) -> None:
    store = configured(tmp_path)

    with make_client(FakeReader(cooking()), store) as client:
        response = client.put("/api/settings", json={"token": "not-a-token"})

    assert response.status_code == 422
    assert "32 Hex-Zeichen" in response.text
    assert store.load().token == FAKE_KEY


def test_debug_toggle_does_not_reconnect(tmp_path: Path) -> None:
    store = configured(tmp_path)
    built: list[DeviceSettings] = []

    with make_client(FakeReader(cooking()), store, built) as client:
        client.put("/api/settings", json={"show_debug": True})
        shown = client.get("/api/settings").json()["show_debug"]

    assert shown is True
    assert len(built) == 1  # only the reader created at startup


def test_unconfigured_device_is_reported_as_unreachable(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path / "config.json", DeviceSettings())
    built: list[DeviceSettings] = []

    with make_client(FakeReader(cooking()), store, built) as client:
        state = client.get("/api/state").json()
        settings = client.get("/api/settings").json()

    assert built == []
    assert state["reachable"] is False
    assert settings["configured"] is False

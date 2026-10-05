from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from hypothesis import given
from hypothesis import strategies as st

from opencook.drivers.base import CookerState
from opencook.history import HistoryStore, SessionTracker
from opencook.history.tracker import IDLE_GAP

T0 = datetime(2026, 10, 5, 10, 0, tzinfo=UTC)


def state(
    t: float, status: int | None, cook_id: int = 1577, name: str = "Kartoffelbrei"
) -> CookerState:
    """State `t` seconds after T0; status None means the device is unreachable."""
    return CookerState(
        reachable=status is not None,
        updated_at=T0 + timedelta(seconds=t),
        status=status,
        cook_id=cook_id,
        cook_type=4,
        cook_name=name,
    )


def run(tracker: SessionTracker, states: list[CookerState]) -> None:
    for s in states:
        tracker.update(s)


def test_completed_recipe_is_one_session_with_cooking_time() -> None:
    tracker = SessionTracker()
    run(tracker, [state(t, 0) for t in range(3)])
    run(tracker, [state(t, 1) for t in range(3, 64)])  # 60 s cooking
    run(tracker, [state(64, 11), state(70, 0)])

    session = tracker.current
    assert session is not None
    assert session.outcome == "completed"
    assert session.cooking_s == 60
    assert session.started_at == T0 + timedelta(seconds=3)


def test_steps_of_one_recipe_with_short_breaks_stay_one_session() -> None:
    tracker = SessionTracker()
    run(tracker, [state(t, 1) for t in range(10)])
    run(tracker, [state(t, 0) for t in range(10, 300)])  # adding ingredients
    run(tracker, [state(t, 1) for t in range(300, 310)])

    session = tracker.current
    assert session is not None
    assert session.outcome == "running"
    assert session.cooking_s == 18  # 9 s + 9 s; the break does not count


def test_idle_gap_closes_session() -> None:
    tracker = SessionTracker()
    run(tracker, [state(t, 1) for t in range(5)])
    changed = tracker.update(state(4 + IDLE_GAP.total_seconds() + 1, 0))

    assert tracker.current is None
    assert changed[-1].ended_at == T0 + timedelta(seconds=4)
    # straight from running to standby without "complete"
    assert changed[-1].outcome == "cancelled"


def test_other_recipe_starts_new_session() -> None:
    tracker = SessionTracker()
    run(tracker, [state(t, 1) for t in range(5)])
    first = tracker.current
    tracker.update(state(5, 11))
    changed = tracker.update(state(6, 1, cook_id=1474, name="Gedämpfter Reis"))

    assert first is not None
    assert first.ended_at is not None
    assert first.outcome == "completed"
    assert tracker.current is not None
    assert tracker.current.name == "Gedämpfter Reis"
    assert changed == [first, tracker.current]


def test_offline_gap_does_not_count_as_cooking_time() -> None:
    tracker = SessionTracker()
    run(tracker, [state(0, 1), state(1, 1), state(2, None), state(200, 1), state(201, 1)])

    assert tracker.current is not None
    assert tracker.current.cooking_s == 2


@given(
    st.lists(
        st.tuples(st.integers(min_value=1, max_value=1200), st.sampled_from([None, 0, 1, 3, 11])),
        max_size=60,
    )
)
def test_cooking_time_never_exceeds_wall_time(steps: list[tuple[int, int | None]]) -> None:
    tracker = SessionTracker()
    sessions = []
    t = 0
    for gap, status in steps:
        t += gap
        sessions.extend(tracker.update(state(t, status)))

    for s in {id(s): s for s in sessions}.values():
        end = s.ended_at or s.last_running_at
        assert 0 <= s.cooking_s <= (end - s.started_at).total_seconds()


def test_store_persists_and_computes_stats() -> None:
    store = HistoryStore.in_memory()
    tracker = SessionTracker()
    states = [
        *[state(t, 1) for t in range(61)],
        state(61, 11),
        *[state(100 + t, 1, cook_id=1474, name="Reis") for t in range(31)],
        state(131, 0),
        *[state(3000 + t, 1) for t in range(11)],
    ]
    for s in states:
        for changed in tracker.update(s):
            store.save(changed)
    assert tracker.current is not None
    store.save(tracker.current)

    stats = store.stats(ZoneInfo("Europe/Berlin"), now=T0 + timedelta(hours=1))

    assert stats.total == 3
    assert stats.completed == 1
    assert stats.cooking_s == 60 + 30 + 10
    assert [(r.name, r.count, r.completed) for r in stats.recipes] == [
        ("Kartoffelbrei", 2, 1),
        ("Reis", 1, 0),
    ]
    assert stats.last_30_days[-1].count == 3
    assert stats.by_hour[12] == 3  # 10:00 UTC is 12:00 in Berlin (CEST)
    assert [s.outcome for s in stats.recent] == ["running", "cancelled", "completed"]


def test_open_session_is_resumed_after_restart() -> None:
    store = HistoryStore.in_memory()
    tracker = SessionTracker()
    for s in [state(t, 1) for t in range(5)]:
        for changed in tracker.update(s):
            store.save(changed)

    resumed = store.open_session()

    assert resumed is not None
    assert resumed.name == "Kartoffelbrei"
    assert resumed.started_at == T0


def test_cleaning_programs_have_their_own_stats() -> None:
    store = HistoryStore.in_memory()
    tracker = SessionTracker()
    gap = int(IDLE_GAP.total_seconds()) + 10
    states = [
        *[state(t, 1) for t in range(11)],
        state(11, 11),
        *[state(gap + t, 1, cook_id=15, name="Tiefenreinigung") for t in range(21)],
        state(gap + 21, 11),
        *[state(2 * gap + t, 1, cook_id=1474, name="Reis") for t in range(6)],
    ]
    for s in states:
        for changed in tracker.update(s):
            store.save(changed)

    stats = store.stats(now=T0 + timedelta(hours=2))

    assert stats.total == 2
    assert [r.name for r in stats.recipes] == ["Reis", "Kartoffelbrei"]  # same count: newest first
    assert all(s.name != "Tiefenreinigung" for s in stats.recent)
    assert stats.cleaning.total == 1
    assert stats.cleaning.completed == 1
    assert stats.cleaning.programs[0].name == "Tiefenreinigung"
    assert stats.cleaning.last_at == T0 + timedelta(seconds=gap)
    assert stats.cleaning.cooks_since_last == 1

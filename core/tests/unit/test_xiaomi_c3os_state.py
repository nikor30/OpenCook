from datetime import UTC, datetime

from opencook.drivers.xiaomi_c3os import state_from_props

NOW = datetime(2026, 10, 5, 9, 50, tzinfo=UTC)

# Values recorded during experiment E4 (official recipe running), name replaced.
RECIPE_RUNNING = {
    "2.1": 1,
    "2.2": 5,
    "2.3": 0,
    "2.4": False,
    "2.5": 0,
    "2.10": "",
    "3.1": False,
    "3.2": 0,
    "4.3": 1474,
    "4.4": 4,
    "4.5": "Testrezept",
    "4.6": 0,
    "4.7": 0,
    "4.8": True,
    "4.9": 0,
    "4.10": 0,
    "4.11": 0,
    "4.12": 0,
    "4.13": False,
    "4.14": 1496,
}


def test_running_recipe_is_mapped() -> None:
    state = state_from_props(RECIPE_RUNNING, NOW)

    assert state.reachable
    assert state.status == 1
    assert state.status_label == "Cooking"
    assert state.mode_label == "Other"
    assert state.remaining_s == 1496
    assert state.cook_id == 1474
    assert state.cook_type_label == "Recipe"
    assert state.cook_name == "Testrezept"
    assert state.raw == RECIPE_RUNNING


def test_failed_and_empty_values_become_none() -> None:
    props = {**RECIPE_RUNNING, "2.1": {"code": -4007}, "4.5": "", "4.14": False}

    state = state_from_props(props, NOW)

    assert state.status is None
    assert state.status_label is None
    assert state.cook_name is None
    assert state.remaining_s is None


def test_unknown_status_keeps_value_without_label() -> None:
    state = state_from_props({**RECIPE_RUNNING, "2.1": 42}, NOW)

    assert state.status == 42
    assert state.status_label is None

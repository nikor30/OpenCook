import pytest
from pydantic import ValidationError

from opencook.recipes import c3os
from opencook.recipes.models import MachineStep, Recipe
from opencook.recipes.schema import SCHEMA_PATH, render
from opencook.recipes.store import RecipeStore


def eggs() -> Recipe:
    return Recipe.model_validate(
        {
            "title": "Parmesan-Rührei",
            "servings": 2,
            "ingredients": [
                {"id": "i1", "name": "Eier", "amount": 4, "unit": "pcs"},
                {"id": "i2", "name": "Butter", "amount": 20, "unit": "g"},
            ],
            "steps": [
                {"id": "s1", "kind": "weigh", "ingredient": "i2", "target_g": 20},
                {
                    "id": "s2",
                    "kind": "machine",
                    "title": "Butter schmelzen",
                    "machine": {
                        "temp_c": 100,
                        "duration_s": 120,
                        "speed": {"level": 1, "of": 10, "direction": "reverse"},
                    },
                },
                {"id": "s3", "kind": "user", "text": "{i1} zugeben."},
                {"id": "s4", "kind": "wait", "duration_s": 60},
            ],
        }
    )


def test_valid_recipe_round_trips_through_the_store() -> None:
    store = RecipeStore.in_memory()
    recipe = eggs()

    store.put(recipe)

    assert store.get(recipe.id) == recipe
    [summary] = store.list()
    assert (summary.title, summary.steps, summary.machine_steps, summary.duration_s) == (
        "Parmesan-Rührei",
        4,
        1,
        120,
    )
    assert store.delete(recipe.id)
    assert store.get(recipe.id) is None


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda r: r["steps"].append(dict(r["steps"][0])), "Schritt-ID mehrfach"),
        (lambda r: r["steps"][0].update(ingredient="nope"), "unbekannte Zutat"),
        (lambda r: r["steps"][1]["machine"]["speed"].update(level=11), "über der Skala"),
        (lambda r: r.update(steps=[]), "at least 1"),
        (lambda r: r.update(extra_field=1), "Extra inputs"),
    ],
)
def test_invalid_recipes_are_rejected(change, message) -> None:  # type: ignore[no-untyped-def]
    data = eggs().model_dump(mode="json")
    change(data)

    with pytest.raises(ValidationError, match=message):
        Recipe.model_validate(data)


def test_speed_is_mapped_to_twenty_levels() -> None:
    step = eggs().steps[1]
    assert isinstance(step, MachineStep)

    settings = c3os.manual_settings(step)

    assert settings == c3os.ManualSettings(temp_c=100, duration_s=120, speed_level=2, reverse=True)


@pytest.mark.parametrize(
    ("temp_c", "level", "of", "expected"),
    [
        (100, 6, 20, []),
        (None, 20, 20, []),
        (80, 20, 20, []),
        (160, 1, 20, ["Schritt 2: 160 °C"]),
        (30, 1, 20, ["Schritt 2: 30 °C"]),
        (100, 7, 20, ["Schritt 2: Stufe 7"]),
        (100, 4, 10, ["Schritt 2: Stufe 8"]),
    ],
)
def test_device_limits(temp_c: int | None, level: int, of: int, expected: list[str]) -> None:
    data = eggs().model_dump(mode="json")
    data["steps"][1]["machine"].update(temp_c=temp_c, speed={"level": level, "of": of})

    found = c3os.problems(Recipe.model_validate(data))

    assert [p.split(" –")[0] for p in found] == expected


def test_schema_file_is_up_to_date() -> None:
    # Regenerate with: python -m opencook.recipes.schema
    assert SCHEMA_PATH.read_text(encoding="utf-8") == render()

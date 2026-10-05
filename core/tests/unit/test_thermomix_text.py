from pathlib import Path

import pytest

from opencook.converters.thermomix_text import convert, parse_settings
from opencook.recipes import c3os
from opencook.recipes.models import MachineStep, UserStep

FIXTURES = Path(__file__).parents[1] / "fixtures" / "thermomix_text"


def machine_steps(name: str) -> list[tuple[int, int | None, int | None, str]]:
    recipe = convert((FIXTURES / name).read_text(encoding="utf-8")).recipe
    return [
        (
            s.machine.duration_s,
            s.machine.temp_c,
            s.machine.speed.level if s.machine.speed else None,
            s.machine.speed.direction if s.machine.speed else "-",
        )
        for s in recipe.steps
        if isinstance(s, MachineStep)
    ]


def test_tomato_sauce() -> None:
    result = convert((FIXTURES / "tomatensauce.txt").read_text(encoding="utf-8"))
    recipe = result.recipe

    assert recipe.title == "Schnelle Tomatensauce"
    assert recipe.servings == 4
    assert recipe.source.type == "converted"
    assert [(i.amount, i.unit, i.name) for i in recipe.ingredients[:3]] == [
        (1, None, "Zwiebel, halbiert"),
        (2, None, "Knoblauchzehen"),
        (20, "g", "Olivenöl"),
    ]
    assert recipe.ingredients[5].amount == 0.5
    assert machine_steps("tomatensauce.txt") == [
        (5, None, 10, "forward"),
        (180, 120, 2, "forward"),
        (900, 100, 2, "reverse"),
        (20, None, 14, "forward"),
    ]
    assert isinstance(recipe.steps[-1], UserStep)
    assert recipe.steps[-1].text == "Abschmecken und servieren."
    assert result.warnings == []
    assert c3os.problems(recipe) == []


def test_text_before_settings_in_the_same_paragraph_is_a_user_step() -> None:
    recipe = convert((FIXTURES / "risotto.txt").read_text(encoding="utf-8")).recipe

    kinds = [s.kind for s in recipe.steps]

    assert kinds == ["machine", "machine", "machine", "machine", "user", "machine", "user"]
    assert recipe.steps[4].text == "Mit Weißwein ablöschen."


def test_gentle_stir_and_reverse() -> None:
    assert machine_steps("risotto.txt")[-1] == (1080, 100, 1, "reverse")


def test_varoma_and_dough_mode_are_flagged() -> None:
    varoma = convert((FIXTURES / "gemuese_varoma.txt").read_text(encoding="utf-8"))
    dough = convert((FIXTURES / "hefeteig.txt").read_text(encoding="utf-8"))

    [steam] = [s for s in varoma.recipe.steps if isinstance(s, MachineStep)]
    assert (steam.machine.temp_c, steam.machine.accessory) == (120, "steamer")
    assert any("Varoma" in w for w in varoma.warnings)
    assert any("Teig-Modus" in w for w in dough.warnings)
    assert dough.recipe.servings is None


@pytest.mark.parametrize(
    ("time", "rest", "expected"),
    [
        ("10 Sek.", "/Stufe 5.5", (10, None, 11, "forward")),
        ("1 Min. 30 Sek.", "/ 90°C / „Linkslauf“ / Stufe 2", (90, 90, 4, "reverse")),
        ("2 Std.", "/Varoma", (7200, 120, None, "-")),
        ("3 Sek.", "/Turbo", (3, None, 20, "forward")),
    ],
)
def test_settings_variants(
    time: str, rest: str, expected: tuple[int, int | None, int | None, str]
) -> None:
    settings = parse_settings(time, rest)

    assert settings is not None
    p = settings.params
    speed = p.speed
    assert (
        p.duration_s,
        p.temp_c,
        speed.level if speed else None,
        speed.direction if speed else "-",
    ) == expected


def test_text_without_headers_and_settings() -> None:
    result = convert("Brot\n500 g Mehl\n1 TL Salz\nAlles verkneten und backen.")

    assert [i.name for i in result.recipe.ingredients] == ["Mehl", "Salz"]
    assert [s.kind for s in result.recipe.steps] == ["user"]
    assert any("Thermomix-Einstellungen" in w for w in result.warnings)


def test_empty_text_is_rejected() -> None:
    with pytest.raises(ValueError, match="leer"):
        convert("  \n ")

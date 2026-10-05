"""Converts pasted recipe text in Thermomix notation into ORF.

Typical input, as shown on community recipe sites:

    Tomatensauce
    4 Portionen
    Zutaten
    1 Zwiebel, halbiert
    20 g Olivenöl
    Zubereitung
    1. Zwiebel in den Mixtopf geben, 5 Sek./Stufe 5 zerkleinern.
    2. Öl zugeben und 3 Min./120°C/Stufe 1 dünsten.

Every "<time>/<temperature>/<direction>/<speed>" group becomes a machine step, other text becomes
user steps. Anything that cannot be mapped to the device exactly is reported in `warnings`
instead of being changed silently. The user pastes the text; nothing is fetched from anywhere.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from opencook.recipes.models import (
    Ingredient,
    MachineParams,
    MachineStep,
    Recipe,
    Source,
    Speed,
    Step,
    UserStep,
)

# Thermomix speeds are 1-10 in half steps; ORF keeps them exactly on a 20-step scale.
TM_SPEED_SCALE = 20
VAROMA_TEMP_C = 120

INGREDIENT_HEADERS = re.compile(r"^(zutaten|zutatenliste|für das rezept)\b.*$", re.IGNORECASE)
STEP_HEADERS = re.compile(r"^(zubereitung|so geht'?s|anleitung|schritte)\b.*$", re.IGNORECASE)
SERVINGS = re.compile(r"(?:für\s*)?(\d+)\s*(?:portionen|personen|stück)\b", re.IGNORECASE)
NUMBERED = re.compile(r"^\s*(?:\d+[.)]|[-•*])\s+")

UNITS = (
    "kg|g|mg|ml|cl|dl|l|EL|TL|Msp\\.?|Prise[n]?|Stück|Stk\\.?|Zehe[n]?|Bund|Dose[n]?|"
    "Pck\\.?|Päckchen|Würfel|Becher|Tasse[n]?|Scheibe[n]?|Zweig[e]?|Blatt|Blätter|Handvoll"
)
FRACTIONS = {"½": 0.5, "¼": 0.25, "¾": 0.75, "⅓": 1 / 3, "⅔": 2 / 3}
INGREDIENT = re.compile(
    rf"^(?P<amount>\d+(?:[.,]\d+)?(?:\s*-\s*\d+(?:[.,]\d+)?)?|[½¼¾⅓⅔])?\s*"
    rf"(?:(?P<unit>{UNITS})(?=\s|$))?\s*(?P<name>.+)$"
)

TIME = r"(?:\d+(?:[.,]\d+)?\s*(?:Std\.?|Min\.?|Sek\.?))(?:\s*\d+\s*Sek\.?)?"
SETTING = (
    r"\d{2,3}\s*°\s*C?|Varoma|[„\"]?Linkslauf[“\"]?|[⟲↺]|Sanftrührstufe|Stufe\s*⨶|"
    r"Stufe\s*\d+(?:[.,]5)?|Teig-?Modus|Knetstufe|Turbo"
)
# One settings group: a time followed by "/"-separated settings, e.g. "3 Min./120°C/Stufe 1".
SETTINGS = re.compile(rf"(?P<time>{TIME})(?P<rest>(?:\s*/\s*(?:{SETTING}))+)", re.IGNORECASE)


@dataclass
class ImportResult:
    recipe: Recipe
    warnings: list[str] = field(default_factory=list)


def _number(text: str) -> float:
    if text in FRACTIONS:
        return FRACTIONS[text]
    return float(text.replace(",", ".").split("-")[0].strip())


def _seconds(text: str) -> int:
    total = 0.0
    for value, unit in re.findall(r"(\d+(?:[.,]\d+)?)\s*(Std|Min|Sek)", text, re.IGNORECASE):
        factor = {"std": 3600, "min": 60, "sek": 1}[unit.lower()]
        total += float(value.replace(",", ".")) * factor
    return max(1, round(total))


def parse_ingredient(line: str, index: int) -> Ingredient | None:
    line = NUMBERED.sub("", line).strip()
    match = INGREDIENT.match(line)
    if not match or not match["name"].strip():
        return None
    amount = _number(match["amount"]) if match["amount"] else None
    unit = match["unit"]
    if unit and unit.lower().startswith(("stück", "stk")):
        unit = "pcs"
    return Ingredient(id=f"i{index}", name=match["name"].strip(" ,"), amount=amount, unit=unit)


@dataclass
class Settings:
    params: MachineParams
    warnings: list[str]


def parse_settings(time: str, rest: str) -> Settings | None:
    temp: int | None = None
    reverse = False
    level: int | None = None
    accessory: Literal["none", "steamer"] = "none"
    warnings: list[str] = []
    recognised = False
    for raw in rest.split("/"):
        part = raw.strip().strip("„“\"'").lower()
        if not part:
            continue
        if m := re.fullmatch(r"(\d{2,3})\s*°\s*c?", part):
            temp = int(m[1])
            recognised = True
        elif part == "varoma":
            temp = VAROMA_TEMP_C
            accessory = "steamer"
            recognised = True
            warnings.append("Varoma als Dampfgaren mit 120 °C übernommen – am Gerät prüfen")
        elif "linkslauf" in part or part in {"⟲", "↺"}:
            reverse = True
            recognised = True
        elif "sanftrühr" in part or part in {"stufe ⨶", "⨶"}:
            level = 1
            recognised = True
        elif m := re.fullmatch(r"stufe\s*(\d+(?:[.,]5)?)", part):
            level = round(float(m[1].replace(",", ".")) * 2)
            recognised = True
        elif "knet" in part or "teig" in part:
            level = 4
            recognised = True
            warnings.append("Knet-/Teig-Modus gibt es so nicht – als Stufe 4 übernommen")
        elif "turbo" in part:
            level = TM_SPEED_SCALE
            recognised = True
            warnings.append("Turbo als höchste Stufe übernommen")
    if not recognised:
        return None
    speed = (
        Speed(level=level, of=TM_SPEED_SCALE, direction="reverse" if reverse else "forward")
        if level
        else None
    )
    return Settings(
        MachineParams(temp_c=temp, duration_s=_seconds(time), speed=speed, accessory=accessory),
        warnings,
    )


def _sections(lines: list[str]) -> tuple[str | None, list[str], list[str], list[str]]:
    """Split into title, header lines, ingredient lines and step lines."""
    title: str | None = None
    head: list[str] = []
    ingredients: list[str] = []
    steps: list[str] = []
    target = head
    for line in lines:
        if INGREDIENT_HEADERS.match(line):
            target = ingredients
        elif STEP_HEADERS.match(line):
            target = steps
        elif title is None and target is head:
            title = line
        else:
            target.append(line)
    if not steps and not ingredients:
        # No headers: lines that start with an amount are ingredients, the rest are steps.
        for line in head:
            (
                ingredients if re.match(r"^\s*(\d|[½¼¾⅓⅔])", line) and len(line) < 60 else steps
            ).append(line)
        head = []
    return title, head, ingredients, steps


def _split_paragraphs(lines: list[str]) -> list[str]:
    paragraphs: list[str] = []
    for line in lines:
        if NUMBERED.match(line) or not paragraphs:
            paragraphs.append(NUMBERED.sub("", line))
        else:
            paragraphs[-1] += " " + line
    return [p.strip() for p in paragraphs if p.strip()]


def convert(text: str, origin: str | None = None) -> ImportResult:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        raise ValueError("Der Text ist leer.")
    title, head, ingredient_lines, step_lines = _sections(lines)
    warnings: list[str] = []

    servings = None
    for line in [*head, *([title] if title else [])]:
        if m := SERVINGS.search(line):
            servings = int(m[1])
            break

    ingredients: list[Ingredient] = []
    for line in ingredient_lines:
        if SERVINGS.fullmatch(line.strip()):
            servings = servings or int(SERVINGS.fullmatch(line.strip())[1])  # type: ignore[index]
            continue
        ingredient = parse_ingredient(line, len(ingredients) + 1)
        if ingredient:
            ingredients.append(ingredient)

    steps: list[Step] = []

    def step_id() -> str:
        return f"s{len(steps) + 1}"

    for number, paragraph in enumerate(_split_paragraphs(step_lines), start=1):
        position = 0
        for match in SETTINGS.finditer(paragraph):
            settings = parse_settings(match["time"], match["rest"])
            if settings is None:
                continue
            # The sentence up to and including the settings describes this machine step.
            sentence_start = max(paragraph.rfind(". ", position, match.start()) + 1, position)
            before = paragraph[position:sentence_start].strip()
            if before:
                steps.append(UserStep(id=step_id(), text=before))
            end = paragraph.find(".", match.end())
            end = len(paragraph) if end == -1 else end + 1
            steps.append(
                MachineStep(
                    id=step_id(),
                    text=paragraph[sentence_start:end].strip(),
                    machine=settings.params,
                )
            )
            warnings.extend(f"Schritt {number}: {w}" for w in settings.warnings)
            position = end
        rest = paragraph[position:].strip()
        if rest:
            steps.append(UserStep(id=step_id(), text=rest))

    if not steps:
        raise ValueError("Keine Zubereitungsschritte gefunden.")
    if not ingredients:
        warnings.append("Keine Zutaten erkannt – bitte im Editor ergänzen")
    if not any(isinstance(s, MachineStep) for s in steps):
        warnings.append("Keine Thermomix-Einstellungen wie „5 Sek./Stufe 5“ gefunden")

    recipe = Recipe(
        title=(title or "Importiertes Rezept")[:200],
        servings=servings,
        source=Source(type="converted", origin=origin or "thermomix-text", license="private"),
        ingredients=ingredients,
        steps=steps,
    )
    return ImportResult(recipe=recipe, warnings=warnings)

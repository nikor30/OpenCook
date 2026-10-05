"""Reads schema.org `Recipe` data (JSON-LD) from a web page and converts it into ORF.

Many recipe sites embed this structured data for search engines. Ingredients and instructions are
passed through the Thermomix text converter, so settings like "10 Min./100°C/Stufe 1" in the
instructions become machine steps. Images are not taken over.
"""

from __future__ import annotations

import html as html_lib
import json
import re
from typing import Any

from opencook.converters.thermomix_text import ImportResult, convert

JSON_LD = re.compile(
    r"<script[^>]+type\s*=\s*[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
    re.IGNORECASE | re.DOTALL,
)
TAG = re.compile(r"<[^>]+>")


class NoRecipeFoundError(ValueError):
    pass


def _is_recipe(node: dict[str, Any]) -> bool:
    kind = node.get("@type")
    kinds = kind if isinstance(kind, list) else [kind]
    return "Recipe" in kinds


def _walk(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [r for item in data for r in _walk(item)]
    if isinstance(data, dict):
        if _is_recipe(data):
            return [data]
        return _walk(data.get("@graph", []))
    return []


def json_ld_types(page: str) -> list[str]:
    """The schema.org types embedded in the page, for the test mode."""
    found: list[str] = []

    def collect(data: Any) -> None:
        if isinstance(data, list):
            for item in data:
                collect(item)
        elif isinstance(data, dict):
            kind = data.get("@type")
            found.extend(kind if isinstance(kind, list) else [kind] if kind else [])
            collect(data.get("@graph", []))

    for block in JSON_LD.findall(page):
        try:
            collect(json.loads(block.strip()))
        except json.JSONDecodeError:
            found.append("(ungültiges JSON)")
    return found


def find_recipe(page: str) -> dict[str, Any] | None:
    for block in JSON_LD.findall(page):
        try:
            data = json.loads(block.strip())
        except json.JSONDecodeError:
            continue
        recipes = _walk(data)
        if recipes:
            return recipes[0]
    return None


def _text(value: Any) -> str:
    """Plain text from a JSON-LD string that may contain HTML and entities."""
    text = html_lib.unescape(TAG.sub(" ", str(value)))
    return re.sub(r"\s+", " ", text).strip()


def _instructions(value: Any) -> list[str]:
    if isinstance(value, str):
        parts = re.split(r"\n+|(?<=\.)\s+(?=\d+\.\s)", value)
        steps = [re.sub(r"^\d+[.)]\s*", "", _text(p)) for p in parts]
        return [step for step in steps if step]
    if isinstance(value, list):
        return [step for item in value for step in _instructions(item)]
    if isinstance(value, dict):
        if "itemListElement" in value:  # HowToSection
            return _instructions(value["itemListElement"])
        return [_text(value.get("text") or value.get("name") or "")]
    return []


def _servings(value: Any) -> str | None:
    values = value if isinstance(value, list) else [value]
    for item in values:
        if m := re.search(r"\d+", str(item)):
            return m[0]
    return None


def to_text(recipe: dict[str, Any]) -> str:
    """Renders the JSON-LD recipe in the layout the text converter understands."""
    lines = [_text(recipe.get("name") or "Importiertes Rezept")]
    if servings := _servings(recipe.get("recipeYield")):
        lines.append(f"{servings} Portionen")
    ingredients = recipe.get("recipeIngredient") or recipe.get("ingredients") or []
    if isinstance(ingredients, str):
        ingredients = [ingredients]
    lines.append("Zutaten")
    lines += [_text(i) for i in ingredients if _text(i)]
    lines.append("Zubereitung")
    lines += [
        f"{n}. {step}" for n, step in enumerate(_instructions(recipe.get("recipeInstructions")), 1)
    ]
    return "\n".join(lines)


def tags(recipe: dict[str, Any]) -> list[str]:
    raw = recipe.get("keywords") or []
    words = raw.split(",") if isinstance(raw, str) else raw
    category = recipe.get("recipeCategory")
    if category:
        words = [*([category] if isinstance(category, str) else category), *words]
    cleaned = [_text(w).lower() for w in words if _text(w)]
    return list(dict.fromkeys(cleaned))[:8]


def convert_page(page: str, url: str) -> ImportResult:
    recipe = find_recipe(page)
    if recipe is None:
        raise NoRecipeFoundError(
            "Auf dieser Seite gibt es keine maschinenlesbaren Rezeptdaten (schema.org). "
            "Kopiere den Rezepttext und nutze „Text einfügen“."
        )
    result = convert(to_text(recipe), origin=url)
    result.recipe = result.recipe.model_copy(update={"tags": tags(recipe)})
    return result

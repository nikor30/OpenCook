"""Writes schemas/orf-v1.json from the Pydantic models: python -m opencook.recipes.schema"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from opencook.recipes.models import Recipe

SCHEMA_PATH = Path(__file__).resolve().parents[3] / "schemas" / "orf-v1.json"


def orf_schema() -> dict[str, Any]:
    schema = Recipe.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "https://github.com/nikor30/OpenCook/schemas/orf-v1.json"
    return schema


def render() -> str:
    return json.dumps(orf_schema(), indent=2, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    SCHEMA_PATH.write_text(render(), encoding="utf-8")
    sys.stdout.write(f"wrote {SCHEMA_PATH}\n")

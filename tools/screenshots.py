#!/usr/bin/env python3
"""Take the README screenshots of the web UI with Playwright.

    docker run --rm --network host -v "$PWD:/work" -w /work \
        mcr.microsoft.com/playwright/python:v1.63.0-noble \
        python tools/screenshots.py --url http://192.168.10.232:8080

Live state comes from the running core. The token hint is replaced so no part of the real token
ends up in the repo, and the statistics use demo data (marked as such in the README) until enough
real history exists.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, Route, sync_playwright

OUT = Path("docs/screenshots")


def fake_settings(show_debug: bool) -> dict[str, Any]:
    return {
        "ip": "192.168.10.159",
        "token_set": True,
        "token_hint": "…a1b2",
        "show_debug": show_debug,
        "configured": True,
    }


def demo_stats() -> dict[str, Any]:
    now = datetime.now(UTC)
    day = now.date()

    def session(days_ago: int, hour: int, name: str, minutes: int, outcome: str) -> dict[str, Any]:
        start = datetime(day.year, day.month, day.day, hour, 0, tzinfo=UTC) - timedelta(days_ago)
        return {
            "name": name,
            "cook_id": None,
            "started_at": start.isoformat(),
            "ended_at": (start + timedelta(minutes=minutes + 5)).isoformat(),
            "cooking_s": minutes * 60,
            "outcome": outcome,
        }

    recent = [
        session(0, 10, "Kartoffelbrei", 24, "completed"),
        session(1, 16, "Gedämpfter Reis", 25, "completed"),
        session(2, 17, "Risotto", 22, "completed"),
        session(3, 6, "Rührei", 6, "completed"),
        session(4, 16, "Kartoffelbrei", 24, "cancelled"),
        session(6, 17, "Gedämpfter Reis", 25, "completed"),
    ]
    counts = [0] * 30
    per_day_ago = {0: 1, 1: 1, 2: 1, 3: 1, 4: 1, 6: 1, 8: 2, 11: 1, 13: 1, 15: 2, 20: 1, 24: 1}
    for d, n in per_day_ago.items():
        counts[29 - d] = n
    hours = [0] * 24
    for h, n in {6: 2, 7: 1, 10: 1, 12: 3, 16: 3, 17: 4, 18: 2}.items():
        hours[h] = n

    def recipe(name: str, count: int, done: int, minutes: int, days_ago: int) -> dict[str, Any]:
        return {
            "name": name,
            "cook_id": None,
            "count": count,
            "completed": done,
            "cooking_s": minutes * 60,
            "last_cooked_at": (now - timedelta(days=days_ago)).isoformat(),
        }

    return {
        "total": 14,
        "completed": 12,
        "cooking_s": 290 * 60,
        "recipes": [
            recipe("Kartoffelbrei", 5, 4, 118, 0),
            recipe("Gedämpfter Reis", 4, 4, 100, 1),
            recipe("Risotto", 3, 3, 64, 2),
            recipe("Rührei", 2, 1, 8, 3),
        ],
        "last_30_days": [
            {"day": (day - timedelta(days=29 - i)).isoformat(), "count": counts[i]}
            for i in range(30)
        ],
        "by_hour": hours,
        "recent": recent,
        "cleaning": {
            "total": 3,
            "completed": 3,
            "last_at": (now - timedelta(days=2)).isoformat(),
            "cooks_since_last": 3,
            "programs": [recipe("Tiefenreinigung", 3, 3, 45, 2)],
            "recent": [],
        },
    }


def fulfill_json(data: dict[str, Any]) -> Any:
    def handler(route: Route) -> None:
        if route.request.method == "GET":
            route.fulfill(content_type="application/json", body=json.dumps(data))
        else:
            route.continue_()

    return handler


def shot(page: Page, name: str, full_page: bool = True) -> None:
    page.wait_for_timeout(1500)
    page.screenshot(path=str(OUT / name), full_page=full_page)
    print("wrote", OUT / name)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", default="http://127.0.0.1:8080")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        for scheme in ("light", "dark"):
            context = browser.new_context(
                viewport={"width": 760, "height": 900},
                device_scale_factor=2,
                color_scheme=scheme,
                locale="de-DE",
                timezone_id="Europe/Berlin",
            )
            page = context.new_page()
            page.route("**/api/settings", fulfill_json(fake_settings(show_debug=False)))
            page.route("**/api/stats", fulfill_json(demo_stats()))

            page.goto(f"{args.url}/")
            shot(page, f"live-{scheme}.png")
            page.goto(f"{args.url}/stats")
            shot(page, f"stats-{scheme}.png")
            page.goto(f"{args.url}/settings")
            shot(page, f"settings-{scheme}.png")

            page.unroute("**/api/settings")
            page.route("**/api/settings", fulfill_json(fake_settings(show_debug=True)))
            page.goto(f"{args.url}/")
            shot(page, f"live-debug-{scheme}.png")
            context.close()

        phone = browser.new_context(
            viewport={"width": 390, "height": 844},
            device_scale_factor=2,
            color_scheme="light",
            locale="de-DE",
            timezone_id="Europe/Berlin",
        )
        page = phone.new_page()
        page.route("**/api/settings", fulfill_json(fake_settings(show_debug=False)))
        page.goto(f"{args.url}/")
        shot(page, "live-phone.png", full_page=False)
        browser.close()


if __name__ == "__main__":
    main()

from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from opencook.converters import schema_org, web
from opencook.recipes.models import MachineStep

PAGE = (Path(__file__).parents[1] / "fixtures" / "schema_org" / "linsensuppe.html").read_text(
    encoding="utf-8"
)
PUBLIC_IP = "93.184.216.34"


async def public(_: str) -> list[str]:
    return [PUBLIC_IP]


async def private(_: str) -> list[str]:
    return ["192.168.10.1"]


def client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=False)


def site(robots: str = "", page: str = PAGE, status: int = 200) -> Callable[..., httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text=robots) if robots else httpx.Response(404)
        return httpx.Response(status, text=page)

    return handler


def test_schema_org_recipe_is_converted() -> None:
    result = schema_org.convert_page(PAGE, "https://example.org/linsen")
    recipe = result.recipe

    assert recipe.title == "Rote Linsensuppe & Kokos"
    assert recipe.servings == 4
    assert recipe.tags == ["suppe", "vegan", "schnell"]
    assert recipe.source.origin == "https://example.org/linsen"
    assert recipe.images == []
    assert [i.name for i in recipe.ingredients][:3] == ["Zwiebel", "Öl", "rote Linsen"]
    machine = [s.machine for s in recipe.steps if isinstance(s, MachineStep)]
    assert [(m.duration_s, m.temp_c) for m in machine] == [(5, None), (180, 120), (900, 100)]
    assert recipe.steps[-1].text == "Mit Salz abschmecken."


def test_instructions_as_one_string_are_split() -> None:
    page = PAGE.replace(
        '"recipeInstructions": [', '"recipeInstructions": "1. Erst. 2. Dann.", "x": ['
    )

    recipe = schema_org.convert_page(page, "https://example.org/x").recipe

    assert [s.text for s in recipe.steps] == ["Erst.", "Dann."]


def test_page_without_recipe_data() -> None:
    with pytest.raises(schema_org.NoRecipeFoundError, match="Text einfügen"):
        schema_org.convert_page("<html><body>Kein Rezept</body></html>", "https://example.org")


async def test_compressed_pages_are_decoded_once() -> None:
    import gzip

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        body = gzip.compress(PAGE.encode())
        return httpx.Response(
            200,
            content=body,
            headers={"content-encoding": "gzip", "content-type": "text/html; charset=utf-8"},
        )

    async with client(handler) as c:
        page = await web.fetch_page("https://example.org/gz", client=c, resolver=public)

    assert "Linsensuppe" in page


async def test_fetch_page() -> None:
    async with client(site()) as c:
        page = await web.fetch_page("https://example.org/linsen", client=c, resolver=public)

    assert "Rote Linsensuppe" in page


@pytest.mark.parametrize(
    ("url", "message"),
    [
        ("https://www.rezeptwelt.de/rezept/1", "Rezeptwelt"),
        ("https://mixbuch.app/r/1", "MixBuch"),
        ("https://cookidoo.de/recipes/1", "Cookidoo"),
        ("ftp://example.org/x", "https://"),
        ("example.org/x", "https://"),
    ],
)
async def test_refused_urls(url: str, message: str) -> None:
    async with client(site()) as c:
        with pytest.raises(web.ImportRefusedError, match=message):
            await web.fetch_page(url, client=c, resolver=public)


async def test_local_network_is_refused() -> None:
    async with client(site()) as c:
        with pytest.raises(web.ImportRefusedError, match="lokalen Netz"):
            await web.fetch_page("http://router.local/", client=c, resolver=private)


async def test_robots_txt_is_respected() -> None:
    robots = "User-agent: *\nDisallow: /rezepte/\n"
    async with client(site(robots)) as c:
        with pytest.raises(web.ImportRefusedError, match=r"robots\.txt"):
            await web.fetch_page("https://example.org/rezepte/1", client=c, resolver=public)
        assert await web.fetch_page("https://example.org/blog/1", client=c, resolver=public)


async def test_redirect_into_blocked_site_is_refused() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(302, headers={"location": "https://www.rezeptwelt.de/x"})

    async with client(handler) as c:
        with pytest.raises(web.ImportRefusedError, match="Rezeptwelt"):
            await web.fetch_page("https://short.example/abc", client=c, resolver=public)


async def test_large_pages_and_errors_are_refused() -> None:
    async with client(site(page="x" * (web.MAX_BYTES + 1))) as c:
        with pytest.raises(web.ImportRefusedError, match="zu groß"):
            await web.fetch_page("https://example.org/big", client=c, resolver=public)
    async with client(site(status=404)) as c:
        with pytest.raises(web.ImportRefusedError, match="404"):
            await web.fetch_page("https://example.org/missing", client=c, resolver=public)

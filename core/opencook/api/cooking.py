"""Routes for recipes (local data) and cook mode. Nothing here writes to the device."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from opencook.converters import schema_org, thermomix_text, web
from opencook.drivers.base import CookerState
from opencook.recipes import c3os
from opencook.recipes.models import MachineStep, Recipe, WaitStep
from opencook.recipes.store import RecipeStore, RecipeSummary
from opencook.runner.run import CookRun

# Manual runs show up as "Handbuch" on the device; during cook mode they belong to the recipe.
MANUAL_COOK_NAME = "Handbuch"


class RecipeOut(BaseModel):
    recipe: Recipe
    problems: list[str]


class CookView(BaseModel):
    run: CookRun
    settings: c3os.ManualSettings | None
    wait_remaining_s: int | None


class TextImport(BaseModel):
    text: str = Field(max_length=50_000)
    origin: str | None = Field(default=None, max_length=200)


class ImportPreview(BaseModel):
    recipe: Recipe
    warnings: list[str]
    problems: list[str]


class UrlImport(BaseModel):
    url: str = Field(min_length=8, max_length=2000)


class CheckOut(BaseModel):
    name: str
    ok: bool
    detail: str


class UrlCheck(BaseModel):
    """Test mode of the URL import: every check, plus the preview if it got that far."""

    ok: bool
    checks: list[CheckOut]
    preview: ImportPreview | None


class CookStart(BaseModel):
    recipe_id: UUID


class CookOptions(BaseModel):
    auto_advance: bool


class CookController:
    def __init__(self, recipes: RecipeStore) -> None:
        self._recipes = recipes
        self.run = recipes.load_run()

    def save(self) -> None:
        self._recipes.save_run(self.run)

    def on_state(self, state: CookerState) -> None:
        if self.run is not None and self.run.update(state, datetime.now(UTC)):
            self.save()

    def history_name(self, state: CookerState) -> CookerState:
        """Count manual runs during cook mode as the recipe in the statistics."""
        if self.run is None or self.run.finished or state.cook_name != MANUAL_COOK_NAME:
            return state
        return state.model_copy(update={"cook_name": self.run.recipe.title})

    def view(self) -> CookView | None:
        if self.run is None:
            return None
        step = self.run.step
        wait_remaining = None
        if isinstance(step, WaitStep) and self.run.phase == "running":
            elapsed = (datetime.now(UTC) - self.run.phase_since).total_seconds()
            wait_remaining = max(0, round(step.duration_s - elapsed))
        return CookView(
            run=self.run,
            settings=c3os.manual_settings(step) if isinstance(step, MachineStep) else None,
            wait_remaining_s=wait_remaining,
        )


def _require(view: CookView | None) -> CookView:
    if view is None:
        raise HTTPException(404, "Es läuft gerade kein Rezept.")
    return view


def make_router(
    recipes: RecipeStore, cook: CookController, resolver: web.Resolver = web.resolve
) -> APIRouter:
    router = APIRouter(prefix="/api")

    def out(recipe: Recipe) -> RecipeOut:
        return RecipeOut(recipe=recipe, problems=c3os.problems(recipe))

    def load(recipe_id: UUID) -> Recipe:
        recipe = recipes.get(recipe_id)
        if recipe is None:
            raise HTTPException(404, "Rezept nicht gefunden.")
        return recipe

    @router.get("/recipes")
    async def list_recipes() -> list[RecipeSummary]:
        return recipes.list()

    @router.post("/recipes", status_code=201)
    async def create_recipe(recipe: Recipe) -> RecipeOut:
        if recipes.get(recipe.id) is not None:
            raise HTTPException(409, "Ein Rezept mit dieser ID gibt es schon.")
        recipes.put(recipe)
        return out(recipe)

    @router.post("/import/text")
    async def import_text(body: TextImport) -> ImportPreview:
        """Converts pasted text into a recipe preview; nothing is saved."""
        try:
            result = thermomix_text.convert(body.text, body.origin)
        except ValueError as err:
            raise HTTPException(422, str(err)) from err
        return ImportPreview(
            recipe=result.recipe,
            warnings=result.warnings,
            problems=c3os.problems(result.recipe),
        )

    @router.get("/import/blocked")
    async def blocked_sites() -> dict[str, str]:
        """Sites whose terms forbid automated reading; the URL import refuses them."""
        return web.BLOCKED_DOMAINS

    @router.post("/import/url")
    async def import_url(body: UrlImport) -> ImportPreview:
        """Fetches one page and converts its schema.org recipe into a preview; nothing is saved."""
        try:
            page = await web.fetch_page(body.url, resolver=resolver)
            result = schema_org.convert_page(page, body.url.strip())
        except ValueError as err:  # ImportRefused, NoRecipeFound, conversion errors
            raise HTTPException(422, str(err)) from err
        return ImportPreview(
            recipe=result.recipe,
            warnings=result.warnings,
            problems=c3os.problems(result.recipe),
        )

    @router.post("/import/url/check")
    async def check_url(body: UrlImport) -> UrlCheck:
        """Runs the URL import step by step and reports each check; nothing is saved."""
        trace: list[web.Check] = []

        def report(ok: bool, preview: ImportPreview | None = None) -> UrlCheck:
            checks = [CheckOut(name=c.name, ok=c.ok, detail=c.detail) for c in trace]
            return UrlCheck(ok=ok, checks=checks, preview=preview)

        try:
            page = await web.fetch_page(body.url, resolver=resolver, trace=trace)
        except web.ImportRefusedError:
            return report(False)
        types = schema_org.json_ld_types(page)
        found = schema_org.find_recipe(page) is not None
        detail = f"schema.org-Typen: {', '.join(types)}" if types else "keine schema.org-Daten"
        trace.append(web.Check("Rezeptdaten", found, detail))
        if not found:
            return report(False)
        try:
            result = schema_org.convert_page(page, body.url.strip())
        except ValueError as err:
            trace.append(web.Check("Umwandlung", False, str(err)))
            return report(False)
        recipe = result.recipe
        machine = sum(isinstance(s, MachineStep) for s in recipe.steps)
        summary = (
            f"„{recipe.title}“: {len(recipe.ingredients)} Zutaten, {len(recipe.steps)} Schritte, "
            f"davon {machine} an der Maschine"
        )
        trace.append(web.Check("Umwandlung", True, summary))
        problems = c3os.problems(recipe)
        return report(
            True, ImportPreview(recipe=recipe, warnings=result.warnings, problems=problems)
        )

    @router.get("/recipes/{recipe_id}")
    async def get_recipe(recipe_id: UUID) -> RecipeOut:
        return out(load(recipe_id))

    @router.put("/recipes/{recipe_id}")
    async def update_recipe(recipe_id: UUID, recipe: Recipe) -> RecipeOut:
        if recipe.id != recipe_id:
            raise HTTPException(422, "Die Rezept-ID passt nicht zur Adresse.")
        load(recipe_id)
        recipes.put(recipe)
        return out(recipe)

    @router.delete("/recipes/{recipe_id}", status_code=204)
    async def delete_recipe(recipe_id: UUID) -> Response:
        if not recipes.delete(recipe_id):
            raise HTTPException(404, "Rezept nicht gefunden.")
        return Response(status_code=204)

    @router.get("/cook")
    async def get_cook() -> CookView | None:
        return cook.view()

    @router.post("/cook", status_code=201)
    async def start_cook(body: CookStart) -> CookView:
        recipe = load(body.recipe_id)
        if cook.run is not None and not cook.run.finished:
            raise HTTPException(409, f"Es läuft bereits „{cook.run.recipe.title}“.")
        found = c3os.problems(recipe)
        if found:
            raise HTTPException(409, " ".join(found))
        cook.run = CookRun.start(recipe, datetime.now(UTC))
        cook.save()
        return _require(cook.view())

    def change(action: str) -> CookView:
        if cook.run is None:
            raise HTTPException(404, "Es läuft gerade kein Rezept.")
        now = datetime.now(UTC)
        if action == "next":
            cook.run.next(now)
        else:
            cook.run.back(now)
        cook.save()
        return _require(cook.view())

    @router.post("/cook/next")
    async def next_step() -> CookView:
        return change("next")

    @router.post("/cook/back")
    async def previous_step() -> CookView:
        return change("back")

    @router.put("/cook")
    async def set_options(options: CookOptions) -> CookView:
        if cook.run is None:
            raise HTTPException(404, "Es läuft gerade kein Rezept.")
        cook.run.auto_advance = options.auto_advance
        cook.save()
        return _require(cook.view())

    @router.delete("/cook", status_code=204)
    async def end_cook() -> Response:
        cook.run = None
        cook.save()
        return Response(status_code=204)

    return router

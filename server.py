"""
Recipe Fetcher — FastAPI backend
Fallback chain: recipe-scrapers → JSON-LD → CSS heuristics → error
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import httpx
from bs4 import BeautifulSoup
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}

INDEX_PATH = Path(__file__).parent / "index.html"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _iso_duration_to_str(val: str | None) -> str:
    """Convert ISO 8601 duration like PT1H30M to '1 hr 30 min'."""
    if not val:
        return ""
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", val, re.IGNORECASE)
    if not m:
        return val
    parts = []
    if m.group(1):
        parts.append(f"{m.group(1)} hr")
    if m.group(2):
        parts.append(f"{m.group(2)} min")
    if m.group(3):
        parts.append(f"{m.group(3)} sec")
    return " ".join(parts) if parts else val


def _extract_int(val) -> int | None:
    if val is None:
        return None
    if isinstance(val, int):
        return val
    m = re.search(r"\d+", str(val))
    return int(m.group()) if m else None


def _normalize_steps(raw_steps) -> list[dict]:
    """Normalize steps into list of {text, image}."""
    steps = []
    if not raw_steps:
        return steps
    if isinstance(raw_steps, str):
        for line in raw_steps.split("\n"):
            line = line.strip()
            if line:
                steps.append({"text": re.sub(r"^\d+[\.\)]\s*", "", line), "image": None})
        return steps
    for item in raw_steps:
        if isinstance(item, str):
            steps.append({"text": item, "image": None})
        elif isinstance(item, dict):
            # HowToSection with itemListElement (e.g. recipe sections)
            if item.get("@type") == "HowToSection" or "itemListElement" in item:
                for sub in item.get("itemListElement", []):
                    if isinstance(sub, dict):
                        steps.append({"text": sub.get("text", ""), "image": sub.get("image")})
                    elif isinstance(sub, str):
                        steps.append({"text": sub, "image": None})
                continue
            text = item.get("text", "")
            image = item.get("image", None)
            if isinstance(image, dict):
                image = image.get("url") or image.get("src")
            if isinstance(image, list):
                image = image[0] if image else None
            steps.append({"text": text, "image": image})
        elif isinstance(item, list):
            # HowToSection — flatten
            for sub in item:
                if isinstance(sub, dict):
                    steps.append({"text": sub.get("text", ""), "image": sub.get("image")})
                elif isinstance(sub, str):
                    steps.append({"text": sub, "image": None})
    return steps


def _normalize_ingredients(raw) -> list[str]:
    if not raw:
        return []
    if isinstance(raw, str):
        return [line.strip() for line in raw.split("\n") if line.strip()]
    return [str(i) for i in raw]


def _build_response(
    title="", image="", servings=None, prep_time="", cook_time="",
    total_time="", ingredients=None, steps=None,
):
    return {
        "title": title or "",
        "image": image or "",
        "servings": servings,
        "prepTime": prep_time or "",
        "cookTime": cook_time or "",
        "totalTime": total_time or "",
        "ingredients": ingredients or [],
        "steps": steps or [],
    }


# ---------------------------------------------------------------------------
# Strategy 1 — recipe-scrapers
# ---------------------------------------------------------------------------

def _try_recipe_scrapers(url: str, html: str) -> dict | None:
    try:
        from recipe_scrapers import scrape_html

        scraper = scrape_html(html, org_url=url)
        title = scraper.title()
        image = scraper.image()
        servings = _extract_int(scraper.yields())
        prep_time = ""
        cook_time = ""
        total_time = ""
        try:
            prep_time = f"{scraper.prep_time()} min"
        except Exception:
            pass
        try:
            cook_time = f"{scraper.cook_time()} min"
        except Exception:
            pass
        try:
            total_time = f"{scraper.total_time()} min"
        except Exception:
            pass

        ingredients = scraper.ingredients()

        raw_steps = []
        try:
            raw_steps = scraper.instructions_list()
        except Exception:
            raw_steps = scraper.instructions().split("\n")

        steps = [{"text": s, "image": None} for s in raw_steps if s.strip()]

        return _build_response(
            title=title, image=image, servings=servings,
            prep_time=prep_time, cook_time=cook_time,
            total_time=total_time,
            ingredients=ingredients, steps=steps,
        )
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Strategy 2 — JSON-LD
# ---------------------------------------------------------------------------

def _try_json_ld(soup: BeautifulSoup) -> dict | None:
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
        except (json.JSONDecodeError, TypeError):
            continue

        recipes = []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    recipes.append(item)
        elif isinstance(data, dict):
            if data.get("@type") == "Recipe" or (
                isinstance(data.get("@type"), list) and "Recipe" in data["@type"]
            ):
                recipes.append(data)
            elif "@graph" in data:
                for item in data["@graph"]:
                    if isinstance(item, dict) and (
                        item.get("@type") == "Recipe"
                        or (isinstance(item.get("@type"), list) and "Recipe" in item["@type"])
                    ):
                        recipes.append(item)

        for recipe in recipes:
            image = recipe.get("image", "")
            if isinstance(image, list):
                image = image[0] if image else ""
            if isinstance(image, dict):
                image = image.get("url", "")

            raw_steps = recipe.get("recipeInstructions", [])
            steps = _normalize_steps(raw_steps)

            return _build_response(
                title=recipe.get("name", ""),
                image=image,
                servings=_extract_int(recipe.get("recipeYield")),
                prep_time=_iso_duration_to_str(recipe.get("prepTime")),
                cook_time=_iso_duration_to_str(recipe.get("cookTime")),
                total_time=_iso_duration_to_str(recipe.get("totalTime")),
                ingredients=_normalize_ingredients(recipe.get("recipeIngredient")),
                steps=steps,
            )
    return None


# ---------------------------------------------------------------------------
# Strategy 3 — CSS heuristic parsing
# ---------------------------------------------------------------------------

def _try_heuristic(soup: BeautifulSoup) -> dict | None:
    title = ""
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(strip=True)
    if not title:
        h2 = soup.find("h2")
        if h2:
            title = h2.get_text(strip=True)

    # Image — look for large hero images
    image = ""
    for img in soup.find_all("img"):
        src = img.get("src", "")
        if not src:
            continue
        width = img.get("width")
        if width and str(width).isdigit() and int(width) < 200:
            continue
        if any(kw in (img.get("class") or []) for kw in ["hero", "recipe", "featured"]):
            image = src
            break
        if any(kw in src.lower() for kw in ["recipe", "hero", "featured", "main"]):
            image = src
            break
    if not image:
        og = soup.find("meta", property="og:image")
        if og:
            image = og.get("content", "")

    # Ingredients — look for common selectors
    ingredients = []
    ingredient_selectors = [
        {"class_": re.compile(r"ingredient", re.I)},
        {"attrs": {"itemprop": "recipeIngredient"}},
        {"attrs": {"itemprop": "ingredients"}},
    ]
    for sel in ingredient_selectors:
        found = soup.find_all("li", **sel)
        if found:
            ingredients = [li.get_text(strip=True) for li in found]
            break
    if not ingredients:
        for ul in soup.find_all("ul"):
            cls = " ".join(ul.get("class", []))
            if re.search(r"ingredient", cls, re.I):
                ingredients = [li.get_text(strip=True) for li in ul.find_all("li")]
                break

    # Steps
    steps = []
    step_selectors = [
        {"class_": re.compile(r"instruction|direction|step", re.I)},
        {"attrs": {"itemprop": "recipeInstructions"}},
    ]
    for sel in step_selectors:
        found = soup.find_all(["li", "p", "div"], **sel)
        if found:
            steps = [{"text": el.get_text(strip=True), "image": None} for el in found]
            break
    if not steps:
        for ol in soup.find_all("ol"):
            cls = " ".join(ol.get("class", []))
            if re.search(r"instruction|direction|step", cls, re.I):
                steps = [
                    {"text": li.get_text(strip=True), "image": None}
                    for li in ol.find_all("li")
                ]
                break

    if not ingredients and not steps:
        return None

    return _build_response(
        title=title, image=image,
        ingredients=ingredients, steps=steps,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/")
async def serve_frontend():
    return FileResponse(INDEX_PATH, media_type="text/html")


@app.get("/recipe")
async def get_recipe(url: str = Query(..., description="Recipe page URL")):
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=20) as client:
            resp = await client.get(url, headers=HEADERS)
            resp.raise_for_status()
            html = resp.text
    except httpx.HTTPStatusError as e:
        return JSONResponse(
            {"error": f"Site returned HTTP {e.response.status_code}"},
            status_code=502,
        )
    except Exception as e:
        return JSONResponse(
            {"error": f"Could not fetch URL: {e}"},
            status_code=502,
        )

    # Strategy 1: recipe-scrapers
    result = _try_recipe_scrapers(url, html)
    if result:
        result["_source"] = "recipe-scrapers"
        return result

    soup = BeautifulSoup(html, "html.parser")

    # Strategy 2: JSON-LD
    result = _try_json_ld(soup)
    if result:
        result["_source"] = "json-ld"
        return result

    # Strategy 3: CSS heuristics
    result = _try_heuristic(soup)
    if result:
        result["_source"] = "heuristic"
        return result

    return JSONResponse(
        {"error": "Could not find recipe data on this page. The site may not have a supported recipe format."},
        status_code=422,
    )


if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)

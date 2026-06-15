from pathlib import Path
import importlib.util
import json
import os
import tempfile
import uuid

from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

DEFAULT_PATH = Path(__file__).resolve().parent / "upload_recipes.py"
ETL_PATH = Path(os.getenv("ETL_NODE_PATH", DEFAULT_PATH)).resolve()

app = FastAPI(title="Recipe Ingest API")

# ── lazy-load ingest so the heavy models only init once ───────────────────────
_ingest_fn = None

def _get_ingest():
    """Load ingest() from upload_recipes.py on first call, cache thereafter."""
    global _ingest_fn
    if _ingest_fn is None:
        from upload_recipes import ingest
        _ingest_fn = ingest
    return _ingest_fn


# ══════════════════════════════════════════════════════════════════════════════
# SCHEMA
# ══════════════════════════════════════════════════════════════════════════════

class Dish(BaseModel):
    id:            Optional[str]       = None
    name:          str                          # maps to → title
    ingredients:   list[str]
    cookingMethod: Optional[str] = None         # maps to → instructions

class DishesPayload(BaseModel):
    dishes: list[Dish]
    dry_run: bool = False


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _dishes_to_recipe_json(dishes: list[Dish]) -> dict:
    """
    Convert the dishes.json schema into the {uuid: recipe} format
    that ingest_recipes.ingest() expects.

    dishes.json field   →   ingest_recipes field
    -----------------       --------------------
    name                →   title
    ingredients         →   ingredients  (list[str])
    cookingMethod       →   instructions
    id                  →   used as the recipe key (uuid4 if absent)
    """
    return {
        (dish.id or str(uuid.uuid4())): {
            "title":        dish.name,
            "ingredients":  dish.ingredients,
            "instructions": dish.cookingMethod or "",
            "picture_link": None,
        }
        for dish in dishes
    }


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ingest/json", status_code=202)
def ingest_from_body(payload: DishesPayload, background_tasks: BackgroundTasks):
    """
    Accept dishes as a JSON body and ingest them into Qdrant.

    Example body (matches dishes.json structure):
    {
        "dishes": [
            {
                "id": "25b6ef16-...",
                "name": "Egg Fried Rice",
                "ingredients": ["Rice", "Egg", "Soy sauce"],
                "cookingMethod": "Fry rice with egg and soy sauce"
            }
        ]
    }
    """
    if not payload.dishes:
        raise HTTPException(status_code=400, detail="dishes list is empty")

    recipe_dict = _dishes_to_recipe_json(payload.dishes)

    # Write to a temp file so ingest() can stream it
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    )
    json.dump(recipe_dict, tmp, ensure_ascii=False)
    tmp.close()

    def _run(path: str, dry_run):
        try:
            _get_ingest()(path, dry_run=dry_run)
        finally:
            os.unlink(path)

    background_tasks.add_task(_run, tmp.name, payload.dry_run)

    return {
        "status":  "accepted",
        "dry_run":  payload.dry_run,
        "queued":  len(payload.dishes),
        "ids":     list(recipe_dict.keys()),
        "message": "Recipes are being processed and uploaded to Qdrant.",
    }


@app.post("/ingest/file", status_code=202)
async def ingest_from_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    """
    Accept a dishes.json file upload and ingest it into Qdrant.

    The file must be a JSON file matching the dishes.json structure:
    { "dishes": [ { "id", "name", "ingredients", "cookingMethod" }, ... ] }
    """
    if not file.filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="Only .json files are accepted")

    raw = await file.read()
    try:
        body = json.loads(raw)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")

    # Validate via pydantic
    try:
        payload = DishesPayload(**body)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))

    if not payload.dishes:
        raise HTTPException(status_code=400, detail="dishes list is empty")

    recipe_dict = _dishes_to_recipe_json(payload.dishes)

    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    )
    json.dump(recipe_dict, tmp, ensure_ascii=False)
    tmp.close()

    def _run(path: str):
        try:
            _get_ingest()(path)
        finally:
            os.unlink(path)

    background_tasks.add_task(_run, tmp.name)

    return {
        "status":   "accepted",
        "filename": file.filename,
        "queued":   len(payload.dishes),
        "ids":      list(recipe_dict.keys()),
        "message":  "Recipes are being processed and uploaded to Qdrant.",
    }
    
    
# python -m uvicorn app:app --host 127.0.0.1 --port 6000 
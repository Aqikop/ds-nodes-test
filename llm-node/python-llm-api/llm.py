"""
food_rag_pipeline.py
────────────────────
Two-collection RAG pipeline for a food assistant.

Collections:
  recipes   — dish names, ingredients, cooking instructions
  nutrition — per-100g macros for individual food items

Flow:
  user query
    → decompose_routing()     (Gemini: parse intent + filters)
    → retrieve()              (Qdrant: vector search + metadata filters)
    → generate_answer()       (Gemini: format final response)
"""

import os
import json
from dataclasses import dataclass, field
from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser


from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import Document

# ── Environment ────────────────────────────────────────────────────────────────

load_dotenv()

os.environ["LANGSMITH_TRACING"] = "true"
os.environ["LANGSMITH_API_KEY"] = os.getenv("LANGCHAIN_API_KEY", "")
os.environ["GOOGLE_API_KEY"]    = os.getenv("GOOGLE_API_KEY", "")
os.environ["QDRANT_API_KEY"]    = os.getenv("QDRANT_API_KEY", "")

# ── Clients (singletons — created once, reused everywhere) ────────────────────

gemini_model = ChatGoogleGenerativeAI(model="gemini-2.5-flash-lite")

qdrant_client = QdrantClient(
    url="https://cf19a9b2-fef9-49a9-96b2-003c18348045.eu-central-1-0.aws.cloud.qdrant.io:6333",
    api_key=os.environ.get("QDRANT_API_KEY"),
    cloud_inference=True,
)

EMBED_MODEL      = "sentence-transformers/all-minilm-l6-v2"
RECIPES_COL      = "recipes"
NUTRITION_COL    = "nutrition"

# ══════════════════════════════════════════════════════════════════════════════
# STAGE 1 — DECOMPOSE & ROUTE
# ══════════════════════════════════════════════════════════════════════════════

_DECOMPOSE_PROMPT = """You are a query parser for a food assistant. Your job is to parse the user's natural language query into a structured JSON that drives recipe retrieval.

The system uses a single collection — **recipes_nutrition** — which contains recipe instructions, ingredients, and full nutritional information per dish.

═══════════════════════════════════════════════════════════
WHAT THIS COLLECTION SUPPORTS
═══════════════════════════════════════════════════════════

You can answer queries about:
  → What to cook, recipe ideas, cooking methods, dish names
  → Meal type, cuisine, ingredients on hand
  → Calories, protein, fat, carbs, fiber, sugar, sodium per dish
  → Diet constraints (keto, vegan, gluten-free, etc.)
  → "Is X healthy", "high protein meals", "low sodium dinner ideas"

═══════════════════════════════════════════════════════════
FILTER FIELDS
═══════════════════════════════════════════════════════════

── Recipe ───────────────────────────────────────────────
mealType         : main_course | side_dish | dessert | snack | breakfast |
                   soup_stew | salad | beverage | bread_pastry | sauce_condiment
cuisine          : american | italian | asian | mexican | mediterranean |
                   french | indian | japanese | thai | chinese | spanish |
                   greek | german | british | latin_american | middle_eastern | other
cookingMethod    : baked | grilled | slow_cooker | stovetop | fried |
                   steamed | no_cook | pressure  (list — can have multiple)
mainProtein      : chicken | beef | pork | salmon | shrimp | turkey | lamb |
                   tofu | tuna | crab | sausage | bacon | duck | veal | other
dietFlags        : vegetarian | vegan | gluten_free | dairy_free | nut_free
                   (list — can have multiple)
maxIngredients   : integer  (max number of ingredients)
maxCookTime      : integer in minutes
hasPicture       : boolean  (true = must have photo | false = exclude photos | null = no preference)

── Nutrition (all values are per whole dish / per serving) ──
maxCalories      : number  — kcal
minProtein       : number  — grams
maxFat           : number  — grams
maxCarbs         : number  — grams
minFiber         : number  — grams
maxSugar         : number  — grams
maxSodium        : number  — milligrams (always use mg; do NOT convert to grams)
isHighProtein    : boolean  (true = high protein dishes only | null = no preference)
isLowCarb        : boolean  (true = low carb / keto only | null = no preference)
isLowCalorie     : boolean  (true = low calorie / diet-friendly only | null = no preference)

── Ingredients on hand ──────────────────────────────────
ingredientsList      : [string] | null
                       Lowercase ingredient names the user already has.
                       Populate when user says "I have X, Y, Z" or "using X and Y".
ingredientUnits      : [string] | null
                       Parallel array — unit per ingredient, null where unspecified.
ingredientQuantities : [number] | null
                       Parallel array — numeric amount per ingredient, null where unspecified.
                       All three arrays must have equal length when populated.

═══════════════════════════════════════════════════════════
QUERY REWRITING
═══════════════════════════════════════════════════════════

Rewrite the user query as a clean, descriptive phrase for vector search:
  - Remove filler: "something", "maybe", "I want", "can you find", "I have"
  - Preserve food names, diet terms, cuisine words exactly
  - If the user lists ingredients they have, turn them into a dish description:
    "I have chicken, garlic, lemon" → "chicken garlic lemon dinner"
  - If the query is purely nutritional ("how much protein in pasta carbonara"),
    rewrite as a dish name: "pasta carbonara"

═══════════════════════════════════════════════════════════
SODIUM NOTE
═══════════════════════════════════════════════════════════

maxSodium is in **milligrams**. Do not convert.
  "low sodium" (no number given) → maxSodium: 600
  "140mg sodium"                 → maxSodium: 140
  "heart healthy"                → maxSodium: 600  (standard low-sodium threshold)

═══════════════════════════════════════════════════════════
OUTPUT SCHEMA  (return ONLY valid JSON — no markdown, no explanation)
═══════════════════════════════════════════════════════════

{{
  "query": string,
  "filters": {{
    "mealType":              null | string,
    "cuisine":               null | string,
    "cookingMethod":         null | [string],
    "mainProtein":           null | string,
    "dietFlags":             null | [string],
    "maxIngredients":        null | number,
    "maxCookTime":           null | number,
    "hasPicture":            null | boolean,
    "maxCalories":           null | number,
    "minProtein":            null | number,
    "maxFat":                null | number,
    "maxCarbs":              null | number,
    "minFiber":              null | number,
    "maxSugar":              null | number,
    "maxSodium":             null | number,
    "isHighProtein":         null | boolean,
    "isLowCarb":             null | boolean,
    "isLowCalorie":          null | boolean,
    "ingredientsList":       null | [string],
    "ingredientUnits":       null | [string],
    "ingredientQuantities":  null | [number]
  }},
  "reason": string
}}

═══════════════════════════════════════════════════════════
EXAMPLES
═══════════════════════════════════════════════════════════

User: "quick Italian pasta recipes"
{{"query":"quick Italian pasta dinner","filters":{{"mealType":"main_course","cuisine":"italian","cookingMethod":["stovetop"],"mainProtein":null,"dietFlags":null,"maxIngredients":null,"maxCookTime":30,"hasPicture":null,"maxCalories":null,"minProtein":null,"maxFat":null,"maxCarbs":null,"minFiber":null,"maxSugar":null,"maxSodium":null,"isHighProtein":null,"isLowCarb":null,"isLowCalorie":null,"ingredientsList":null,"ingredientUnits":null,"ingredientQuantities":null}},"reason":"Recipe search with cuisine and time filter."}}

User: "high protein low carb chicken dinner under 30 minutes"
{{"query":"high protein low carb chicken dinner","filters":{{"mealType":"main_course","cuisine":null,"cookingMethod":null,"mainProtein":"chicken","dietFlags":null,"maxIngredients":null,"maxCookTime":30,"hasPicture":null,"maxCalories":null,"minProtein":20.0,"maxFat":null,"maxCarbs":10.0,"minFiber":null,"maxSugar":null,"maxSodium":null,"isHighProtein":true,"isLowCarb":true,"isLowCalorie":null,"ingredientsList":null,"ingredientUnits":null,"ingredientQuantities":null}},"reason":"Protein and carb constraints extracted; cook time filter applied."}}

User: "low sodium heart healthy dinner ideas"
{{"query":"heart healthy low sodium dinner","filters":{{"mealType":"main_course","cuisine":null,"cookingMethod":null,"mainProtein":null,"dietFlags":null,"maxIngredients":null,"maxCookTime":null,"hasPicture":null,"maxCalories":null,"minProtein":null,"maxFat":null,"maxCarbs":null,"minFiber":null,"maxSugar":null,"maxSodium":600,"isHighProtein":null,"isLowCarb":null,"isLowCalorie":null,"ingredientsList":null,"ingredientUnits":null,"ingredientQuantities":null}},"reason":"Heart-healthy implies low sodium threshold of 600mg."}}

User: "how many calories in pasta carbonara"
{{"query":"pasta carbonara","filters":{{"mealType":null,"cuisine":"italian","cookingMethod":null,"mainProtein":null,"dietFlags":null,"maxIngredients":null,"maxCookTime":null,"hasPicture":null,"maxCalories":null,"minProtein":null,"maxFat":null,"maxCarbs":null,"minFiber":null,"maxSugar":null,"maxSodium":null,"isHighProtein":null,"isLowCarb":null,"isLowCalorie":null,"ingredientsList":null,"ingredientUnits":null,"ingredientQuantities":null}},"reason":"Nutritional lookup — rewritten as dish name for vector search."}}

User: "I have 200g chicken breast, 3 cloves of garlic, and some olive oil — what can I make?"
{{"query":"chicken breast garlic olive oil dinner","filters":{{"mealType":null,"cuisine":null,"cookingMethod":null,"mainProtein":"chicken","dietFlags":null,"maxIngredients":null,"maxCookTime":null,"hasPicture":null,"maxCalories":null,"minProtein":null,"maxFat":null,"maxCarbs":null,"minFiber":null,"maxSugar":null,"maxSodium":null,"isHighProtein":null,"isLowCarb":null,"isLowCalorie":null,"ingredientsList":["chicken breast","garlic","olive oil"],"ingredientUnits":["grams","cloves",null],"ingredientQuantities":[200,3,null]}},"reason":"Ingredients-on-hand query; parallel arrays populated with available quantities."}}

User: "vegan gluten-free breakfast with pictures"
{{"query":"vegan gluten-free breakfast","filters":{{"mealType":"breakfast","cuisine":null,"cookingMethod":null,"mainProtein":"tofu","dietFlags":["vegan","gluten_free"],"maxIngredients":null,"maxCookTime":null,"hasPicture":true,"maxCalories":null,"minProtein":null,"maxFat":null,"maxCarbs":null,"minFiber":null,"maxSugar":null,"maxSodium":null,"isHighProtein":null,"isLowCarb":null,"isLowCalorie":null,"ingredientsList":null,"ingredientUnits":null,"ingredientQuantities":null}},"reason":"Diet flags and meal type set; hasPicture true because user explicitly asked."}}

Now parse this query:
User: "{user_query}"
"""

# Build chain once at module level — reused on every call
_decompose_chain = (
    ChatPromptTemplate.from_template(_DECOMPOSE_PROMPT)
    | gemini_model
    | StrOutputParser()   # keep as string — Java expects JSON, not Python dict
)



def decompose_routing(user_query: str) -> str:
    """
    Parse user query into structured JSON string for downstream Java processing.
    Returns a valid JSON string — never a Python dict.
    """
    raw = _decompose_chain.invoke({"user_query": user_query})

    # Strip markdown fences Gemini occasionally adds
    clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    # Validate it's actually parseable JSON before sending to Java
    try:
        json.loads(clean)
    except json.JSONDecodeError as e:
        raise ValueError(f"[decompose_routing] Gemini returned invalid JSON: {e}\nRaw: {clean[:300]}")

    print(f"[decompose_routing] intent: {clean}")
    return clean  # str — valid JSON


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 2 — RETRIEVE
# ══════════════════════════════════════════════════════════════════════════════

def build_recipe_filter(recipe_filters: dict) -> models.Filter | None:
    """Map recipe_filters dict → Qdrant Filter."""
    if not recipe_filters:
        return None

    must = []

    # Exact string / boolean matches
    for field in ["meal_type", "cuisine", "main_protein", "has_picture"]:
        val = recipe_filters.get(field)
        if val is not None:
            must.append(models.FieldCondition(
                key=field,
                match=models.MatchValue(value=val)
            ))

    # List fields — match any element
    for field in ["cooking_method", "diet_flags"]:
        val = recipe_filters.get(field)
        if val:
            must.append(models.FieldCondition(
                key=field,
                match=models.MatchAny(any=val)
            ))

    # Numeric upper bounds
    if recipe_filters.get("max_ingredients") is not None:
        must.append(models.FieldCondition(
            key="ingredient_count",
            range=models.Range(lte=recipe_filters["max_ingredients"])
        ))
    if recipe_filters.get("max_cook_time") is not None:
        must.append(models.FieldCondition(
            key="estimated_cook_time_min",
            range=models.Range(lte=recipe_filters["max_cook_time"])
        ))

    return models.Filter(must=must) if must else None


def build_nutrition_filter(nutrition_filters: dict) -> models.Filter | None:
    """Map nutrition_filters dict → Qdrant Filter.
    NOTE: sodium is stored in grams — max_sodium_g maps directly, no conversion needed.
    """
    if not nutrition_filters:
        return None

    must = []

    if nutrition_filters.get("food_name"):
        must.append(models.FieldCondition(
            key="food_name",
            match=models.MatchValue(value=nutrition_filters["food_name"])
        ))

    # Boolean flags — only filter when explicitly True
    for field in ["is_high_protein", "is_low_carb", "is_low_calorie"]:
        if nutrition_filters.get(field) is True:
            must.append(models.FieldCondition(
                key=field,
                match=models.MatchValue(value=True)
            ))

    # Numeric range filters
    range_map = {
        "max_calories": ("calories", "lte"),
        "min_protein":  ("protein",  "gte"),
        "max_fat":      ("fat",      "lte"),
        "max_carbs":    ("carbs",    "lte"),
        "min_fiber":    ("fiber",    "gte"),
        "max_sugar":    ("sugar",    "lte"),
        "max_sodium_g": ("sodium",   "lte"),
    }
    for filter_key, (payload_key, operator) in range_map.items():
        val = nutrition_filters.get(filter_key)
        if val is not None:
            must.append(models.FieldCondition(
                key=payload_key,
                range=models.Range(**{operator: val})
            ))

    return models.Filter(must=must) if must else None


def query_collection(
    collection_name: str,
    search_text: str,
    query_filter: models.Filter | None,
    limit: int = 5,
) -> list:
    """Run a single Qdrant vector search and return ScoredPoint list."""
    if not search_text.strip():
        print(f"[query_collection] Empty search text for '{collection_name}' — skipping.")
        return []

    print(f"\n[{collection_name}] query  : '{search_text}'")
    print(f"[{collection_name}] filter : {query_filter}")

    results = qdrant_client.query_points(
        collection_name=collection_name,
        query=Document(text=search_text, model=EMBED_MODEL),
        query_filter=query_filter,
        limit=limit,
    )
    return results.points


def _ingredient_nutrition_lookup(recipe_points: list) -> list:
    """
    Per-ingredient nutrition lookup for estimate_nutrition queries.
    Extracts ingredients from each recipe's text and searches nutrition collection.
    """
    all_nutrition = []
    for point in recipe_points:
        # Parse ingredients from the structured text field
        text = point.payload.get("text", "")
        try:
            ing_block = text.split("Ingredients:\n")[1].split("\n\nInstructions:")[0]
            ingredients = [
                line.lstrip("- ").strip()
                for line in ing_block.splitlines()
                if line.strip()
            ]
        except IndexError:
            ingredients = []

        for ingredient in ingredients[:4]:  # top 4 per recipe to limit API calls
            hits = query_collection(NUTRITION_COL, ingredient, None, limit=1)
            all_nutrition.extend(hits)

    return all_nutrition


def retrieve(user_query: str, intent: dict, limit: int = 5) -> dict:
    """
    Route intent to correct Qdrant collection(s) and return results.

    Args:
        user_query : original user question (fallback search text)
        intent     : output of decompose_routing()
        limit      : max results per collection

    Returns:
        {
            "intent":    intent dict,
            "recipes":   list[ScoredPoint],
            "nutrition": list[ScoredPoint],
        }
    """
    if not intent:
        print("[retrieve] Empty intent — falling back to recipe semantic search.")
        return {
            "intent": {},
            "recipes": query_collection(RECIPES_COL, user_query, None, limit),
            "nutrition": [],
        }

    collections        = intent.get("collections", [RECIPES_COL])
    estimate_nutrition = intent.get("estimate_nutrition", False)
    recipe_query       = intent.get("recipe_query") or user_query
    nutrition_query    = intent.get("nutrition_query") or user_query

    output = {"intent": intent, "recipes": [], "nutrition": []}

    if RECIPES_COL in collections:
        recipe_filter      = build_recipe_filter(intent.get("recipe_filters") or {})
        output["recipes"]  = query_collection(RECIPES_COL, recipe_query, recipe_filter, limit)

    if NUTRITION_COL in collections:
        if estimate_nutrition and output["recipes"]:
            # Ingredient-level lookup instead of direct nutrition search
            output["nutrition"] = _ingredient_nutrition_lookup(output["recipes"])
        else:
            nutrition_filter      = build_nutrition_filter(intent.get("nutrition_filters") or {})
            output["nutrition"]   = query_collection(NUTRITION_COL, nutrition_query, nutrition_filter, limit)

    return output


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 3 — GENERATE ANSWER
# ══════════════════════════════════════════════════════════════════════════════

def _format_recipe_point(point, rank: int, user_ingredients: list[str] | None) -> str:
    """Format a single recipe ScoredPoint as a context block for the LLM."""
    payload        = point.payload
    text           = payload.get("text", "")
    cook_time      = payload.get("estimated_cook_time_min")
    diet_flags     = payload.get("diet_flags") or []
    cooking_method = payload.get("cooking_method") or []

    time_str = (
        f"{cook_time} min"       if cook_time and 0 < cook_time <= 300 else
        f"{cook_time // 60} hrs" if cook_time and cook_time > 300      else
        "not specified"
    )

    overlap_line = ""
    if user_ingredients:
        matched = [i for i in user_ingredients if i.lower() in text.lower()]
        if matched:
            overlap_line = f"Matched your ingredients: {', '.join(matched)}\n"

    return (
        f"[Recipe {rank}]\n"
        f"{overlap_line}"
        f"Cook time : {time_str}\n"
        f"Method    : {', '.join(cooking_method) or 'not specified'}\n"
        f"Diet      : {', '.join(diet_flags) or 'none'}\n"
        f"Score     : {point.score:.3f}\n"
        f"---\n"
        f"{text}"
    )


def _format_nutrition_point(point, rank: int) -> str:
    """Format a single nutrition ScoredPoint as a context block for the LLM."""
    payload    = point.payload
    sodium_g   = payload.get("sodium")
    sodium_str = f"{round(sodium_g * 1000, 1)}mg" if sodium_g is not None else "N/A"

    return (
        f"[Nutrition {rank}] {payload.get('food_name', 'unknown').title()}\n"
        f"Calories : {payload.get('calories', 'N/A')} kcal | "
        f"Protein  : {payload.get('protein',  'N/A')}g | "
        f"Fat      : {payload.get('fat',      'N/A')}g | "
        f"Carbs    : {payload.get('carbs',    'N/A')}g | "
        f"Fiber    : {payload.get('fiber',    'N/A')}g | "
        f"Sugar    : {payload.get('sugar',    'N/A')}g | "
        f"Sodium   : {sodium_str}\n"
        f"Score    : {point.score:.3f}"
    )


def _build_context(
    results: dict,
    user_ingredients: list[str] | None,
) -> tuple[str, str]:
    """Build recipe_section and nutrition_section strings for prompt injection."""

    # Recipe section
    recipe_points = results.get("recipes", [])[:3]
    if recipe_points:
        blocks = [_format_recipe_point(p, i + 1, user_ingredients)
                  for i, p in enumerate(recipe_points)]
        recipe_section = (
            "RETRIEVED RECIPES\n"
            "════════════════════════════════════════════════════════\n"
            + "\n\n".join(blocks) + "\n\n"
        )
    else:
        recipe_section = "RETRIEVED RECIPES\nNo recipes found.\n\n"

    # Nutrition section
    nutrition_points = results.get("nutrition", [])[:5]
    if nutrition_points:
        blocks = [_format_nutrition_point(p, i + 1)
                  for i, p in enumerate(nutrition_points)]
        nutrition_section = (
            "RETRIEVED NUTRITION DATA\n"
            "════════════════════════════════════════════════════════\n"
            + "\n".join(blocks) + "\n\n"
        )
    else:
        nutrition_section = ""

    return recipe_section, nutrition_section


_ANSWER_PROMPT = """\
You are a helpful food assistant. Answer the user's request using ONLY the retrieved data below.

User query: "{user_query}"

{recipe_section}{nutrition_section}\
════════════════════════════════════════════════════════
INSTRUCTIONS
════════════════════════════════════════════════════════

General rules:
- Answer using only retrieved data — never invent recipes, ingredients, or nutrition values
- If nothing was retrieved, say so clearly and suggest the user broaden their search
- Be friendly, concise, and scannable

Recipe queries → format each result as:
**[Recipe Name]**
- Cook time   : [X min / X hrs / not specified]
- Method      : [cooking method]
- Diet        : [diet flags, or "none"]
- Ingredients : [if user searched by ingredient, list matched ones first, then remaining]
- Instructions: [full instructions from the retrieved text]
- Summary     : [one sentence]

Nutrition queries → format as:
**[Food Name]** — [X kcal | Xg protein | Xg fat | Xg carbs | Xg fiber | Xg sugar | Xmg sodium]
Add a one-line interpretation, e.g. "High protein, low carb — good for keto."

Estimate nutrition queries → format as:
**Estimated nutrition for [Recipe Name]**
Per serving: [X kcal | Xg protein | Xg fat | Xg carbs]
(Based on individual ingredient lookups — estimate only)

Combined queries (recipes + nutrition) →
- Lead with the recipes
- Follow with a brief nutrition note for the key ingredients
- If the user asked "is this healthy", give a clear yes/no with a one-line reason

Ranking: present up to 3 recipes, best match first (highest score)
"""

_answer_chain = (
    ChatPromptTemplate.from_template(_ANSWER_PROMPT)
    | gemini_model
    | StrOutputParser()
)


def generate_answer(
    user_query: str,
    results: dict,
    user_ingredients: list[str] | None = None,
) -> str:
    """
    Format retrieved documents into prompt context and generate final answer.

    Args:
        user_query       : original user question
        results          : output of retrieve()
        user_ingredients : ingredient keywords from user query for overlap highlighting
    """
    recipe_section, nutrition_section = _build_context(results, user_ingredients)

    answer = _answer_chain.invoke({
        "user_query":        user_query,
        "recipe_section":    recipe_section,
        "nutrition_section": nutrition_section,
    })

    return answer


# ══════════════════════════════════════════════════════════════════════════════
# DISPLAY HELPER
# ══════════════════════════════════════════════════════════════════════════════

def display_results(results: dict) -> None:
    """Pretty-print raw retrieval results (for debugging)."""
    intent = results.get("intent", {})
    print(f"\nReason  : {intent.get('reason', 'N/A')}")
    print(f"Estimate: {intent.get('estimate_nutrition', False)}")

    if results["recipes"]:
        print(f"\n── Recipes ({len(results['recipes'])}) ──────────────────────────")
        for p in results["recipes"]:
            cook_time = p.payload.get("estimated_cook_time_min")
            time_str  = f"{cook_time} min" if cook_time and cook_time > 0 else "time unknown"
            print(
                f"  [{p.score:.3f}] {p.payload.get('title', 'Unknown')}"
                f"  ({p.payload.get('cuisine', '')} · "
                f"{p.payload.get('meal_type', '')} · {time_str})"
            )

    if results["nutrition"]:
        print(f"\n── Nutrition ({len(results['nutrition'])}) ──────────────────────")
        for p in results["nutrition"]:
            sodium_g   = p.payload.get("sodium")
            sodium_str = f"{round(sodium_g * 1000)}mg" if sodium_g is not None else "N/A"
            print(
                f"  [{p.score:.3f}] {p.payload.get('food_name', 'Unknown')}"
                f"  ({p.payload.get('calories', 'N/A')} kcal · "
                f"{p.payload.get('protein', 'N/A')}g protein · "
                f"{p.payload.get('carbs', 'N/A')}g carbs · {sodium_str} sodium)"
            )


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    question = "Find a vegetarian baked dessert under 20 minutes"

    # Stage 1 — decompose
    intent = decompose_routing(question)

    # Stage 2 — retrieve
    results = retrieve(
        user_query=question,
        intent=intent,
        limit=5,
    )
    display_results(results)

    # Stage 3 — generate answer
    # Extract protein keyword for ingredient overlap highlighting
    protein = (intent.get("recipe_filters") or {}).get("main_protein")
    user_ingredients = [protein] if protein else None

    answer = generate_answer(
        user_query=question,
        results=results,
        user_ingredients=user_ingredients,
    )
    print("\n── Final Answer ─────────────────────────────────────────")
    print(answer)
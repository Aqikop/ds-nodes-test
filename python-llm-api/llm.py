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

_DECOMPOSE_PROMPT = """You are a query decomposer for a food assistant with two Qdrant collections.

Your job: parse the user query into a structured JSON that drives retrieval.

═══════════════════════════════════════════════════════════
COLLECTIONS
═══════════════════════════════════════════════════════════

① recipes2.1 — dish names, ingredients, cooking instructions
② nutrition  — per-100g macros for individual food items

═══════════════════════════════════════════════════════════
ROUTING RULES  (choose one or both collections)
═══════════════════════════════════════════════════════════

Use recipes2.1 when the user asks:
  → what to cook, how to cook, recipe ideas, cooking method,
    meal type, cuisine, ingredient combinations, dish names,
    what to make with ingredients they already have

Use nutrition when the user asks:
  → calories, protein, fat, carbs, fiber, sugar, sodium,
    macros, nutritional facts, "is X healthy", "how much protein in X"

Use BOTH when the user asks:
  → "high protein chicken recipes"    (recipe + nutrition constraint)
  → "keto dinner ideas"               (recipe filtered by diet, validate macros)
  → "how many calories in pasta carbonara" (recipe to identify dish + nutrition lookup)
  → "low sodium meals I can cook"     (recipe search + sodium filter on ingredients)

═══════════════════════════════════════════════════════════
FILTER FIELDS
═══════════════════════════════════════════════════════════

── recipes2.1 ───────────────────────────────────────────
meal_type          : main_course | side_dish | dessert | snack | breakfast |
                     soup_stew | salad | beverage | bread_pastry | sauce_condiment
cuisine            : american | italian | asian | mexican | mediterranean |
                     french | indian | japanese | thai | chinese | spanish |
                     greek | german | british | latin_american | middle_eastern | other
cooking_method     : baked | grilled | slow_cooker | stovetop | fried |
                     steamed | no_cook | pressure  (list — can have multiple)
main_protein       : chicken | beef | pork | salmon | shrimp | turkey | lamb |
                     tofu | tuna | crab | sausage | bacon | duck | veal | other
diet_flags         : vegetarian | vegan | gluten_free | dairy_free | nut_free
                     (list — can have multiple)
max_ingredients    : integer  (maps to ingredient_count lte)
max_cook_time      : integer in minutes  (maps to estimated_cook_time_min lte)
has_picture        : true | false  (only set true when user explicitly asks for photo)
ingredients_list   : [string] | null
                     List of ingredient names the user has on hand.
                     Populate when the user says "I have X, Y, Z" or "using X and Y".
                     Each entry should be a clean, lowercase ingredient name
                     (e.g. ["chicken breast", "garlic", "olive oil"]).
ingredient_units   : [string] | null
                     Parallel array to ingredients_list — unit for each ingredient
                     (e.g. ["grams", "cloves", "tablespoons"]).
                     Use null for entries where no unit was specified.
ingredient_quantities : [number] | null
                     Parallel array to ingredients_list — numeric quantity for each
                     ingredient (e.g. [200, 3, 2]).
                     Use null for entries where no quantity was specified.
                     All three arrays (ingredients_list, ingredient_units,
                     ingredient_quantities) must have the same length when populated.

── nutrition ────────────────────────────────────────────
food_name          : string  (only when a specific ingredient is clearly named)
max_calories       : number  (kcal per 100g)
min_protein        : number  (grams per 100g)
max_fat            : number  (grams per 100g)
max_carbs          : number  (grams per 100g)
min_fiber          : number  (grams per 100g)
max_sugar          : number  (grams per 100g)
max_sodium_g       : number  (grams per 100g — NOTE: stored in grams, not mg.
                              Convert user's mg to g: 140mg → 0.14)
is_high_protein    : true    (only when user says "high protein")
is_low_carb        : true    (only when user says "low carb" or "keto")
is_low_calorie     : true    (only when user says "low calorie" or "diet-friendly")

═══════════════════════════════════════════════════════════
QUERY REWRITING RULES
═══════════════════════════════════════════════════════════

- recipe_query   : rephrase as a dish description for vector search
                   e.g. "something quick" → "quick easy weeknight dinner"
                   e.g. "I have chicken, garlic, lemon" → "chicken garlic lemon dinner recipe"
- nutrition_query: rephrase as an ingredient/food item description
                   e.g. "how much protein in eggs" → "eggs protein content"
- Strip filler words: "something", "maybe", "I want", "can you find", "I have"
- Preserve food names, diet terms, cuisine words exactly

═══════════════════════════════════════════════════════════
SPECIAL INTENTS
═══════════════════════════════════════════════════════════

estimate_nutrition: true when user wants total nutrition of a full recipe
  → triggers the ingredient-level nutrition estimation pipeline
  → set collections to ["recipes2.1","nutrition"] always

═══════════════════════════════════════════════════════════
OUTPUT SCHEMA  (return ONLY valid JSON — no markdown, no explanation)
═══════════════════════════════════════════════════════════

{{
  "collections": ["recipes2.1"] | ["nutrition"] | ["recipes2.1", "nutrition"],
  "estimate_nutrition": true | false,
  "recipe_query": string | null,
  "nutrition_query": string | null,
  "recipe_filters": {{
    "meal_type":              null | string,
    "cuisine":                null | string,
    "cooking_method":         null | [string],
    "main_protein":           null | string,
    "diet_flags":             null | [string],
    "max_ingredients":        null | number,
    "max_cook_time":          null | number,
    "has_picture":            null | boolean,
    "ingredients_list":       null | [string],
    "ingredient_units":       null | [string],
    "ingredient_quantities":  null | [number]
  }},
  "nutrition_filters": {{
    "food_name":       null | string,
    "max_calories":    null | number,
    "min_protein":     null | number,
    "max_fat":         null | number,
    "max_carbs":       null | number,
    "min_fiber":       null | number,
    "max_sugar":       null | number,
    "max_sodium_g":    null | number,
    "is_high_protein": null | true,
    "is_low_carb":     null | true,
    "is_low_calorie":  null | true
  }},
  "reason": string
}}

═══════════════════════════════════════════════════════════
EXAMPLES
═══════════════════════════════════════════════════════════

User: "quick Italian pasta recipes"
{{"collections":["recipes2.1"],"estimate_nutrition":false,"recipe_query":"quick Italian pasta dinner","nutrition_query":null,"recipe_filters":{{"meal_type":"main_course","cuisine":"italian","cooking_method":["stovetop"],"main_protein":null,"diet_flags":null,"max_ingredients":null,"max_cook_time":30,"has_picture":null,"ingredients_list":null,"ingredient_units":null,"ingredient_quantities":null}},"nutrition_filters":{{"food_name":null,"max_calories":null,"min_protein":null,"max_fat":null,"max_carbs":null,"min_fiber":null,"max_sugar":null,"max_sodium_g":null,"is_high_protein":null,"is_low_carb":null,"is_low_calorie":null}},"reason":"User wants recipe ideas — cuisine and speed filter applied."}}

User: "how many calories in avocado"
{{"collections":["nutrition"],"estimate_nutrition":false,"recipe_query":null,"nutrition_query":"avocado calorie content","recipe_filters":{{"meal_type":null,"cuisine":null,"cooking_method":null,"main_protein":null,"diet_flags":null,"max_ingredients":null,"max_cook_time":null,"has_picture":null,"ingredients_list":null,"ingredient_units":null,"ingredient_quantities":null}},"nutrition_filters":{{"food_name":"avocado","max_calories":null,"min_protein":null,"max_fat":null,"max_carbs":null,"min_fiber":null,"max_sugar":null,"max_sodium_g":null,"is_high_protein":null,"is_low_carb":null,"is_low_calorie":null}},"reason":"Pure nutrition fact lookup — no recipe needed."}}

User: "high protein low carb chicken dinner under 30 minutes"
{{"collections":["recipes2.1","nutrition"],"estimate_nutrition":false,"recipe_query":"high protein low carb chicken dinner","nutrition_query":"chicken high protein low carb","recipe_filters":{{"meal_type":"main_course","cuisine":null,"cooking_method":null,"main_protein":"chicken","diet_flags":null,"max_ingredients":null,"max_cook_time":30,"has_picture":null,"ingredients_list":null,"ingredient_units":null,"ingredient_quantities":null}},"nutrition_filters":{{"food_name":null,"max_calories":null,"min_protein":20.0,"max_fat":null,"max_carbs":10.0,"min_fiber":null,"max_sugar":null,"max_sodium_g":null,"is_high_protein":true,"is_low_carb":true,"is_low_calorie":null}},"reason":"Recipe search with nutritional constraints — both collections needed."}}

User: "what are the total calories in slow cooker chicken and dumplings"
{{"collections":["recipes2.1","nutrition"],"estimate_nutrition":true,"recipe_query":"slow cooker chicken and dumplings","nutrition_query":"chicken dumplings ingredients nutrition","recipe_filters":{{"meal_type":"main_course","cuisine":null,"cooking_method":["slow_cooker"],"main_protein":"chicken","diet_flags":null,"max_ingredients":null,"max_cook_time":null,"has_picture":null,"ingredients_list":null,"ingredient_units":null,"ingredient_quantities":null}},"nutrition_filters":{{"food_name":null,"max_calories":null,"min_protein":null,"max_fat":null,"max_carbs":null,"min_fiber":null,"max_sugar":null,"max_sodium_g":null,"is_high_protein":null,"is_low_carb":null,"is_low_calorie":null}},"reason":"User wants calorie estimate — triggers ingredient-level nutrition pipeline."}}

User: "low sodium heart healthy dinner ideas"
{{"collections":["recipes2.1","nutrition"],"estimate_nutrition":false,"recipe_query":"heart healthy low sodium dinner","nutrition_query":"low sodium heart healthy foods","recipe_filters":{{"meal_type":"main_course","cuisine":null,"cooking_method":null,"main_protein":null,"diet_flags":null,"max_ingredients":null,"max_cook_time":null,"has_picture":null,"ingredients_list":null,"ingredient_units":null,"ingredient_quantities":null}},"nutrition_filters":{{"food_name":null,"max_calories":null,"min_protein":null,"max_fat":null,"max_carbs":null,"min_fiber":null,"max_sugar":null,"max_sodium_g":0.14,"is_high_protein":null,"is_low_carb":null,"is_low_calorie":null}},"reason":"Heart-healthy implies low sodium — max_sodium_g=0.14g (140mg)."}}

User: "I have 200g chicken breast, 3 cloves of garlic, and some olive oil — what can I make?"
{{"collections":["recipes2.1"],"estimate_nutrition":false,"recipe_query":"chicken breast garlic olive oil dinner recipe","nutrition_query":null,"recipe_filters":{{"meal_type":null,"cuisine":null,"cooking_method":null,"main_protein":"chicken","diet_flags":null,"max_ingredients":null,"max_cook_time":null,"has_picture":null,"ingredients_list":["chicken breast","garlic","olive oil"],"ingredient_units":["grams","cloves",null],"ingredient_quantities":[200,3,null]}},"nutrition_filters":{{"food_name":null,"max_calories":null,"min_protein":null,"max_fat":null,"max_carbs":null,"min_fiber":null,"max_sugar":null,"max_sodium_g":null,"is_high_protein":null,"is_low_carb":null,"is_low_calorie":null}},"reason":"User wants recipes using specific on-hand ingredients with quantities — ingredients_list populated with parallel unit and quantity arrays."}}

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
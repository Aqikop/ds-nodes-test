# LLM Node Contract

The LLM node is responsible only for query understanding and final answer formatting.
It does not own food data, does not search indexes, and does not merge distributed
results. Those responsibilities stay in the coordinator and search/index nodes.

This Java module is an HTTP adapter around the Python LLM API in `python-llm-api`,
which calls Stage 1 and Stage 3 from `llm.py`.

## Role In The System

```text
Client
  -> Coordinator
    -> Java LLM Node: decompose user query
      -> Python LLM API: calls test3.py
    -> Search/index nodes: retrieve recipe/nutrition results
    -> Java LLM Node: format final answer from retrieved results
      -> Python LLM API: calls test3.py
  -> Client
```

The coordinator should treat this node as a stateless REST service.

## Stage 1: Query Decomposition

Endpoint:

```text
POST /llm/decompose
```

Request body:

```json
{
  "userQuery": "high protein low carb chicken dinner under 30 minutes"
}
```

Response body:

```json
{
  "collections": ["recipes", "nutrition"],
  "estimateNutrition": false,
  "recipeQuery": "high protein low carb chicken dinner",
  "nutritionQuery": "chicken high protein low carb",
  "recipeFilters": {
    "mealType": "main_course",
    "cuisine": null,
    "cookingMethod": null,
    "mainProtein": "chicken",
    "dietFlags": null,
    "maxIngredients": null,
    "maxCookTime": 30,
    "hasPicture": null
  },
  "nutritionFilters": {
    "foodName": null,
    "maxCalories": null,
    "minProtein": 20.0,
    "maxFat": null,
    "maxCarbs": 10.0,
    "minFiber": null,
    "maxSugar": null,
    "maxSodium": null,
    "isHighProtein": true,
    "isLowCarb": true,
    "isLowCalorie": null
  },
  "reason": "Recipe search with nutrition constraints.",
  "state": "RECEIVED"
}
```

The shared DTO for this response is `UserIntent`. Extra fields returned by
`llm.py`, such as `reason` and `state`, are ignored by `UserIntent`.

Coordinator behavior after this response:

- If `collections` contains `recipes`, call the recipe/ingredient/dish search node
  with `recipeQuery` and `recipeFilters`.
- If `collections` contains `nutrition`, call the nutrition search node with
  `nutritionQuery` and `nutritionFilters`.
- If both are present, call both search paths and keep both result lists.
- If `estimateNutrition` is `true`, retrieve recipe results first, then use recipe
  ingredients to retrieve nutrition data.
- If the LLM node is unavailable, coordinator should mark the request as failed or
  fall back to a simple keyword search.

## Stage 3: Final Answer Formatting

Endpoint:

```text
POST /llm/answer
```

Request body:

```json
{
  "userQuery": "high protein low carb chicken dinner under 30 minutes",
  "recipes": [
    {
      "itemName": "Grilled Chicken Salad",
      "payload": "Dish text, ingredients, and instructions from the recipe node",
      "score": 0.91,
      "metadata": {
        "cookTime": 25,
        "mealType": "main_course"
      },
      "state": "RECEIVED"
    }
  ],
  "nutrition": [
    {
      "itemName": "chicken breast",
      "payload": "Nutrition details from nutrition node",
      "score": 0.88,
      "metadata": {
        "calories": 165,
        "protein": 31,
        "carbs": 0
      },
      "state": "RECEIVED"
    }
  ]
}
```

Response body:

```json
{
  "answer": "A concise final answer generated only from the retrieved data.",
  "recipes": [],
  "nutrition": [],
  "state": "RECEIVED"
}
```

Coordinator behavior after this response:

- Store `answer` as the final user-visible result.
- Do not ask the LLM node to invent missing recipe or nutrition data.
- If no search results exist, coordinator may still call `/llm/answer`; the LLM
  node should produce a clear "no results found" message.

## Required Shared DTOs

The shared model module should contain these DTOs so coordinator and LLM node agree
on the same JSON shape:

- `LLMRequest`: input for `/llm/decompose`
- `UserIntent`: output contract for `/llm/decompose`
- `LLMAnswerRequest`: input for `/llm/answer`
- `SearchResponse`: output from `/llm/answer`
- `RecipeFilters`
- `NutritionFilters`
- `RecipeQueryResult`
- `NutritionQueryResult`

## Runtime

Run the Python API first:

```text
python-llm-api on http://127.0.0.1:5000
```

Then run the Java LLM node:

```text
llm-node on http://localhost:8081
```

## Ownership Boundary

LLM node owns:

- User query decomposition
- Routing recommendation
- Filter extraction
- Final natural-language answer formatting

Coordinator owns:

- Request IDs and request state
- Calling LLM node
- Calling search/index nodes
- Merging search results
- Retry/fault tolerance
- Returning final response to client

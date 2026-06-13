import torch
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct, PayloadSchemaType
)
import json, uuid


device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Using: {device}")   # aim for cuda — 5x faster encoding
model = SentenceTransformer("all-MiniLM-L6-v2", device=device)

qdrant_api_key = ""

qdrant_client = QdrantClient(
    url="https://cf19a9b2-fef9-49a9-96b2-003c18348045.eu-central-1-0.aws.cloud.qdrant.io:6333",
    api_key=qdrant_api_key,
)

COLLECTION = "recipes_nutrition"
VECTOR_DIM = 384
BATCH_SIZE = 512

# ── Create collection (idempotent) ─────────────────────────────────────────────
if not qdrant_client.collection_exists(COLLECTION):
    qdrant_client.create_collection(
        collection_name=COLLECTION,
        vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
    )

# ── Index payload fields for fast filtering ────────────────────────────────────
INDEXED_FIELDS = {
    "meal_type":                      PayloadSchemaType.KEYWORD,
    "cuisine":                        PayloadSchemaType.KEYWORD,
    "main_protein":                   PayloadSchemaType.KEYWORD,
    "cooking_method":                 PayloadSchemaType.KEYWORD,
    "diet_flags":                     PayloadSchemaType.KEYWORD,
    "ingredient_count":               PayloadSchemaType.INTEGER,
    "estimated_cook_time_min":        PayloadSchemaType.INTEGER,
    "has_picture":                    PayloadSchemaType.BOOL,
    "ingredients_list":               PayloadSchemaType.KEYWORD,
    # nutrition filters
    "nutrition_total.calories":       PayloadSchemaType.FLOAT,
    "nutrition_total.protein":        PayloadSchemaType.FLOAT,
    "nutrition_total.fat":            PayloadSchemaType.FLOAT,
    "nutrition_total.carbs":          PayloadSchemaType.FLOAT,
    "nutrition_total.fiber":          PayloadSchemaType.FLOAT,
    "nutrition_total.sugar":          PayloadSchemaType.FLOAT,
    "nutrition_total.sodium_mg":      PayloadSchemaType.FLOAT,
    "nutrition_coverage":             PayloadSchemaType.FLOAT,
}
for field, schema in INDEXED_FIELDS.items():
    qdrant_client.create_payload_index(
        collection_name=COLLECTION,
        field_name=field,
        field_schema=schema,
    )


# ── Stream JSONL and upload in batches ─────────────────────────────────────────
def index_jsonl(jsonl_path: str):
    batch_texts, batch_payloads = [], []

    def flush():
        if not batch_texts:
            return
        embeddings = model.encode(batch_texts, show_progress_bar=False).tolist()
        points = [
            PointStruct(id=str(uuid.uuid4()), vector=emb, payload={
                "text": txt,
                **{k: v for k, v in meta.items() if k != "parsed_ingredients"},
                # flatten parsed_ingredients list into parallel indexed arrays
                "ingredients_list": [p["name"]         for p in meta.get("parsed_ingredients", [])],
                "quantities_list":  [p["quantity"]     for p in meta.get("parsed_ingredients", [])],
                "units_list":       [p["unit"]         for p in meta.get("parsed_ingredients", [])],
                "qty_per_100g_list":[p["qty_per_100g"] for p in meta.get("parsed_ingredients", [])],
                # flatten nutrition_total so indexed fields resolve correctly
                "nutrition_total.calories":  meta.get("nutrition_total", {}).get("calories"),
                "nutrition_total.protein":   meta.get("nutrition_total", {}).get("protein"),
                "nutrition_total.fat":       meta.get("nutrition_total", {}).get("fat"),
                "nutrition_total.carbs":     meta.get("nutrition_total", {}).get("carbs"),
                "nutrition_total.fiber":     meta.get("nutrition_total", {}).get("fiber"),
                "nutrition_total.sugar":     meta.get("nutrition_total", {}).get("sugar"),
                "nutrition_total.sodium_mg": meta.get("nutrition_total", {}).get("sodium_mg"),
            })
            for emb, txt, meta in zip(embeddings, batch_texts, batch_payloads)
        ]
        qdrant_client.upsert(collection_name=COLLECTION, points=points)
        batch_texts.clear()
        batch_payloads.clear()

    with open(jsonl_path) as f:
        for i, line in enumerate(f):
            chunk = json.loads(line)
            batch_texts.append(chunk["text"])
            batch_payloads.append(chunk["metadata"])
            if len(batch_texts) >= BATCH_SIZE:
                flush()
                print(f"Uploaded {i+1} records...", end="\r")

    flush()
    print(f"\nDone. Total uploaded: {i+1}")
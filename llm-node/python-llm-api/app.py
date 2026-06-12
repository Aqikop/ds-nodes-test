from pathlib import Path
import importlib.util
import json
import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


DEFAULT_LLM_PATH = Path(__file__).resolve().parent / "llm.py"
LLM_PATH = Path(os.getenv("LLM_PATH", DEFAULT_LLM_PATH)).resolve()


def load_llm_module():
    spec = importlib.util.spec_from_file_location("llm", LLM_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module from {LLM_PATH}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


llm = load_llm_module()
app = FastAPI(title="Food LLM API")


class DecomposeRequest(BaseModel):
    userQuery: str


class AnswerRequest(BaseModel):
    userQuery: str
    results: dict
    userIngredients: list[str] | None = None


@app.post("/decompose")
def decompose(request: DecomposeRequest):
    try:
        json_text = llm.decompose_routing(request.userQuery)
        return json.loads(json_text)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/answer")
def answer(request: AnswerRequest):
    try:
        final_answer = llm.generate_answer(
            user_query=request.userQuery,
            results=request.results,
            user_ingredients=request.userIngredients,
        )
        return {"answer": final_answer}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
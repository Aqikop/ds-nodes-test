# Python LLM API

This API wraps the local `llm.py` file in this folder so the Java `llm-node`
can call Stage 1 and Stage 3 over HTTP.

```text
Coordinator -> Java llm-node:8081 -> Python LLM API:5000 -> llm.py
```

## Setup

Run in `cmd`:

```cmd
cd /d C:\Users\Admin\eclipse-workspace\ds-nodes-test\python-llm-api
py -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install fastapi uvicorn python-dotenv langchain-google-genai langchain-core qdrant-client
```

Set required keys in the same `cmd` window:

```cmd
set GOOGLE_API_KEY=your_google_key_here
set QDRANT_API_KEY=your_qdrant_key_here
set LANGCHAIN_API_KEY=your_langchain_key_here
```

Run:

```cmd
python -m uvicorn app:app --host 127.0.0.1 --port 5000
```

By default, `app.py` loads:

```text
python-llm-api/llm.py
```

To use a different file without editing code, set:

```cmd
set LLM_PATH=C:\path\to\llm.py
```

## Test Python Directly

```cmd
curl -X POST http://127.0.0.1:5000/decompose ^
  -H "Content-Type: application/json" ^
  -d "{\"userQuery\":\"high protein low carb chicken dinner under 30 minutes\"}"
```

## Test Through Java LLM Node

Start Java `llm-node` on port `8081`, then:

```cmd
curl -X POST http://localhost:8081/llm/decompose ^
  -H "Content-Type: application/json" ^
  -d "{\"userQuery\":\"high protein low carb chicken dinner under 30 minutes\"}"
```

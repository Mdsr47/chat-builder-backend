# RAG FastAPI

A FastAPI-based retrieval-augmented generation (RAG) app with:
- SQLite database backend via SQLAlchemy
- JWT authentication
- PDF and website ingest support
- Vector search using FAISS and SentenceTransformers
- Multiple LLM provider support via `groq`, `openai`, and `anthropic`
- Instagram Graph API integration hooks

## Requirements

The project dependencies are listed in `requirements.txt`.

## Setup

1. Create a Python virtual environment and activate it.

```powershell
python -m venv rag_env
.\rag_env\Scripts\Activate.ps1
```

2. Install dependencies.

```powershell
pip install -r requirements.txt
```

3. Copy `.env` from your local configuration and set values.

```powershell
copy .env.example .env
```

4. Initialize the database and run migrations/seeds.

```powershell
python init_db.py
```

## Run

```powershell
uvicorn main:app --reload
```

The API will be available at `http://127.0.0.1:8000`.

## Notes

- Do not commit `.env` or local files like `rag.db`.
- Vector indexes are stored under `vector_store/` and should be ignored by Git.
- If you use OpenAI or Anthropic providers, install the optional packages and set your API keys in `.env`.

## Useful files

- `main.py` — FastAPI application routes and business logic
- `models.py` — SQLAlchemy ORM models
- `database.py` — database engine/session setup
- `dependencies.py` — request dependencies and auth helpers
- `ingest.py` — PDF and URL content ingestion
- `retriever.py` — embedding and FAISS search layer
- `llm.py` — LLM response generation and provider adapters
- `jwt_handler.py` — JWT creation and verification

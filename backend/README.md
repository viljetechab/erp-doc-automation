# OrderFlow Pro Order Pipeline — Backend

## Quick Start

```bash
# 1. Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows

# 2. Install dependencies
pip install -e ".[dev]"

# 3. Set up environment
copy .env.example .env
# Edit .env and add your OPENAI_API_KEY

# 4. Run the server
uvicorn app.main:app --reload --port 8000
```

## API Docs

Once running, visit:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health: http://localhost:8000/api/v1/health

## Project Structure

```
app/
├── api/          # Route layer (no business logic)
├── core/         # Exceptions, error handlers, logging
├── db/           # Database engine and session
├── models/       # SQLAlchemy ORM models
├── prompts/      # OpenAI prompt templates
├── schemas/      # Pydantic request/response schemas
└── services/     # Business logic layer
```

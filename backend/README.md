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
# Edit .env: set DATABASE_URL, OPENAI_API_KEY, etc.

# 4. Apply database migrations
alembic upgrade head

# 5. Run the server
uvicorn app.main:app --reload --port 8000
```

## Database

The backend uses **PostgreSQL** with async SQLAlchemy (asyncpg driver).

### Connection

Set `DATABASE_URL` in `.env`:

```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/orderflow_pro
```

SQLite is only supported for local development (`APP_ENV=development`).
Production and staging environments **reject** SQLite URLs at startup.

### Migrations (Alembic)

Schema is managed via Alembic migrations, not application startup logic.

```bash
# Apply all migrations to the current database
alembic upgrade head

# Create a new migration after changing ORM models
alembic revision --autogenerate -m "describe the change"

# Show current migration status
alembic current

# Downgrade one step (use with caution)
alembic downgrade -1
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
alembic/
├── env.py        # Alembic environment (wired to app.config)
└── versions/     # Migration scripts
```

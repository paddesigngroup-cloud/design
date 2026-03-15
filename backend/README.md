# Backend Database Foundation

This directory contains the production-oriented PostgreSQL foundation for future cabinet and closet data.

## Stack

- PostgreSQL
- SQLAlchemy 2.x
- Alembic
- FastAPI-compatible Python package layout

## Quick Start on Windows Server

1. Create or activate a Python virtual environment.
2. Install dependencies:

```powershell
cd C:\DesignKP\backend
python -m pip install -e .[dev]
```

3. Ensure the root `.env` contains a PostgreSQL connection string.

Recommended:

```env
DATABASE_URL=postgresql+asyncpg://designkp:change-me@127.0.0.1:5432/designkp
```

The runtime is configured for `asyncpg`, which matches the current environment and FastAPI integration.

4. Run migrations:

```powershell
cd C:\DesignKP\backend
alembic upgrade head
```

5. Run a database health check:

```powershell
cd C:\DesignKP\backend
python -m designkp_backend.db.health
```

6. Run the API:

```powershell
cd C:\DesignKP\backend
uvicorn designkp_backend.main:app --host 127.0.0.1 --port 8000
```

## Notes

- This phase intentionally does not define cabinet business tables yet.
- All future schema changes should be added through Alembic revisions.
- Shared conventions are provided for UUID primary keys, timestamps, soft deletes, and optimistic version counters.

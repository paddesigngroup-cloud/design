from designkp_backend.config import normalize_postgres_url


def test_normalize_postgres_url_converts_asyncpg_to_psycopg() -> None:
    raw = "postgresql+asyncpg://user:pass@localhost:5432/designkp"
    assert normalize_postgres_url(raw) == "postgresql+psycopg://user:pass@localhost:5432/designkp"


def test_normalize_postgres_url_converts_bare_postgresql_to_psycopg() -> None:
    raw = "postgresql://user:pass@localhost:5432/designkp"
    assert normalize_postgres_url(raw) == "postgresql+psycopg://user:pass@localhost:5432/designkp"

from __future__ import annotations


def import_model_modules() -> None:
    """Import concrete model modules so Alembic can discover metadata.

    This package intentionally has no business tables in the foundation phase.
    The function exists so future model modules can be imported in one place.
    """

    from . import account  # noqa: F401
    from . import catalog  # noqa: F401

    return None

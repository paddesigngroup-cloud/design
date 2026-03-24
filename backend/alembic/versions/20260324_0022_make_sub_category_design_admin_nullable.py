"""make sub category design admin nullable

Revision ID: 20260324_0022
Revises: 20260324_0021
Create Date: 2026-03-24 23:40:00
"""

from __future__ import annotations

from alembic import op
from sqlalchemy.dialects import postgresql


revision = "20260324_0022"
down_revision = "20260324_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "sub_category_designs",
        "admin_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "sub_category_designs",
        "admin_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )

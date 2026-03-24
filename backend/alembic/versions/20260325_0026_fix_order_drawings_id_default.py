"""fix order drawings id default

Revision ID: 20260325_0026
Revises: 20260325_0025
Create Date: 2026-03-25 01:55:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260325_0026"
down_revision = "20260325_0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "order_drawings",
        "id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
        server_default=sa.text("gen_random_uuid()"),
    )


def downgrade() -> None:
    op.alter_column(
        "order_drawings",
        "id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
        server_default=None,
    )

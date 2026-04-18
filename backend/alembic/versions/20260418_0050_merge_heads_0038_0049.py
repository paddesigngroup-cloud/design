"""merge alembic heads 0038 and 0049

Revision ID: 20260418_0050
Revises: 20260330_0038, 20260418_0049
Create Date: 2026-04-18 01:00:00
"""

from __future__ import annotations


revision = "20260418_0050"
down_revision = ("20260330_0038", "20260418_0049")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
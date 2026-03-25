"""add interior value mode to params

Revision ID: 20260325_0030
Revises: 20260325_0029
Create Date: 2026-03-25 22:20:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260325_0030"
down_revision = "20260325_0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "params",
        sa.Column("interior_value_mode", sa.String(length=16), nullable=False, server_default="formula"),
    )
    op.execute(
        """
        UPDATE params
        SET interior_value_mode = 'auto'
        WHERE param_code IN ('f_s_cz', 'u_i_w', 'u_i_d', 'm_s_cz')
        """
    )
    op.alter_column("params", "interior_value_mode", server_default=None)


def downgrade() -> None:
    op.drop_column("params", "interior_value_mode")

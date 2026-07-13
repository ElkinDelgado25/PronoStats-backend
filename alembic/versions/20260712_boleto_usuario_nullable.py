"""Allow nullable usuario_id on boletos for guest slips.

Revision ID: 20260712_boleto_usuario_nullable
Revises: 20260712_add_boleto_pagado
Create Date: 2026-07-12
"""

from alembic import op


revision = "20260712_boleto_usuario_nullable"
down_revision = "20260712_add_boleto_pagado"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.alter_column("boletos", "usuario_id", nullable=True)


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("UPDATE boletos SET usuario_id = 1 WHERE usuario_id IS NULL")
        op.alter_column("boletos", "usuario_id", nullable=False)

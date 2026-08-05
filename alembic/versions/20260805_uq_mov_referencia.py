"""Add unique constraint on movimientos_cartera.referencia_externa.

Revision ID: 20260805_uq_mov_referencia
Revises: 20260712_boleto_usuario_nullable
Create Date: 2026-08-05
"""

from alembic import op


revision = "20260805_uq_mov_referencia"
down_revision = "20260712_boleto_usuario_nullable"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Postgres/SQLite: UNIQUE permite multiples NULL; evita doble credito Stripe.
    op.create_index(
        "ix_movimientos_cartera_boleto_uuid",
        "movimientos_cartera",
        ["boleto_uuid"],
        unique=False,
    )
    op.create_unique_constraint(
        "uq_movimientos_cartera_referencia_externa",
        "movimientos_cartera",
        ["referencia_externa"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_movimientos_cartera_referencia_externa",
        "movimientos_cartera",
        type_="unique",
    )
    op.drop_index("ix_movimientos_cartera_boleto_uuid", table_name="movimientos_cartera")

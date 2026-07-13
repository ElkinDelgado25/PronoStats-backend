"""Add transfer as a wallet payment method.

Revision ID: 20260711_add_transfer_payment_method
Revises:
Create Date: 2026-07-11
"""

from alembic import op


revision = "20260711_add_transfer_payment_method"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite stores this enum as text. PostgreSQL needs the new enum member on
    # databases created before MetodoPago.transfer existed.
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TYPE metodopago ADD VALUE IF NOT EXISTS 'transfer'")


def downgrade() -> None:
    # PostgreSQL cannot safely remove an enum value without rebuilding the
    # dependent type, so this migration intentionally has no downgrade action.
    pass

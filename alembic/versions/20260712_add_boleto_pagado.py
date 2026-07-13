"""Add pagado flag to boletos.

Revision ID: 20260712_add_boleto_pagado
Revises: 20260711_add_transfer_payment_method
Create Date: 2026-07-12
"""

import sqlalchemy as sa
from alembic import op


revision = "20260712_add_boleto_pagado"
down_revision = "20260711_add_transfer_payment_method"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "boletos",
        sa.Column("pagado", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_column("boletos", "pagado")

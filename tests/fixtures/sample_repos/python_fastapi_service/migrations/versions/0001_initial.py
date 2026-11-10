"""Initial payment schema migration."""

import sqlalchemy as sa
from alembic import op


def upgrade():
    op.create_table(
        "ledger_transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.String(length=64), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
    )


def downgrade():
    op.drop_table("ledger_transactions")

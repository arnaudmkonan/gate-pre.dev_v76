"""Email verification on portal users + Stripe IDs on clients.

Revision ID: k7l8m9n0p1q2
Revises: j6k7l8m9n0p1
Create Date: 2026-10-10

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "k7l8m9n0p1q2"
down_revision: Union[str, None] = "j6k7l8m9n0p1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "client_users",
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "client_users",
        sa.Column("email_verify_token", sa.String(length=100), nullable=True),
    )
    op.create_index(
        "ix_client_users_email_verify_token",
        "client_users",
        ["email_verify_token"],
        unique=False,
    )
    op.execute(
        sa.text(
            "UPDATE client_users SET email_verified_at = NOW() "
            "WHERE email_verified_at IS NULL AND status = 'active'"
        )
    )

    op.add_column("clients", sa.Column("stripe_customer_id", sa.String(length=100), nullable=True))
    op.add_column("clients", sa.Column("stripe_subscription_id", sa.String(length=100), nullable=True))
    op.create_index("ix_clients_stripe_customer_id", "clients", ["stripe_customer_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_clients_stripe_customer_id", table_name="clients")
    op.drop_column("clients", "stripe_subscription_id")
    op.drop_column("clients", "stripe_customer_id")
    op.drop_index("ix_client_users_email_verify_token", table_name="client_users")
    op.drop_column("client_users", "email_verify_token")
    op.drop_column("client_users", "email_verified_at")

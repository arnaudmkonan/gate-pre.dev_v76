"""Add client_usage_events for pilot metering.

Revision ID: j6k7l8m9n0p1
Revises: i5j6k7l8m9n0
Create Date: 2026-03-27

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "j6k7l8m9n0p1"
down_revision: Union[str, None] = "i5j6k7l8m9n0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "client_usage_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("client_id", sa.UUID(), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("resource_id", sa.String(length=255), nullable=True),
        sa.Column("event_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_client_usage_events_client_id", "client_usage_events", ["client_id"], unique=False)
    op.create_index("ix_client_usage_events_event_type", "client_usage_events", ["event_type"], unique=False)
    op.create_index("ix_usage_client_created", "client_usage_events", ["client_id", "created_at"], unique=False)
    op.create_index("ix_usage_type_created", "client_usage_events", ["event_type", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_usage_type_created", table_name="client_usage_events")
    op.drop_index("ix_usage_client_created", table_name="client_usage_events")
    op.drop_index("ix_client_usage_events_event_type", table_name="client_usage_events")
    op.drop_index("ix_client_usage_events_client_id", table_name="client_usage_events")
    op.drop_table("client_usage_events")

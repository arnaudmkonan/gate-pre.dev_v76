"""Add leads and landing_page_events if missing (549 upgrade incorrectly dropped them).

Revision ID: i5j6k7l8m9n0
Revises: h4i5j6k7l8m9
Create Date: 2026-03-27

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "i5j6k7l8m9n0"
down_revision: Union[str, None] = "h4i5j6k7l8m9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    tables = set(insp.get_table_names())

    if "leads" not in tables:
        op.create_table(
            "leads",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("first_name", sa.String(length=100), nullable=False),
            sa.Column("last_name", sa.String(length=100), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("company", sa.String(length=255), nullable=False),
            sa.Column("phone", sa.String(length=50), nullable=True),
            sa.Column("company_size", sa.String(length=50), nullable=True),
            sa.Column("role", sa.String(length=100), nullable=True),
            sa.Column("source", sa.String(length=100), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=50), nullable=True),
            sa.Column("registered_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("email", name="leads_email_key"),
        )
        op.create_index("idx_leads_email", "leads", ["email"], unique=False)

    if "landing_page_events" not in tables:
        op.create_table(
            "landing_page_events",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("session_id", sa.String(length=100), nullable=False),
            sa.Column("event_type", sa.String(length=50), nullable=False),
            sa.Column("page_path", sa.String(length=255), nullable=True),
            sa.Column("element_id", sa.String(length=100), nullable=True),
            sa.Column("referrer", sa.String(length=500), nullable=True),
            sa.Column("user_agent", sa.Text(), nullable=True),
            sa.Column("ip_address", sa.String(length=50), nullable=True),
            sa.Column("utm_source", sa.String(length=100), nullable=True),
            sa.Column("utm_medium", sa.String(length=100), nullable=True),
            sa.Column("utm_campaign", sa.String(length=100), nullable=True),
            sa.Column("event_data", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("idx_lpe_type", "landing_page_events", ["event_type"], unique=False)
        op.create_index("idx_lpe_session", "landing_page_events", ["session_id"], unique=False)
        op.create_index("idx_lpe_created", "landing_page_events", ["created_at"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    tables = set(insp.get_table_names())

    if "landing_page_events" in tables:
        op.drop_index("idx_lpe_created", table_name="landing_page_events")
        op.drop_index("idx_lpe_session", table_name="landing_page_events")
        op.drop_index("idx_lpe_type", table_name="landing_page_events")
        op.drop_table("landing_page_events")

    if "leads" in tables:
        op.drop_index("idx_leads_email", table_name="leads")
        op.drop_table("leads")

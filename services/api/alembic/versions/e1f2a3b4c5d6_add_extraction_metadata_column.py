"""Add extraction_metadata column to extraction_results

Revision ID: e1f2a3b4c5d6
Revises: d9e8f7c6b5a4
Create Date: 2026-02-17 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = 'e1f2a3b4c5d6'
down_revision = 'd9e8f7c6b5a4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    from sqlalchemy import inspect

    bind = op.get_bind()
    cols = {c["name"] for c in inspect(bind).get_columns("extraction_results")}
    if "extraction_metadata" in cols:
        return
    op.add_column(
        "extraction_results",
        sa.Column("extraction_metadata", postgresql.JSON(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('extraction_results', 'extraction_metadata')

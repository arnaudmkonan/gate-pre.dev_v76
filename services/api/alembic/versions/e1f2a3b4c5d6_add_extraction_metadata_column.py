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
    # Add extraction_metadata column for storing extractor-specific metadata
    # (party details, cargo item metadata, etc.) from trade document extraction
    op.add_column(
        'extraction_results',
        sa.Column('extraction_metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('extraction_results', 'extraction_metadata')

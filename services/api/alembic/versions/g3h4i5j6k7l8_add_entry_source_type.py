"""Add source_type and source_reference to entries table

Revision ID: g3h4i5j6k7l8
Revises: f2g3h4i5j6k7
Create Date: 2026-01-28 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'g3h4i5j6k7l8'
down_revision = 'f2g3h4i5j6k7'
branch_labels = None
depends_on = None


def upgrade():
    # Add source_type column to entries table
    op.add_column(
        'entries',
        sa.Column('source_type', sa.String(30), nullable=False, server_default='manual')
    )

    # Add source_reference column to entries table
    op.add_column(
        'entries',
        sa.Column('source_reference', sa.String(200), nullable=True)
    )

    # Create index on source_type for filtering
    op.create_index('ix_entries_source_type', 'entries', ['source_type'])


def downgrade():
    op.drop_index('ix_entries_source_type', table_name='entries')
    op.drop_column('entries', 'source_reference')
    op.drop_column('entries', 'source_type')

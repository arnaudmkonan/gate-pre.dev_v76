"""Add ACE entries table

Revision ID: d9e8f7c6b5a4
Revises: c8f7a9b2d1e4
Create Date: 2026-01-23

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'd9e8f7c6b5a4'
down_revision = 'c8f7a9b2d1e4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create ACE entries table
    op.create_table(
        'ace_entries',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('entry_number', sa.String(50), nullable=False, index=True),
        sa.Column('entry_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('entry_type', sa.String(10), nullable=True),
        
        # Importer info
        sa.Column('importer_name', sa.String(500), nullable=True, index=True),
        sa.Column('importer_number', sa.String(50), nullable=True),
        
        # Port info
        sa.Column('port_code', sa.String(10), nullable=True),
        sa.Column('port_name', sa.String(200), nullable=True),
        
        # Line item details
        sa.Column('hts_code', sa.String(20), nullable=True, index=True),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('country_of_origin', sa.String(100), nullable=True, index=True),
        sa.Column('quantity', sa.Numeric(15, 4), nullable=True),
        sa.Column('unit', sa.String(20), nullable=True),
        
        # Values and duties
        sa.Column('entered_value', sa.Numeric(15, 2), nullable=True),
        sa.Column('duty_rate', sa.Numeric(10, 4), nullable=True),
        sa.Column('duty_amount', sa.Numeric(15, 2), nullable=True),
        sa.Column('mpf_amount', sa.Numeric(15, 2), nullable=True),
        sa.Column('hmf_amount', sa.Numeric(15, 2), nullable=True),
        
        # Liquidation tracking
        sa.Column('liquidation_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('liquidation_status', sa.String(50), nullable=True),
        
        # Additional data
        sa.Column('raw_data', postgresql.JSONB, nullable=True),
        sa.Column('batch_id', sa.String(50), nullable=True, index=True),
        
        # Timestamps from BaseModel
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    
    # Create composite index for entry_number + hts_code
    op.create_index('ix_ace_entries_entry_number_hts', 'ace_entries', ['entry_number', 'hts_code'])
    
    # Create index for entry_date
    op.create_index('ix_ace_entries_entry_date', 'ace_entries', ['entry_date'])


def downgrade() -> None:
    op.drop_index('ix_ace_entries_entry_date')
    op.drop_index('ix_ace_entries_entry_number_hts')
    op.drop_table('ace_entries')

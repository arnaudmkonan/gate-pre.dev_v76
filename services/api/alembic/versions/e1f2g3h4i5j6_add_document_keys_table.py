"""Add document_keys table for extracted linking identifiers

Revision ID: e1f2g3h4i5j6
Revises: d9e8f7c6b5a4
Create Date: 2026-01-24

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'e1f2g3h4i5j6'
down_revision = 'd9e8f7c6b5a4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create document_keys table for extracted linking identifiers
    op.create_table(
        'document_keys',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        
        # Link to source document
        sa.Column('document_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('raw_files.id', ondelete='CASCADE'), nullable=False),
        
        # Key identification
        sa.Column('key_type', sa.String(50), nullable=False),  # ENTRY_NUM, BOL_NUM, etc.
        sa.Column('key_value', sa.String(500), nullable=False),  # Original extracted value
        sa.Column('key_value_normalized', sa.String(500), nullable=True),  # Normalized for matching
        
        # Extraction metadata
        sa.Column('confidence', sa.Float, default=1.0, nullable=False),  # 0.0-1.0
        sa.Column('extraction_method', sa.String(20), default='regex', nullable=False),  # regex, llm, manual, ocr
        sa.Column('source_text', sa.Text, nullable=True),  # Context snippet
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    
    # Primary lookup indexes
    op.create_index('ix_document_keys_document_id', 'document_keys', ['document_id'])
    op.create_index('ix_document_keys_key_type', 'document_keys', ['key_type'])
    op.create_index('ix_document_keys_key_value', 'document_keys', ['key_value'])
    op.create_index('ix_document_keys_normalized', 'document_keys', ['key_value_normalized'])
    
    # Compound indexes for linking queries
    op.create_index('ix_document_keys_type_value', 'document_keys', ['key_type', 'key_value'])
    op.create_index('ix_document_keys_type_normalized', 'document_keys', ['key_type', 'key_value_normalized'])


def downgrade() -> None:
    op.drop_index('ix_document_keys_type_normalized')
    op.drop_index('ix_document_keys_type_value')
    op.drop_index('ix_document_keys_normalized')
    op.drop_index('ix_document_keys_key_value')
    op.drop_index('ix_document_keys_key_type')
    op.drop_index('ix_document_keys_document_id')
    op.drop_table('document_keys')

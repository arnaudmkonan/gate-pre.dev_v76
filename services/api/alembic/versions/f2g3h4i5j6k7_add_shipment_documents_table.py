"""Add shipment enhancements and shipment_documents junction table

Revision ID: f2g3h4i5j6k7
Revises: e1f2g3h4i5j6
Create Date: 2026-01-24

Adds Lakehouse-style document linking infrastructure:
- New columns to shipments table for linking and search
- shipment_documents junction table for document-shipment relationships
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'f2g3h4i5j6k7'
down_revision = 'e1f2g3h4i5j6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns to shipments table for Lakehouse architecture
    # Using batch_alter_table for safety
    with op.batch_alter_table('shipments', schema=None) as batch_op:
        # Human-readable name
        batch_op.add_column(sa.Column('name', sa.String(500), nullable=True))
        
        # Primary linking key
        batch_op.add_column(sa.Column('primary_key_type', sa.String(50), nullable=True))
        batch_op.add_column(sa.Column('primary_key_value', sa.String(500), nullable=True))
        
        # Document tracking
        batch_op.add_column(sa.Column('document_count', sa.Integer, default=0, nullable=True))
        batch_op.add_column(sa.Column('document_types', postgresql.ARRAY(sa.String), nullable=True))
        
        # Denormalized identifiers for search
        batch_op.add_column(sa.Column('entry_number', sa.String(50), nullable=True))
        batch_op.add_column(sa.Column('bol_number', sa.String(100), nullable=True))
        batch_op.add_column(sa.Column('awb_number', sa.String(50), nullable=True))
        batch_op.add_column(sa.Column('container_numbers', postgresql.ARRAY(sa.String), nullable=True))
        batch_op.add_column(sa.Column('po_numbers', postgresql.ARRAY(sa.String), nullable=True))
        
        # Party information (denormalized for search)
        batch_op.add_column(sa.Column('importer_name', sa.String(500), nullable=True))
        batch_op.add_column(sa.Column('exporter_name', sa.String(500), nullable=True))
        batch_op.add_column(sa.Column('manufacturer_name', sa.String(500), nullable=True))
        
        # Transport info
        batch_op.add_column(sa.Column('port_of_entry', sa.String(100), nullable=True))
        batch_op.add_column(sa.Column('arrival_date', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('entry_date', sa.DateTime(timezone=True), nullable=True))
        
        # Financial
        batch_op.add_column(sa.Column('total_declared_value', sa.Numeric(15, 2), nullable=True))
        batch_op.add_column(sa.Column('total_duty', sa.Numeric(15, 2), nullable=True))
        batch_op.add_column(sa.Column('currency', sa.String(3), default='USD', nullable=True))

    # Create indexes on shipments
    op.create_index('ix_shipments_primary_key', 'shipments', ['primary_key_type', 'primary_key_value'])
    op.create_index('ix_shipments_status', 'shipments', ['status'])
    op.create_index('ix_shipments_entry_number', 'shipments', ['entry_number'])
    op.create_index('ix_shipments_bol_number', 'shipments', ['bol_number'])
    op.create_index('ix_shipments_awb_number', 'shipments', ['awb_number'])
    op.create_index('ix_shipments_importer_name', 'shipments', ['importer_name'])
    
    # Create shipment_documents junction table
    op.create_table(
        'shipment_documents',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        
        # Foreign keys
        sa.Column('shipment_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('shipments.id', ondelete='CASCADE'), nullable=False),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('raw_files.id', ondelete='CASCADE'), nullable=False),
        
        # Link metadata
        sa.Column('linked_by_key_type', sa.String(50), nullable=True),
        sa.Column('linked_by_key_value', sa.String(500), nullable=True),
        sa.Column('link_confidence', sa.Float, default=1.0, nullable=False),
        sa.Column('link_method', sa.String(20), default='auto', nullable=False),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    
    # Create indexes on shipment_documents
    op.create_index('ix_shipment_documents_shipment_id', 'shipment_documents', ['shipment_id'])
    op.create_index('ix_shipment_documents_document_id', 'shipment_documents', ['document_id'])
    op.create_index('ix_shipment_documents_shipment_doc', 'shipment_documents', ['shipment_id', 'document_id'], unique=True)


def downgrade() -> None:
    # Drop shipment_documents table and indexes
    op.drop_index('ix_shipment_documents_shipment_doc')
    op.drop_index('ix_shipment_documents_document_id')
    op.drop_index('ix_shipment_documents_shipment_id')
    op.drop_table('shipment_documents')
    
    # Drop indexes from shipments
    op.drop_index('ix_shipments_importer_name')
    op.drop_index('ix_shipments_awb_number')
    op.drop_index('ix_shipments_bol_number')
    op.drop_index('ix_shipments_entry_number')
    op.drop_index('ix_shipments_status')
    op.drop_index('ix_shipments_primary_key')
    
    # Remove added columns from shipments
    with op.batch_alter_table('shipments', schema=None) as batch_op:
        batch_op.drop_column('currency')
        batch_op.drop_column('total_duty')
        batch_op.drop_column('total_declared_value')
        batch_op.drop_column('entry_date')
        batch_op.drop_column('arrival_date')
        batch_op.drop_column('port_of_entry')
        batch_op.drop_column('manufacturer_name')
        batch_op.drop_column('exporter_name')
        batch_op.drop_column('importer_name')
        batch_op.drop_column('po_numbers')
        batch_op.drop_column('container_numbers')
        batch_op.drop_column('awb_number')
        batch_op.drop_column('bol_number')
        batch_op.drop_column('entry_number')
        batch_op.drop_column('document_types')
        batch_op.drop_column('document_count')
        batch_op.drop_column('primary_key_value')
        batch_op.drop_column('primary_key_type')
        batch_op.drop_column('name')

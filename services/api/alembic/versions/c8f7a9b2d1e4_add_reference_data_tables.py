"""Add reference data tables for trade compliance

Revision ID: c8f7a9b2d1e4
Revises: b663ab8dfc32
Create Date: 2026-01-23 17:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB


# revision identifiers, used by Alembic.
revision = 'c8f7a9b2d1e4'
down_revision = 'b663ab8dfc32'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # OFAC SDN Table (Sanctions screening)
    op.create_table(
        'ofac_sdn',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('sdn_name', sa.String(500), nullable=False, index=True),
        sa.Column('sdn_type', sa.String(50), nullable=True),  # Individual, Entity, Vessel, etc.
        sa.Column('program', sa.String(200), nullable=True),  # CUBA, SDGT, etc.
        sa.Column('title', sa.String(200), nullable=True),
        sa.Column('call_sign', sa.String(50), nullable=True),  # For vessels
        sa.Column('vessel_type', sa.String(100), nullable=True),
        sa.Column('tonnage', sa.String(50), nullable=True),
        sa.Column('grt', sa.String(50), nullable=True),
        sa.Column('vessel_flag', sa.String(100), nullable=True),
        sa.Column('vessel_owner', sa.String(500), nullable=True),
        sa.Column('nationality', sa.String(100), nullable=True),
        sa.Column('aliases', ARRAY(sa.String), nullable=True, default=[]),
        sa.Column('addresses', JSONB, nullable=True, default=[]),
        sa.Column('id_numbers', JSONB, nullable=True, default=[]),  # Passport, Tax ID, etc.
        sa.Column('date_of_birth', sa.String(100), nullable=True),
        sa.Column('place_of_birth', sa.String(200), nullable=True),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )
    
    # HTS Codes Table (Tariff classification)
    op.create_table(
        'hts_codes',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('hts_code', sa.String(20), nullable=False, unique=True, index=True),
        sa.Column('description', sa.Text, nullable=False),
        sa.Column('chapter', sa.Integer, nullable=True),
        sa.Column('heading', sa.String(10), nullable=True),
        sa.Column('subheading', sa.String(20), nullable=True),
        sa.Column('duty_rate', sa.String(100), nullable=True),  # e.g. "6.5%", "Free", "2.5¢/kg"
        sa.Column('duty_rate_percent', sa.Numeric(10, 4), nullable=True),
        sa.Column('unit_of_quantity', sa.String(50), nullable=True),
        sa.Column('special_rates', JSONB, nullable=True, default={}),  # FTA rates
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )
    
    # NAICS Codes Table (Industry classification)
    op.create_table(
        'naics_codes',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('naics_code', sa.String(10), nullable=False, unique=True, index=True),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('sector', sa.String(100), nullable=True),
        sa.Column('level', sa.Integer, nullable=True),  # 2, 3, 4, 5, or 6 digit
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )
    
    # Compliance Screens Table (Results of screening)
    op.create_table(
        'compliance_screens',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('shipment_id', UUID(as_uuid=True), sa.ForeignKey('shipments.id', ondelete='CASCADE'), nullable=True),
        sa.Column('party_id', UUID(as_uuid=True), sa.ForeignKey('parties.id', ondelete='CASCADE'), nullable=True),
        sa.Column('product_id', UUID(as_uuid=True), sa.ForeignKey('products.id', ondelete='CASCADE'), nullable=True),
        sa.Column('screen_type', sa.String(50), nullable=False),  # 'ofac', 'adcvd', 'section_301', 'section_232'
        sa.Column('result', JSONB, nullable=True),  # Full screening result
        sa.Column('risk_level', sa.String(20), nullable=True),  # 'clear', 'possible_match', 'confirmed_match'
        sa.Column('matches', JSONB, nullable=True, default=[]),  # Matched entities/orders
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('resolved', sa.Boolean, default=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_by', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )
    
    # Drawback Ledger Table (For entry reconciliation and duty refunds)
    op.create_table(
        'drawback_ledger',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('import_entry_num', sa.String(50), nullable=True, index=True),
        sa.Column('import_entry_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('import_line_id', UUID(as_uuid=True), nullable=True),
        sa.Column('export_ref', sa.String(100), nullable=True, index=True),
        sa.Column('export_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('match_type', sa.String(50), nullable=True),  # 'direct', 'substitution', 'manufacturing'
        sa.Column('match_score', sa.Numeric(5, 4), nullable=True),
        sa.Column('hts_code', sa.String(20), nullable=True),
        sa.Column('quantity', sa.Numeric(15, 4), nullable=True),
        sa.Column('import_value', sa.Numeric(15, 2), nullable=True),
        sa.Column('duty_paid', sa.Numeric(15, 2), nullable=True),
        sa.Column('potential_refund', sa.Numeric(15, 2), nullable=True),
        sa.Column('status', sa.String(50), default='pending'),  # pending, claimed, approved, denied
        sa.Column('claim_filed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )
    
    # Create indexes
    op.create_index('ix_ofac_sdn_program', 'ofac_sdn', ['program'])
    op.create_index('ix_ofac_sdn_sdn_type', 'ofac_sdn', ['sdn_type'])
    op.create_index('ix_hts_codes_chapter', 'hts_codes', ['chapter'])
    op.create_index('ix_compliance_screens_type', 'compliance_screens', ['screen_type'])
    op.create_index('ix_compliance_screens_risk', 'compliance_screens', ['risk_level'])
    op.create_index('ix_drawback_ledger_status', 'drawback_ledger', ['status'])


def downgrade() -> None:
    op.drop_table('drawback_ledger')
    op.drop_table('compliance_screens')
    op.drop_table('naics_codes')
    op.drop_table('hts_codes')
    op.drop_table('ofac_sdn')

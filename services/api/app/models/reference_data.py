"""
Reference data models for trade compliance.
These models match the imported SQL data tables with integer IDs and embeddings.
Note: HTS, NAICS, and OFAC tables were imported from SQL files with specific schemas.
ComplianceScreen and DrawbackLedger use standard UUID BaseModel.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy import (
    Column, String, Text, Integer, Boolean, Numeric, DateTime,
    ForeignKey, Index
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB, ARRAY
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector

from app.models.base import BaseModel, Base


# ==================== Imported Reference Tables (Integer IDs) ====================
# These match the imported SQL file schemas

class OFACSdn(Base):
    """OFAC Specially Designated Nationals list entry (imported with embeddings)."""
    __tablename__ = "ofac_sdn"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sdn_name = Column(String(500), nullable=False, index=True)
    sdn_type = Column(String(50), nullable=True)  # Individual, Entity, Vessel
    program = Column(String(500), nullable=True)  # CUBA, SDGT, IRAN, etc.
    title = Column(String(200), nullable=True)
    aliases = Column(JSONB, default=[])
    addresses = Column(JSONB, default=[])
    nationality = Column(String(100), nullable=True)
    citizenship = Column(String(100), nullable=True)
    date_of_birth = Column(String(100), nullable=True)
    place_of_birth = Column(String(200), nullable=True)
    id_numbers = Column(JSONB, default=[])  # Passport, Tax ID, etc.
    remarks = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    embedding = Column(Vector(1536), nullable=True)
    created_at = Column(DateTime, default=func.now())


class HTSCode(Base):
    """Harmonized Tariff Schedule codes (imported with embeddings)."""
    __tablename__ = "hts_codes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hts_code = Column(String(20), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=False)
    chapter = Column(Integer, nullable=True)
    duty_rate = Column(String(100), nullable=True)  # e.g. "6.5%", "Free"
    duty_rate_percent = Column(Numeric(10, 4), nullable=True)
    embedding = Column(Vector(1536), nullable=True)
    created_at = Column(DateTime, default=func.now())


class NAICSCode(Base):
    """North American Industry Classification System codes (imported with embeddings)."""
    __tablename__ = "naics_codes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # Note: column is 'code' in the database, not 'naics_code'
    naics_code = Column('code', String(10), nullable=False, unique=True, index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    sector = Column(String(200), nullable=True)
    embedding = Column(Vector(1536), nullable=True)
    created_at = Column(DateTime, default=func.now())


# ==================== Application Tables (UUID IDs via BaseModel) ====================

class ComplianceScreen(BaseModel):
    """Results of compliance screening (OFAC, AD/CVD, etc.)."""
    __tablename__ = "compliance_screens"

    shipment_id = Column(PGUUID(as_uuid=True), ForeignKey('shipments.id', ondelete='CASCADE'), nullable=True)
    party_id = Column(PGUUID(as_uuid=True), ForeignKey('parties.id', ondelete='CASCADE'), nullable=True)
    product_id = Column(PGUUID(as_uuid=True), ForeignKey('products.id', ondelete='CASCADE'), nullable=True)
    screen_type = Column(String(50), nullable=False)  # 'ofac', 'adcvd', 'section_301', 'section_232'
    result = Column(JSONB, nullable=True)  # Full screening result
    risk_level = Column(String(20), nullable=True)  # 'clear', 'possible_match', 'confirmed_match'
    matches = Column(JSONB, default=[])  # Matched entities/orders
    notes = Column(Text, nullable=True)
    resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolved_by = Column(String(100), nullable=True)

    # Relationships
    shipment = relationship("Shipment", back_populates="compliance_screens")
    party = relationship("Party", back_populates="compliance_screens")
    product = relationship("Product", back_populates="compliance_screens")

    __table_args__ = (
        Index('ix_compliance_screens_type', 'screen_type'),
        Index('ix_compliance_screens_risk', 'risk_level'),
    )


class DrawbackLedger(BaseModel):
    """Drawback ledger for tracking duty refund eligibility."""
    __tablename__ = "drawback_ledger"

    import_entry_num = Column(String(50), nullable=True, index=True)
    import_entry_date = Column(DateTime(timezone=True), nullable=True)
    import_line_id = Column(PGUUID(as_uuid=True), nullable=True)
    export_ref = Column(String(100), nullable=True, index=True)
    export_date = Column(DateTime(timezone=True), nullable=True)
    match_type = Column(String(50), nullable=True)  # 'direct', 'substitution', 'manufacturing'
    match_score = Column(Numeric(5, 4), nullable=True)
    hts_code = Column(String(20), nullable=True)
    quantity = Column(Numeric(15, 4), nullable=True)
    import_value = Column(Numeric(15, 2), nullable=True)
    duty_paid = Column(Numeric(15, 2), nullable=True)
    potential_refund = Column(Numeric(15, 2), nullable=True)
    status = Column(String(50), default='pending')  # pending, claimed, approved, denied
    claim_filed_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)

    __table_args__ = (
        Index('ix_drawback_ledger_status', 'status'),
    )

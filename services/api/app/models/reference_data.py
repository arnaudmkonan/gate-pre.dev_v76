"""
Reference data models for trade compliance.
Includes OFAC SDN, HTS codes, NAICS codes, and compliance screening results.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Column, String, Text, Integer, Boolean, Numeric, DateTime,
    ForeignKey, Index
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID, ARRAY, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import BaseModel


class OFACSdn(BaseModel):
    """OFAC Specially Designated Nationals list entry."""
    __tablename__ = "ofac_sdn"

    sdn_name = Column(String(500), nullable=False, index=True)
    sdn_type = Column(String(50), nullable=True)  # Individual, Entity, Vessel
    program = Column(String(200), nullable=True)  # CUBA, SDGT, IRAN, etc.
    title = Column(String(200), nullable=True)
    call_sign = Column(String(50), nullable=True)  # For vessels
    vessel_type = Column(String(100), nullable=True)
    tonnage = Column(String(50), nullable=True)
    grt = Column(String(50), nullable=True)
    vessel_flag = Column(String(100), nullable=True)
    vessel_owner = Column(String(500), nullable=True)
    nationality = Column(String(100), nullable=True)
    aliases = Column(ARRAY(String), default=[])
    addresses = Column(JSONB, default=[])
    id_numbers = Column(JSONB, default=[])  # Passport, Tax ID, etc.
    date_of_birth = Column(String(100), nullable=True)
    place_of_birth = Column(String(200), nullable=True)
    is_active = Column(Boolean, default=True)

    __table_args__ = (
        Index('ix_ofac_sdn_program', 'program'),
        Index('ix_ofac_sdn_sdn_type', 'sdn_type'),
    )


class HTSCode(BaseModel):
    """Harmonized Tariff Schedule codes."""
    __tablename__ = "hts_codes"

    hts_code = Column(String(20), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=False)
    chapter = Column(Integer, nullable=True)
    heading = Column(String(10), nullable=True)
    subheading = Column(String(20), nullable=True)
    duty_rate = Column(String(100), nullable=True)  # e.g. "6.5%", "Free"
    duty_rate_percent = Column(Numeric(10, 4), nullable=True)
    unit_of_quantity = Column(String(50), nullable=True)
    special_rates = Column(JSONB, default={})  # FTA rates
    notes = Column(Text, nullable=True)

    __table_args__ = (
        Index('ix_hts_codes_chapter', 'chapter'),
    )


class NAICSCode(BaseModel):
    """North American Industry Classification System codes."""
    __tablename__ = "naics_codes"

    naics_code = Column(String(10), nullable=False, unique=True, index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    sector = Column(String(100), nullable=True)
    level = Column(Integer, nullable=True)  # 2, 3, 4, 5, or 6 digit


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

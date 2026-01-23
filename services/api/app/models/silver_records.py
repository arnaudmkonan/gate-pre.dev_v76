from typing import List, Optional

from sqlalchemy import Column, String, Float, ForeignKey, JSON, ARRAY, Enum as SAEnum
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel

class Party(BaseModel):
    """
    Silver Layer: Normalized party/entity (Company, Person, Organization).
    PRD 4.3: id, canonical_name, party_type, tax_id, aliases[], addresses[], contact_info, golden_record_id
    """
    __tablename__ = "parties"

    canonical_name = Column(String, nullable=False, index=True)
    party_type = Column(String, nullable=True)  # e.g., "vendor", "importer", "carrier"
    tax_id = Column(String, nullable=True, index=True)
    aliases = Column(ARRAY(String), nullable=True, default=[])
    contact_info = Column(JSON, nullable=True)
    
    # In Phase 2, this might point to a dedicated GoldenRecord table or be a self-ref
    # For now, we store the ID if resolved.
    golden_record_id = Column(UUID(as_uuid=True), nullable=True, index=True)

    # Relationships
    addresses = relationship("Address", back_populates="party", cascade="all, delete-orphan")
    compliance_screens = relationship("ComplianceScreen", back_populates="party", cascade="all, delete-orphan")


class Address(BaseModel):
    """
    Silver Layer: Normalized address linked to a Party.
    PRD 4.3: id, street, city, state, postal_code, country, normalized_address, geocode, party_id
    """
    __tablename__ = "addresses"

    party_id = Column(UUID(as_uuid=True), ForeignKey("parties.id"), nullable=True)
    
    street = Column(String, nullable=True)
    city = Column(String, nullable=True)
    state = Column(String, nullable=True)
    postal_code = Column(String, nullable=True)
    country = Column(String, nullable=True)
    
    normalized_address = Column(String, nullable=True)  # Full string representation
    geocode = Column(JSON, nullable=True)  # {lat: ..., lng: ...}

    party = relationship("Party", back_populates="addresses")


class Product(BaseModel):
    """
    Silver Layer: Normalized product information.
    PRD 4.3: id, description, hs_code, country_of_origin, unit_of_measure, aliases[], golden_record_id
    """
    __tablename__ = "products"

    description = Column(String, nullable=False)
    hs_code = Column(String, nullable=True, index=True)
    country_of_origin = Column(String, nullable=True)
    unit_of_measure = Column(String, nullable=True)
    aliases = Column(ARRAY(String), nullable=True, default=[])
    
    golden_record_id = Column(UUID(as_uuid=True), nullable=True, index=True)

    # Relationships
    compliance_screens = relationship("ComplianceScreen", back_populates="product", cascade="all, delete-orphan")


class EntityLink(BaseModel):
    """
    Silver Layer: Tracks relationships between identified entities.
    PRD 4.3: source_entity_id, target_entity_id, link_type, confidence, resolution_method
    """
    __tablename__ = "entity_links"

    source_entity_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    target_entity_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    link_type = Column(String, nullable=False)  # e.g., "same_as", "subsidiary_of", "vendor_for"
    confidence = Column(Float, nullable=False, default=1.0)
    resolution_method = Column(String, nullable=True)  # e.g., "exact_match", "embedding", "rule_based"

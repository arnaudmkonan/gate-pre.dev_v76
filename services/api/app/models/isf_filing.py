"""
ISF (Importer Security Filing) / 10+2 Model.

Implements the ISF/10+2 requirement for ocean shipments:
- 10 data elements from the importer
- 2 data elements from the carrier
- Must be filed 24 hours before vessel departure

Task 3.6 from ROADMAP_FULL_WORKFLOW.md
"""
from enum import Enum
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Text, Boolean, Index
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY

from app.models.base import BaseModel


class ISFStatus(str, Enum):
    """ISF filing status."""
    DRAFT = "draft"
    PENDING = "pending"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    MATCHED = "matched"  # Matched to entry
    AMENDED = "amended"


class ISFFiling(BaseModel):
    """
    ISF (Importer Security Filing) / 10+2 Filing.
    
    Required for ocean shipments 24 hours before vessel departure.
    
    10 Importer Elements:
    1. Seller (owner) name and address
    2. Buyer (owner) name and address
    3. Importer of record number
    4. Consignee number(s)
    5. Manufacturer (or supplier) name and address
    6. Ship to party name and address
    7. Country of origin
    8. Commodity HTS-6 (to 6 digits)
    9. Container stuffing location
    10. Consolidator (stuffer) name and address
    
    +2 Carrier Elements:
    1. Vessel stow plan
    2. Container status messages
    """
    __tablename__ = "isf_filings"
    
    # ISF Identification
    isf_number = Column(String(20), unique=True, nullable=True, index=True)
    transaction_number = Column(String(30), nullable=True)  # CBP transaction number
    
    # Status
    status = Column(String(20), default=ISFStatus.DRAFT.value, nullable=False, index=True)
    filed_at = Column(DateTime(timezone=True), nullable=True)
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    
    # Link to shipment and entry
    shipment_id = Column(UUID(as_uuid=True), ForeignKey("shipments.id"), nullable=True)
    entry_id = Column(UUID(as_uuid=True), ForeignKey("entries.id"), nullable=True)
    
    # ========== 10 Importer Data Elements ==========
    
    # 1. Seller (Owner) - Name and Address
    seller_name = Column(String(500), nullable=True)
    seller_address = Column(Text, nullable=True)
    seller_city = Column(String(100), nullable=True)
    seller_country = Column(String(2), nullable=True)  # ISO country code
    seller_id = Column(String(50), nullable=True)  # Optional ID
    
    # 2. Buyer (Owner) - Name and Address
    buyer_name = Column(String(500), nullable=True)
    buyer_address = Column(Text, nullable=True)
    buyer_city = Column(String(100), nullable=True)
    buyer_country = Column(String(2), nullable=True)
    buyer_id = Column(String(50), nullable=True)
    
    # 3. Importer of Record Number
    importer_of_record_number = Column(String(50), nullable=True, index=True)
    importer_of_record_name = Column(String(500), nullable=True)
    
    # 4. Consignee Number(s)
    consignee_number = Column(String(50), nullable=True)
    consignee_name = Column(String(500), nullable=True)
    consignee_address = Column(Text, nullable=True)
    
    # 5. Manufacturer (or Supplier) - Name and Address
    manufacturer_name = Column(String(500), nullable=True)
    manufacturer_address = Column(Text, nullable=True)
    manufacturer_city = Column(String(100), nullable=True)
    manufacturer_country = Column(String(2), nullable=True)
    manufacturer_id = Column(String(50), nullable=True)  # MID
    
    # 6. Ship To Party - Name and Address
    ship_to_name = Column(String(500), nullable=True)
    ship_to_address = Column(Text, nullable=True)
    ship_to_city = Column(String(100), nullable=True)
    ship_to_state = Column(String(50), nullable=True)
    ship_to_postal_code = Column(String(20), nullable=True)
    ship_to_country = Column(String(2), nullable=True)
    
    # 7. Country of Origin (can have multiple for mixed shipments)
    country_of_origin = Column(String(2), nullable=True)
    countries_of_origin = Column(ARRAY(String), nullable=True, default=[])
    
    # 8. Commodity HTS-6 (to 6 digits) - can have multiple
    hts_codes = Column(ARRAY(String), nullable=True, default=[])
    hts_primary = Column(String(10), nullable=True)  # Primary HTS code
    
    # 9. Container Stuffing Location
    stuffing_location_name = Column(String(500), nullable=True)
    stuffing_location_address = Column(Text, nullable=True)
    stuffing_location_city = Column(String(100), nullable=True)
    stuffing_location_country = Column(String(2), nullable=True)
    
    # 10. Consolidator (Stuffer) - Name and Address
    consolidator_name = Column(String(500), nullable=True)
    consolidator_address = Column(Text, nullable=True)
    consolidator_city = Column(String(100), nullable=True)
    consolidator_country = Column(String(2), nullable=True)
    consolidator_id = Column(String(50), nullable=True)
    
    # ========== Carrier Elements (+2) ==========
    # These are typically provided by the carrier, but tracked here for reference
    
    # Vessel/Transport Info
    vessel_name = Column(String(200), nullable=True)
    voyage_number = Column(String(50), nullable=True)
    carrier_code = Column(String(10), nullable=True)  # SCAC code
    
    # Container Info
    container_numbers = Column(ARRAY(String), nullable=True, default=[])
    
    # Bill of Lading
    master_bill_of_lading = Column(String(50), nullable=True)
    house_bill_of_lading = Column(String(50), nullable=True)
    
    # Port Info
    port_of_loading = Column(String(10), nullable=True)  # Foreign port
    port_of_discharge = Column(String(10), nullable=True)  # US port
    
    # Dates
    estimated_departure = Column(DateTime(timezone=True), nullable=True)
    estimated_arrival = Column(DateTime(timezone=True), nullable=True)
    actual_departure = Column(DateTime(timezone=True), nullable=True)
    
    # ========== Filing Info ==========
    
    # Filing metadata
    filer_code = Column(String(10), nullable=True)
    bond_type = Column(String(5), nullable=True)
    
    # Response from CBP
    cbp_response = Column(JSONB, nullable=True)
    
    # Amendment tracking
    amendment_count = Column(Integer, default=0)
    is_flexible = Column(Boolean, default=True)  # Flexible filing (not all data known yet)
    
    # Notes
    notes = Column(Text, nullable=True)
    
    # Validation
    validation_errors = Column(JSONB, nullable=True)
    is_valid = Column(Boolean, default=False)
    
    # Relationships
    shipment = relationship("Shipment", foreign_keys=[shipment_id])
    entry = relationship("Entry", foreign_keys=[entry_id])
    
    __table_args__ = (
        Index("ix_isf_filings_status", "status"),
        Index("ix_isf_filings_importer", "importer_of_record_number"),
        Index("ix_isf_filings_vessel", "vessel_name", "voyage_number"),
        Index("ix_isf_filings_shipment", "shipment_id"),
        Index("ix_isf_filings_entry", "entry_id"),
    )
    
    def get_missing_elements(self):
        """Return list of missing required ISF elements."""
        missing = []
        
        # Check each of the 10 required elements
        if not self.seller_name:
            missing.append("seller_name")
        if not self.buyer_name:
            missing.append("buyer_name")
        if not self.importer_of_record_number:
            missing.append("importer_of_record_number")
        if not self.consignee_number and not self.consignee_name:
            missing.append("consignee")
        if not self.manufacturer_name:
            missing.append("manufacturer_name")
        if not self.ship_to_name and not self.ship_to_address:
            missing.append("ship_to")
        if not self.country_of_origin and not self.countries_of_origin:
            missing.append("country_of_origin")
        if not self.hts_codes and not self.hts_primary:
            missing.append("hts_codes")
        if not self.stuffing_location_name:
            missing.append("stuffing_location")
        if not self.consolidator_name:
            missing.append("consolidator")
        
        return missing
    
    def get_completeness_percentage(self):
        """Return ISF completeness as percentage."""
        missing = self.get_missing_elements()
        return ((10 - len(missing)) / 10) * 100
    
    def to_dict(self):
        """Convert to dictionary for API response."""
        return {
            "id": str(self.id),
            "isf_number": self.isf_number,
            "transaction_number": self.transaction_number,
            "status": self.status,
            "filed_at": self.filed_at.isoformat() if self.filed_at else None,
            "accepted_at": self.accepted_at.isoformat() if self.accepted_at else None,
            "shipment_id": str(self.shipment_id) if self.shipment_id else None,
            "entry_id": str(self.entry_id) if self.entry_id else None,
            
            # 10 Elements summary
            "seller": {
                "name": self.seller_name,
                "address": self.seller_address,
                "country": self.seller_country,
            },
            "buyer": {
                "name": self.buyer_name,
                "address": self.buyer_address,
                "country": self.buyer_country,
            },
            "importer_of_record": {
                "number": self.importer_of_record_number,
                "name": self.importer_of_record_name,
            },
            "consignee": {
                "number": self.consignee_number,
                "name": self.consignee_name,
            },
            "manufacturer": {
                "name": self.manufacturer_name,
                "address": self.manufacturer_address,
                "country": self.manufacturer_country,
                "mid": self.manufacturer_id,
            },
            "ship_to": {
                "name": self.ship_to_name,
                "address": self.ship_to_address,
                "city": self.ship_to_city,
                "country": self.ship_to_country,
            },
            "country_of_origin": self.country_of_origin,
            "countries_of_origin": self.countries_of_origin or [],
            "hts_codes": self.hts_codes or [],
            "stuffing_location": {
                "name": self.stuffing_location_name,
                "address": self.stuffing_location_address,
                "country": self.stuffing_location_country,
            },
            "consolidator": {
                "name": self.consolidator_name,
                "address": self.consolidator_address,
                "country": self.consolidator_country,
            },
            
            # Transport
            "vessel": {
                "name": self.vessel_name,
                "voyage": self.voyage_number,
                "carrier_code": self.carrier_code,
            },
            "container_numbers": self.container_numbers or [],
            "bill_of_lading": {
                "master": self.master_bill_of_lading,
                "house": self.house_bill_of_lading,
            },
            "port_of_loading": self.port_of_loading,
            "port_of_discharge": self.port_of_discharge,
            "estimated_departure": self.estimated_departure.isoformat() if self.estimated_departure else None,
            "estimated_arrival": self.estimated_arrival.isoformat() if self.estimated_arrival else None,
            
            # Validation
            "is_valid": self.is_valid,
            "is_flexible": self.is_flexible,
            "completeness_percentage": self.get_completeness_percentage(),
            "missing_elements": self.get_missing_elements(),
            "amendment_count": self.amendment_count,
        }


class ISFAmendment(BaseModel):
    """
    Track amendments to ISF filings.
    
    ISF supports "flexible filing" where not all data is known initially.
    Amendments can be filed to add/correct data.
    """
    __tablename__ = "isf_amendments"
    
    isf_id = Column(UUID(as_uuid=True), ForeignKey("isf_filings.id", ondelete="CASCADE"), nullable=False)
    amendment_number = Column(Integer, nullable=False)
    
    # What changed
    changed_fields = Column(JSONB, nullable=True)  # {"field": {"old": x, "new": y}}
    reason = Column(Text, nullable=True)
    
    # Filing info
    filed_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(20), default="pending")
    cbp_response = Column(JSONB, nullable=True)
    
    # Who filed
    filed_by = Column(String(100), nullable=True)
    
    # Relationship
    isf = relationship("ISFFiling", foreign_keys=[isf_id])
    
    __table_args__ = (
        Index("ix_isf_amendments_isf_id", "isf_id"),
    )

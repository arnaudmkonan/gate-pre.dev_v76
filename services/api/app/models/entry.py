"""
Entry Models for Customs Brokerage Workflow.

Complete CBP 7501 Entry Summary data model supporting:
- Full entry header with all CBP required fields
- Line items with duty calculations
- Multi-party support (importer, consignee, seller, manufacturer, etc.)
- Document linking
- Status tracking and history
- ACE filing integration

Task 1.1 from ROADMAP_FULL_WORKFLOW.md
"""
from enum import Enum
from datetime import datetime, timezone
from typing import Optional, List
import uuid

from sqlalchemy import (
    Column, String, Text, Integer, Numeric, DateTime, Boolean, 
    ForeignKey, Index, Enum as SAEnum, CheckConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY

from app.models.base import BaseModel


# ==================== Enums ====================

class EntryStatus(str, Enum):
    """Entry workflow status."""
    DRAFT = "draft"  # Initial creation, incomplete
    PENDING_DOCUMENTS = "pending_documents"  # Waiting for required docs
    PENDING_REVIEW = "pending_review"  # Ready for broker review
    PENDING_CLIENT_APPROVAL = "pending_client_approval"  # Sent to client for approval
    READY_TO_FILE = "ready_to_file"  # Validated and ready
    FILING = "filing"  # Transmission in progress
    FILED = "filed"  # Submitted to CBP
    ACCEPTED = "accepted"  # CBP accepted
    REJECTED = "rejected"  # CBP rejected
    HOLD = "hold"  # CBP hold for exam
    RELEASED = "released"  # Cargo released
    LIQUIDATED = "liquidated"  # Final duty determination
    CANCELLED = "cancelled"  # Entry cancelled


class EntryType(str, Enum):
    """CBP Entry Types per 19 CFR."""
    CONSUMPTION = "01"  # Consumption Entry
    CONSUMPTION_FTZ = "02"  # Consumption with FTZ admission
    CONSUMPTION_ADDCVD = "03"  # Consumption with AD/CVD
    INFORMAL = "05"  # Informal Entry (under $2500)
    WAREHOUSE = "06"  # Warehouse Entry
    FTZ_ADMISSION = "07"  # FTZ Admission
    RECONCILIATION = "09"  # Reconciliation Entry
    DRAWBACK = "22"  # Drawback Entry
    TEMPORARY_IMPORT = "23"  # TIB - Temporary Import Bond
    IN_TRANSIT = "24"  # In Transit


class PartyRole(str, Enum):
    """Party roles in an entry."""
    IMPORTER_OF_RECORD = "importer_of_record"
    CONSIGNEE = "consignee"
    ULTIMATE_CONSIGNEE = "ultimate_consignee"
    SELLER = "seller"
    MANUFACTURER = "manufacturer"
    SHIPPER = "shipper"
    BUYER = "buyer"
    NOTIFY_PARTY = "notify_party"
    BROKER = "broker"
    FREIGHT_FORWARDER = "freight_forwarder"


# ==================== Entry Model ====================

class Entry(BaseModel):
    """
    Customs Entry - Full CBP 7501 Entry Summary.
    
    Represents a formal or informal customs entry with all required
    fields for ACE/ABI filing.
    """
    __tablename__ = "entries"

    # ===== Entry Identification =====
    entry_number = Column(String(15), nullable=True, unique=True, index=True)
    # Format: PPPCYYYYNNNNNNN (3 port + 1 check + 4 filer + 7 sequence)
    
    entry_type = Column(String(2), nullable=False, default=EntryType.CONSUMPTION.value)
    filer_code = Column(String(3), nullable=True)  # Broker's filer code
    
    # Entry dates
    entry_date = Column(DateTime(timezone=True), nullable=True)
    import_date = Column(DateTime(timezone=True), nullable=True)
    release_date = Column(DateTime(timezone=True), nullable=True)
    
    # ===== Port Information =====
    port_of_entry = Column(String(4), nullable=True, index=True)  # CBP port code
    port_of_unlading = Column(String(4), nullable=True)
    destination_port = Column(String(4), nullable=True)
    
    # ===== Transport Information =====
    mode_of_transport = Column(String(2), nullable=True)  # 10=Vessel, 20=Rail, 30=Truck, 40=Air
    carrier_code = Column(String(4), nullable=True)  # SCAC code
    vessel_name = Column(String(100), nullable=True)
    voyage_flight_number = Column(String(20), nullable=True)
    bill_of_lading = Column(String(50), nullable=True, index=True)
    master_bill = Column(String(50), nullable=True)
    house_bill = Column(String(50), nullable=True)
    
    # Container information
    container_numbers = Column(ARRAY(String), nullable=True, default=[])
    foreign_port_of_lading = Column(String(5), nullable=True)  # UN/LOCODE
    
    # ===== Importer Information =====
    importer_of_record_number = Column(String(15), nullable=True, index=True)  # EIN or CBP assigned
    importer_of_record_name = Column(String(500), nullable=True)
    ultimate_consignee_name = Column(String(500), nullable=True)
    
    # Reference to Party records (Silver layer)
    importer_party_id = Column(UUID(as_uuid=True), ForeignKey("parties.id"), nullable=True)
    consignee_party_id = Column(UUID(as_uuid=True), ForeignKey("parties.id"), nullable=True)
    
    # ===== Bond Information =====
    bond_type = Column(String(10), nullable=True)  # 8=Continuous, 9=Single Transaction
    bond_number = Column(String(20), nullable=True)
    surety_code = Column(String(3), nullable=True)
    
    # ===== Value & Duty Summary =====
    total_entered_value = Column(Numeric(15, 2), nullable=True, default=0)
    total_dutiable_value = Column(Numeric(15, 2), nullable=True, default=0)
    
    # Duty components
    total_duty = Column(Numeric(15, 2), nullable=True, default=0)
    total_tax = Column(Numeric(15, 2), nullable=True, default=0)
    total_fee = Column(Numeric(15, 2), nullable=True, default=0)  # MPF + HMF + other
    mpf_amount = Column(Numeric(15, 2), nullable=True, default=0)  # Merchandise Processing Fee
    hmf_amount = Column(Numeric(15, 2), nullable=True, default=0)  # Harbor Maintenance Fee
    
    # Additional duties
    section_301_amount = Column(Numeric(15, 2), nullable=True, default=0)
    section_232_amount = Column(Numeric(15, 2), nullable=True, default=0)
    add_amount = Column(Numeric(15, 2), nullable=True, default=0)  # Antidumping
    cvd_amount = Column(Numeric(15, 2), nullable=True, default=0)  # Countervailing
    
    # Grand total
    total_amount_due = Column(Numeric(15, 2), nullable=True, default=0)
    
    currency = Column(String(3), default="USD", nullable=False)
    exchange_rate = Column(Numeric(10, 6), nullable=True, default=1.0)
    
    # ===== Line Item Counts =====
    line_count = Column(Integer, default=0, nullable=False)
    
    # ===== Status & Workflow =====
    status = Column(String(30), default=EntryStatus.DRAFT.value, nullable=False, index=True)
    assigned_to = Column(String(100), nullable=True)  # Broker/user assigned
    
    # ===== ACE/ABI Integration =====
    ace_entry_id = Column(String(50), nullable=True)  # ACE assigned ID after filing
    ace_status = Column(String(30), nullable=True)  # Status from ACE
    ace_response = Column(JSONB, nullable=True)  # Last ACE response
    filed_at = Column(DateTime(timezone=True), nullable=True)
    
    # ===== Liquidation =====
    liquidation_date = Column(DateTime(timezone=True), nullable=True)
    liquidation_type = Column(String(20), nullable=True)  # final, extension
    liquidated_duty = Column(Numeric(15, 2), nullable=True)
    duty_difference = Column(Numeric(15, 2), nullable=True)  # Owed or refund
    
    # ===== Flags & Indicators =====
    is_ftz = Column(Boolean, default=False, nullable=False)  # Foreign Trade Zone
    is_reconciliation_flagged = Column(Boolean, default=False, nullable=False)
    is_prior_disclosure = Column(Boolean, default=False, nullable=False)
    has_add_cvd = Column(Boolean, default=False, nullable=False)
    requires_license = Column(Boolean, default=False, nullable=False)
    
    # ===== Additional Data =====
    notes = Column(Text, nullable=True)
    internal_reference = Column(String(100), nullable=True)  # Client's internal ref
    
    # ===== Client/Importer Link =====
    client_id = Column(UUID(as_uuid=True), nullable=True, index=True)  # Future: FK to clients table
    
    # ===== Source Tracking =====
    shipment_id = Column(UUID(as_uuid=True), ForeignKey("shipments.id"), nullable=True)
    
    # Relationships
    lines = relationship("EntryLine", back_populates="entry", cascade="all, delete-orphan", order_by="EntryLine.line_number")
    parties = relationship("EntryParty", back_populates="entry", cascade="all, delete-orphan")
    documents = relationship("EntryDocument", back_populates="entry", cascade="all, delete-orphan")
    status_history = relationship("EntryStatusHistory", back_populates="entry", cascade="all, delete-orphan", order_by="EntryStatusHistory.changed_at.desc()")
    
    importer_party = relationship("app.models.silver_records.Party", foreign_keys=[importer_party_id])
    consignee_party = relationship("app.models.silver_records.Party", foreign_keys=[consignee_party_id])
    shipment = relationship("Shipment", backref="entries")
    
    __table_args__ = (
        Index("ix_entries_status_date", "status", "entry_date"),
        Index("ix_entries_importer", "importer_of_record_number"),
        Index("ix_entries_bol", "bill_of_lading"),
        Index("ix_entries_client", "client_id"),
    )
    
    def calculate_totals(self):
        """Recalculate entry totals from line items."""
        self.total_entered_value = sum(line.entered_value or 0 for line in self.lines)
        self.total_dutiable_value = sum(line.dutiable_value or 0 for line in self.lines)
        self.total_duty = sum(line.duty_amount or 0 for line in self.lines)
        self.section_301_amount = sum(line.section_301_duty or 0 for line in self.lines)
        self.section_232_amount = sum(line.section_232_duty or 0 for line in self.lines)
        self.add_amount = sum(line.add_duty or 0 for line in self.lines)
        self.cvd_amount = sum(line.cvd_duty or 0 for line in self.lines)
        self.line_count = len(self.lines)
        
        # Total amount due
        self.total_amount_due = (
            self.total_duty + 
            self.mpf_amount + 
            self.hmf_amount +
            self.section_301_amount +
            self.section_232_amount +
            self.add_amount +
            self.cvd_amount
        )


# ==================== Entry Line Model ====================

class EntryLine(BaseModel):
    """
    Entry Line Item - Individual line on CBP 7501.
    
    Each line represents a product with specific HTS classification,
    value, quantity, and calculated duties.
    """
    __tablename__ = "entry_lines"

    entry_id = Column(UUID(as_uuid=True), ForeignKey("entries.id", ondelete="CASCADE"), nullable=False)
    
    # Line identification
    line_number = Column(Integer, nullable=False)
    
    # ===== Product Classification =====
    hts_code = Column(String(12), nullable=True, index=True)  # 10-digit HTS code
    hts_description = Column(Text, nullable=True)  # Official HTS description
    product_description = Column(Text, nullable=True)  # Commercial description
    
    # ===== Country of Origin =====
    country_of_origin = Column(String(2), nullable=True, index=True)  # ISO 2-letter code
    country_of_export = Column(String(2), nullable=True)
    
    # ===== Manufacturer =====
    manufacturer_id = Column(UUID(as_uuid=True), ForeignKey("parties.id"), nullable=True)
    manufacturer_name = Column(String(500), nullable=True)
    manufacturer_mid = Column(String(20), nullable=True)  # CBP Manufacturer ID
    
    # ===== Quantity =====
    quantity_1 = Column(Numeric(15, 4), nullable=True)  # Primary quantity
    uom_1 = Column(String(10), nullable=True)  # Unit of measure 1 (X, KG, M, etc.)
    quantity_2 = Column(Numeric(15, 4), nullable=True)  # Secondary quantity
    uom_2 = Column(String(10), nullable=True)
    gross_weight = Column(Numeric(15, 4), nullable=True)  # KG
    net_weight = Column(Numeric(15, 4), nullable=True)  # KG
    
    # ===== Value =====
    entered_value = Column(Numeric(15, 2), nullable=True)
    dutiable_value = Column(Numeric(15, 2), nullable=True)
    
    # Relationship value (for related parties)
    relationship_indicator = Column(Boolean, default=False, nullable=False)
    transaction_value_method = Column(String(2), nullable=True)  # Valuation method
    
    # ===== Duty Rates & Calculations =====
    duty_rate = Column(Numeric(8, 4), nullable=True)  # Ad valorem rate (%)
    duty_rate_specific = Column(Numeric(12, 6), nullable=True)  # Specific rate ($/unit)
    duty_type = Column(String(10), nullable=True)  # ad_valorem, specific, compound
    
    duty_amount = Column(Numeric(15, 2), nullable=True, default=0)
    
    # Additional duties
    section_301_rate = Column(Numeric(8, 4), nullable=True)
    section_301_duty = Column(Numeric(15, 2), nullable=True, default=0)
    
    section_232_rate = Column(Numeric(8, 4), nullable=True)
    section_232_duty = Column(Numeric(15, 2), nullable=True, default=0)
    
    add_rate = Column(Numeric(8, 4), nullable=True)  # Antidumping rate
    add_duty = Column(Numeric(15, 2), nullable=True, default=0)
    add_case_number = Column(String(20), nullable=True)
    
    cvd_rate = Column(Numeric(8, 4), nullable=True)  # Countervailing duty rate
    cvd_duty = Column(Numeric(15, 2), nullable=True, default=0)
    cvd_case_number = Column(String(20), nullable=True)
    
    # Total line duty
    total_line_duty = Column(Numeric(15, 2), nullable=True, default=0)
    
    # ===== FTA / Special Programs =====
    special_program_indicator = Column(String(2), nullable=True)  # SPI code
    fta_code = Column(String(10), nullable=True)  # USMCA, KORUS, etc.
    fta_eligible = Column(Boolean, default=False, nullable=False)
    applied_fta_rate = Column(Numeric(8, 4), nullable=True)
    
    # ===== Flags =====
    is_add_cvd_flagged = Column(Boolean, default=False, nullable=False)
    requires_license = Column(Boolean, default=False, nullable=False)
    quota_category = Column(String(20), nullable=True)
    
    # ===== Linking =====
    source_document_id = Column(UUID(as_uuid=True), nullable=True)  # Document that sourced this line
    invoice_line_id = Column(UUID(as_uuid=True), nullable=True)  # Link to InvoiceLine
    
    # ===== Additional Data =====
    raw_extraction_data = Column(JSONB, nullable=True)  # Original extracted data
    validation_errors = Column(JSONB, nullable=True, default=[])
    validation_warnings = Column(JSONB, nullable=True, default=[])
    
    # Relationships
    entry = relationship("Entry", back_populates="lines")
    manufacturer = relationship("app.models.silver_records.Party")
    
    __table_args__ = (
        Index("ix_entry_lines_entry", "entry_id"),
        Index("ix_entry_lines_hts", "hts_code"),
        Index("ix_entry_lines_origin", "country_of_origin"),
        CheckConstraint("line_number >= 1", name="ck_entry_lines_line_number_positive"),
    )
    
    def calculate_duties(self):
        """Calculate all duties for this line."""
        value = self.dutiable_value or self.entered_value or 0
        
        # Base duty
        if self.duty_rate:
            self.duty_amount = value * (self.duty_rate / 100)
        elif self.duty_rate_specific and self.quantity_1:
            self.duty_amount = self.duty_rate_specific * self.quantity_1
        else:
            self.duty_amount = 0
        
        # Section 301
        if self.section_301_rate:
            self.section_301_duty = value * (self.section_301_rate / 100)
        else:
            self.section_301_duty = 0
            
        # Section 232
        if self.section_232_rate:
            self.section_232_duty = value * (self.section_232_rate / 100)
        else:
            self.section_232_duty = 0
            
        # ADD
        if self.add_rate:
            self.add_duty = value * (self.add_rate / 100)
        else:
            self.add_duty = 0
            
        # CVD
        if self.cvd_rate:
            self.cvd_duty = value * (self.cvd_rate / 100)
        else:
            self.cvd_duty = 0
            
        # Total
        self.total_line_duty = (
            self.duty_amount +
            self.section_301_duty +
            self.section_232_duty +
            self.add_duty +
            self.cvd_duty
        )


# ==================== Entry Document Model ====================

class EntryDocument(BaseModel):
    """
    Junction table linking documents to entries.
    
    Tracks which documents were used to create/support an entry.
    """
    __tablename__ = "entry_documents"

    entry_id = Column(UUID(as_uuid=True), ForeignKey("entries.id", ondelete="CASCADE"), nullable=False)
    document_id = Column(UUID(as_uuid=True), ForeignKey("document_metadata.id", ondelete="CASCADE"), nullable=False)
    
    # Document role/type in the entry
    document_type = Column(String(50), nullable=True)  # commercial_invoice, bol, packing_list, etc.
    is_primary = Column(Boolean, default=False, nullable=False)  # Primary supporting document
    
    # Tracking
    added_by = Column(String(100), nullable=True)  # User who added
    notes = Column(Text, nullable=True)
    
    # Relationships
    entry = relationship("Entry", back_populates="documents")
    document = relationship("DocumentMetadata")
    
    __table_args__ = (
        Index("ix_entry_documents_entry", "entry_id"),
        Index("ix_entry_documents_document", "document_id"),
        Index("ix_entry_documents_unique", "entry_id", "document_id", unique=True),
    )


# ==================== Entry Party Model ====================

class EntryParty(BaseModel):
    """
    Parties associated with an entry.
    
    Supports multiple party roles beyond just importer/consignee.
    """
    __tablename__ = "entry_parties"

    entry_id = Column(UUID(as_uuid=True), ForeignKey("entries.id", ondelete="CASCADE"), nullable=False)
    
    # Party information
    role = Column(String(30), nullable=False)  # PartyRole enum value
    
    # Can link to normalized Party or store inline
    party_id = Column(UUID(as_uuid=True), ForeignKey("parties.id"), nullable=True)
    
    # Inline party data (when not linked to Silver layer)
    name = Column(String(500), nullable=False)
    address_line_1 = Column(String(200), nullable=True)
    address_line_2 = Column(String(200), nullable=True)
    city = Column(String(100), nullable=True)
    state_province = Column(String(50), nullable=True)
    postal_code = Column(String(20), nullable=True)
    country = Column(String(2), nullable=True)  # ISO 2-letter
    
    # Identifiers
    cbp_number = Column(String(20), nullable=True)  # EIN, CBP assigned, etc.
    mid = Column(String(20), nullable=True)  # Manufacturer ID
    duns = Column(String(15), nullable=True)
    
    # Relationships
    entry = relationship("Entry", back_populates="parties")
    party = relationship("app.models.silver_records.Party")
    
    __table_args__ = (
        Index("ix_entry_parties_entry", "entry_id"),
        Index("ix_entry_parties_role", "role"),
    )


# ==================== Entry Status History Model ====================

class EntryStatusHistory(BaseModel):
    """
    Audit trail of entry status changes.
    """
    __tablename__ = "entry_status_history"

    entry_id = Column(UUID(as_uuid=True), ForeignKey("entries.id", ondelete="CASCADE"), nullable=False)
    
    # Status change
    from_status = Column(String(30), nullable=True)
    to_status = Column(String(30), nullable=False)
    
    # Who/when/why
    changed_by = Column(String(100), nullable=True)  # User or system
    changed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    reason = Column(Text, nullable=True)
    
    # Additional context
    ace_message = Column(JSONB, nullable=True)  # CBP response if applicable
    
    # Relationships
    entry = relationship("Entry", back_populates="status_history")
    
    __table_args__ = (
        Index("ix_entry_status_history_entry", "entry_id"),
        Index("ix_entry_status_history_date", "changed_at"),
    )

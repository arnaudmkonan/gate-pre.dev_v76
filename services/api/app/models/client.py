"""
Client/Importer Data Models.

Database models for managing multiple importer clients in a multi-tenant
customs brokerage environment.

Task 4.1 from ROADMAP_FULL_WORKFLOW.md
"""
from enum import Enum
from datetime import datetime, timezone, date
from typing import Optional, List
import uuid

from sqlalchemy import (
    Column, String, Text, Integer, Numeric, DateTime, Boolean, Date,
    ForeignKey, Index, Enum as SAEnum, CheckConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY

from app.models.base import BaseModel


# ==================== Enums ====================

class ClientStatus(str, Enum):
    """Client account status."""
    ACTIVE = "active"  # Active client, can file entries
    INACTIVE = "inactive"  # Temporarily inactive
    ONBOARDING = "onboarding"  # New client setup in progress
    SUSPENDED = "suspended"  # Account suspended
    TERMINATED = "terminated"  # Relationship ended


class ClientType(str, Enum):
    """Type of client entity."""
    CORPORATION = "corporation"
    LLC = "llc"
    PARTNERSHIP = "partnership"
    SOLE_PROPRIETOR = "sole_proprietor"
    GOVERNMENT = "government"
    NON_PROFIT = "non_profit"
    OTHER = "other"


class BondType(str, Enum):
    """Type of customs bond."""
    CONTINUOUS = "continuous"  # Covers all entries in a year
    SINGLE_TRANSACTION = "single_transaction"  # Covers one entry
    ISF = "isf"  # ISF security bond


class ContactType(str, Enum):
    """Type of client contact."""
    PRIMARY = "primary"  # Main contact
    BILLING = "billing"  # For invoices
    OPERATIONS = "operations"  # Day-to-day import operations
    COMPLIANCE = "compliance"  # Regulatory/compliance contact
    EXECUTIVE = "executive"  # C-level/VP
    OTHER = "other"


# ==================== Client Model ====================

class Client(BaseModel):
    """
    Client/Importer company.
    
    Represents an importer of record for whom the broker files entries.
    """
    __tablename__ = "clients"

    # ===== Company Information =====
    name = Column(String(500), nullable=False, index=True)
    legal_name = Column(String(500), nullable=True)  # Full legal name if different
    dba_name = Column(String(500), nullable=True)  # Doing business as
    
    # Company type and status
    client_type = Column(String(30), default=ClientType.CORPORATION.value, nullable=False)
    status = Column(String(20), default=ClientStatus.ONBOARDING.value, nullable=False, index=True)
    
    # ===== Identifiers =====
    ior_number = Column(String(20), nullable=True, unique=True, index=True)  # Importer of Record Number
    # Format: XX-XXXXXXX (EIN) or XXXXXX-XXXXX (CBP assigned)
    
    ein = Column(String(15), nullable=True, unique=True, index=True)  # Employer ID Number
    duns = Column(String(15), nullable=True, index=True)  # D&B D-U-N-S Number
    cbp_assigned_number = Column(String(15), nullable=True)  # CBP Assigned Importer Number
    
    # ===== Primary Address =====
    address_line_1 = Column(String(200), nullable=True)
    address_line_2 = Column(String(200), nullable=True)
    city = Column(String(100), nullable=True)
    state_province = Column(String(50), nullable=True)
    postal_code = Column(String(20), nullable=True)
    country = Column(String(2), default="US", nullable=False)  # ISO 2-letter
    
    # ===== Contact Information =====
    phone = Column(String(30), nullable=True)
    fax = Column(String(30), nullable=True)
    email = Column(String(255), nullable=True)
    website = Column(String(255), nullable=True)
    
    # ===== Customs Information =====
    primary_port = Column(String(4), nullable=True)  # Most frequent entry port
    common_hts_chapters = Column(ARRAY(String), nullable=True, default=[])  # Common import categories
    common_origin_countries = Column(ARRAY(String), nullable=True, default=[])  # Common source countries
    
    # ===== Compliance & Risk =====
    c_tpat_member = Column(Boolean, default=False, nullable=False)  # C-TPAT certified
    c_tpat_svi_number = Column(String(20), nullable=True)  # C-TPAT SVI
    trusted_trader = Column(Boolean, default=False, nullable=False)
    known_importer = Column(Boolean, default=False, nullable=False)  # Known Importer Status
    
    ace_portal_account = Column(String(50), nullable=True)  # ACE portal account
    
    # ===== Financial =====
    credit_limit = Column(Numeric(15, 2), nullable=True)  # Credit limit for duty payments
    payment_terms = Column(String(50), nullable=True)  # e.g., "Net 30", "COD"
    billing_method = Column(String(30), nullable=True)  # monthly, per_entry, etc.
    
    # ===== Broker Relationship =====
    onboarding_date = Column(Date, nullable=True)
    first_entry_date = Column(Date, nullable=True)  # Date of first filed entry
    assigned_broker = Column(String(100), nullable=True)  # Assigned broker/account manager
    
    # ===== Preferences =====
    preferences = Column(JSONB, nullable=True, default={})
    # Examples:
    # - notification_email: true
    # - auto_file_when_ready: false
    # - require_approval: true
    
    # ===== Notes & Documentation =====
    notes = Column(Text, nullable=True)
    internal_code = Column(String(20), nullable=True, index=True)  # Internal reference code
    
    # ===== Relationships =====
    contacts = relationship("ClientContact", back_populates="client", cascade="all, delete-orphan")
    bonds = relationship("ClientBond", back_populates="client", cascade="all, delete-orphan")
    settings = relationship("ClientSettings", back_populates="client", uselist=False, cascade="all, delete-orphan")
    
    __table_args__ = (
        {"extend_existing": True},
    )
    
    @property
    def display_name(self) -> str:
        """Get display name for client."""
        return self.dba_name or self.name
    
    @property
    def full_address(self) -> str:
        """Get formatted full address."""
        parts = [
            self.address_line_1,
            self.address_line_2,
            f"{self.city}, {self.state_province} {self.postal_code}".strip(),
            self.country if self.country != "US" else None
        ]
        return "\n".join(p for p in parts if p)


# ==================== Client Contact Model ====================

class ClientContact(BaseModel):
    """
    Contact person at a client company.
    """
    __tablename__ = "client_contacts"

    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    
    # Contact info
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    title = Column(String(100), nullable=True)  # Job title
    
    contact_type = Column(String(30), default=ContactType.PRIMARY.value, nullable=False)
    is_primary = Column(Boolean, default=False, nullable=False)
    
    # Communication
    email = Column(String(255), nullable=True)
    phone = Column(String(30), nullable=True)
    mobile = Column(String(30), nullable=True)
    fax = Column(String(30), nullable=True)
    
    # Address (if different from company)
    address_line_1 = Column(String(200), nullable=True)
    city = Column(String(100), nullable=True)
    state_province = Column(String(50), nullable=True)
    postal_code = Column(String(20), nullable=True)
    country = Column(String(2), nullable=True)
    
    # Preferences
    receives_notifications = Column(Boolean, default=True, nullable=False)
    receives_invoices = Column(Boolean, default=False, nullable=False)
    receives_status_updates = Column(Boolean, default=True, nullable=False)
    
    notes = Column(Text, nullable=True)
    
    # Relationships
    client = relationship("Client", back_populates="contacts")
    
    __table_args__ = ({"extend_existing": True},)
    
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


# ==================== Client Bond Model ====================

class ClientBond(BaseModel):
    """
    Customs bond for a client.
    
    Tracks continuous and single transaction bonds.
    """
    __tablename__ = "client_bonds"

    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    
    # Bond details
    bond_type = Column(String(30), nullable=False)  # continuous, single_transaction, isf
    bond_number = Column(String(30), nullable=False, index=True)
    surety_code = Column(String(3), nullable=False)  # 3-digit surety code
    surety_name = Column(String(200), nullable=True)
    
    # Coverage
    bond_amount = Column(Numeric(15, 2), nullable=True)  # Bond amount
    coverage_start = Column(Date, nullable=True)
    coverage_end = Column(Date, nullable=True)  # For continuous bonds, annual renewal
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    is_sufficient = Column(Boolean, default=True, nullable=False)  # Sufficient for current activity
    
    # For single transaction bonds
    entry_id = Column(UUID(as_uuid=True), nullable=True)  # Link to specific entry if STB
    
    notes = Column(Text, nullable=True)
    
    # Relationships
    client = relationship("Client", back_populates="bonds")
    
    __table_args__ = ({"extend_existing": True},)
    
    @property
    def is_expired(self) -> bool:
        if not self.coverage_end:
            return False
        return date.today() > self.coverage_end
    
    @property
    def days_until_expiration(self) -> Optional[int]:
        if not self.coverage_end:
            return None
        return (self.coverage_end - date.today()).days


# ==================== Client Settings Model ====================

class ClientSettings(BaseModel):
    """
    Client-specific settings and preferences.
    
    One-to-one with Client for extended preferences.
    """
    __tablename__ = "client_settings"

    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, unique=True)
    
    # ===== Entry Preferences =====
    default_entry_type = Column(String(2), nullable=True, default="01")  # Consumption
    default_port = Column(String(4), nullable=True)
    require_approval_before_file = Column(Boolean, default=True, nullable=False)
    auto_calculate_duties = Column(Boolean, default=True, nullable=False)
    
    # ===== Notification Preferences =====
    notify_on_entry_file = Column(Boolean, default=True, nullable=False)
    notify_on_cbp_response = Column(Boolean, default=True, nullable=False)
    notify_on_document_ready = Column(Boolean, default=True, nullable=False)
    notify_on_duty_payment = Column(Boolean, default=True, nullable=False)
    notification_emails = Column(ARRAY(String), nullable=True, default=[])  # Additional emails
    
    # ===== Document Preferences =====
    store_document_copies = Column(Boolean, default=True, nullable=False)
    document_retention_days = Column(Integer, default=2555, nullable=False)  # 7 years default
    
    # ===== Classification Preferences =====
    preferred_fta = Column(String(20), nullable=True)  # Default FTA if applicable
    binding_ruling_numbers = Column(ARRAY(String), nullable=True, default=[])  # Known ruling numbers
    
    # ===== Billing Preferences =====
    invoice_delivery_method = Column(String(20), nullable=True, default="email")  # email, mail, portal
    consolidate_invoices = Column(Boolean, default=False, nullable=False)  # Consolidate vs per-entry
    
    # ===== Custom Fields (flexible storage) =====
    custom_fields = Column(JSONB, nullable=True, default={})
    
    # Relationships
    client = relationship("Client", back_populates="settings")
    
    __table_args__ = ({"extend_existing": True},)


# ==================== Helper function to add FK to Entry ====================

# Note: Entry.client_id already exists in entry.py
# This comment documents the relationship:
# Entry.client_id -> clients.id

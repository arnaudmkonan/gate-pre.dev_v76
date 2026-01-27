"""
ACE Settings Model.

Stores ACE Portal account configuration for customs filing.
Supports multiple filer codes per organization (brokers acting for multiple importers).

Task 3.3 from ROADMAP_FULL_WORKFLOW.md
"""
from sqlalchemy import Column, String, Text, Boolean, Index, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class ACESettings(BaseModel):
    """Organization-level ACE Portal settings."""
    
    __tablename__ = "ace_settings"
    
    # Link to organization
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Primary filer code (3-letter code assigned by CBP)
    primary_filer_code = Column(String(3), nullable=True)
    
    # Primary port code (4-digit)
    primary_port_code = Column(String(4), nullable=True)
    
    # Bond information
    default_bond_type = Column(String(20), nullable=True, default="continuous")
    default_bond_surety_code = Column(String(3), nullable=True)
    
    # ACE Portal API configuration (encrypted in production)
    ace_portal_username = Column(String(255), nullable=True)
    ace_portal_client_id = Column(String(255), nullable=True)  # For OAuth
    
    # Environment settings
    ace_environment = Column(String(20), nullable=False, default="test")  # test, production
    
    # Filing preferences
    auto_file_when_ready = Column(Boolean, default=False)
    require_dual_approval = Column(Boolean, default=True)
    
    # Notification preferences
    notify_on_filing = Column(Boolean, default=True)
    notify_on_acceptance = Column(Boolean, default=True)
    notify_on_rejection = Column(Boolean, default=True)
    notify_on_liquidation = Column(Boolean, default=True)
    notification_email = Column(String(255), nullable=True)
    
    # Additional configuration
    config = Column(JSONB, nullable=True, default=dict)
    
    # Relationships
    organization = relationship("Organization", backref="ace_settings")
    filer_codes = relationship("FilerCode", back_populates="ace_settings", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("idx_ace_settings_org", "organization_id"),
        UniqueConstraint("organization_id", name="uq_ace_settings_per_org"),
    )


class FilerCode(BaseModel):
    """
    Individual filer code configuration.
    
    Brokers may have multiple filer codes for different importers/consignees.
    Each filer code can have its own port and bond configuration.
    """
    
    __tablename__ = "filer_codes"
    
    # Link to ACE settings
    ace_settings_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ace_settings.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Filer code (3-letter code)
    filer_code = Column(String(3), nullable=False)
    
    # Display name for this filer code
    name = Column(String(255), nullable=True)
    
    # Associated importer/client (optional)
    client_id = Column(
        UUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    # Port of entry for this filer code
    port_code = Column(String(4), nullable=True)
    
    # Bond configuration for this filer
    bond_type = Column(String(20), nullable=True)  # continuous, single_transaction
    bond_number = Column(String(20), nullable=True)
    surety_code = Column(String(3), nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    is_primary = Column(Boolean, default=False)
    
    # Additional notes
    notes = Column(Text, nullable=True)
    
    # Relationships
    ace_settings = relationship("ACESettings", back_populates="filer_codes")
    client = relationship("Client", backref="filer_codes")
    
    __table_args__ = (
        Index("idx_filer_code_settings", "ace_settings_id"),
        Index("idx_filer_code_client", "client_id"),
        Index("idx_filer_code_code", "filer_code"),
        UniqueConstraint("ace_settings_id", "filer_code", name="uq_filer_code_per_settings"),
    )


# Validation helpers
def validate_filer_code(code: str) -> bool:
    """Validate filer code format (3 uppercase letters)."""
    if not code or len(code) != 3:
        return False
    return code.isalpha() and code.isupper()


def validate_port_code(code: str) -> bool:
    """Validate port code format (4 digits)."""
    if not code or len(code) != 4:
        return False
    return code.isdigit()


def validate_surety_code(code: str) -> bool:
    """Validate surety code format (3 digits)."""
    if not code or len(code) != 3:
        return False
    return code.isdigit()

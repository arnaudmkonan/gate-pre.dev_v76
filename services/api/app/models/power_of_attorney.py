"""
Power of Attorney Model  (Task B.2)

CBP requires a valid POA from the importer before any broker can file
on their behalf (19 USC § 1484; 19 CFR Part 141).

POA types:
  - general:  All entries for the life of the POA
  - limited:  Specific single shipment or entry
  - customs_only:  All CBP filings but not free-trade payments

Lifecycle:
  draft → pending_signature → active → [expired | revoked]

The model is intentionally lightweight — the actual PDF/e-signature
workflow sits on top (DocuSign / HelloSign integration in a future sprint).
"""
from datetime import date, datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import (
    Boolean, Column, Date, DateTime, ForeignKey,
    Index, String, Text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class POAStatus(str, Enum):
    DRAFT = "draft"
    PENDING_SIGNATURE = "pending_signature"
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"


class POAType(str, Enum):
    GENERAL = "general"           # All entries
    LIMITED = "limited"           # Single shipment
    CUSTOMS_ONLY = "customs_only" # CBP only, not manifest agent


class PowerOfAttorney(BaseModel):
    """
    CBP Power of Attorney record.

    Associates an importer (client) with a broker and tracks
    POA status, type, and validity window.
    """
    __tablename__ = "powers_of_attorney"

    # ---- Parties --------------------------------------------------------
    client_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    broker_license_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("broker_licenses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # ---- Grantor identity -----------------------------------------------
    grantor_name = Column(String(500), nullable=False)   # Importer legal name
    grantor_title = Column(String(200), nullable=True)   # e.g. "Vice President"
    grantor_ein = Column(String(20), nullable=True)      # Importer EIN

    # ---- POA details ----------------------------------------------------
    poa_type = Column(String(30), nullable=False, default=POAType.GENERAL.value)
    status = Column(String(30), nullable=False, default=POAStatus.DRAFT.value, index=True)

    # ---- Validity window ------------------------------------------------
    effective_date = Column(Date, nullable=True)
    expiry_date = Column(Date, nullable=True)   # None = no expiry (indefinite)

    # ---- E-signature metadata -------------------------------------------
    signature_provider = Column(String(50), nullable=True)  # "docusign", "hellosign"
    signature_request_id = Column(String(200), nullable=True)
    signed_at = Column(DateTime(timezone=True), nullable=True)
    signature_ip = Column(String(50), nullable=True)

    # ---- Document storage -----------------------------------------------
    document_url = Column(Text, nullable=True)   # S3/GCS URL to signed PDF

    # ---- Audit ----------------------------------------------------------
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revocation_reason = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    # ---- Relationships --------------------------------------------------
    client = relationship("Client", foreign_keys=[client_id])

    __table_args__ = (
        Index("ix_poa_client_status", "client_id", "status"),
        Index("ix_poa_status", "status"),
    )

    def is_active(self) -> bool:
        """Return True if this POA can currently be used to file."""
        if self.status != POAStatus.ACTIVE.value:
            return False
        today = date.today()
        if self.effective_date and today < self.effective_date:
            return False
        if self.expiry_date and today > self.expiry_date:
            return False
        return True

    def days_until_expiry(self) -> Optional[int]:
        if not self.expiry_date:
            return None
        return (self.expiry_date - date.today()).days

    def to_dict(self):
        return {
            "id": str(self.id),
            "client_id": str(self.client_id),
            "broker_license_id": str(self.broker_license_id) if self.broker_license_id else None,
            "grantor_name": self.grantor_name,
            "grantor_title": self.grantor_title,
            "grantor_ein": self.grantor_ein,
            "poa_type": self.poa_type,
            "status": self.status,
            "effective_date": self.effective_date.isoformat() if self.effective_date else None,
            "expiry_date": self.expiry_date.isoformat() if self.expiry_date else None,
            "is_active": self.is_active(),
            "days_until_expiry": self.days_until_expiry(),
            "signed_at": self.signed_at.isoformat() if self.signed_at else None,
            "document_url": self.document_url,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

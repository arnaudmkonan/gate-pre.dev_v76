"""
Shipment Suggestion Model

Stores pending shipment grouping suggestions for user review.
In manual mode, users review and accept/reject suggestions.
In auto mode, suggestions are auto-accepted and shipments created.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from sqlalchemy import (
    Column, String, DateTime, ForeignKey, Float, Boolean,
    Text, Enum as SQLEnum, JSON
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
import enum

from app.models.base import Base


class SuggestionStatus(enum.Enum):
    """Status of a shipment suggestion."""
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    MERGED = "merged"  # Merged with another shipment
    EXPIRED = "expired"


class AssemblyMode(enum.Enum):
    """Shipment assembly mode preference."""
    AUTO = "auto"  # Automatically create shipments
    MANUAL = "manual"  # Require user review
    ASSISTED = "assisted"  # Create but flag for review


class ShipmentSuggestion(Base):
    """
    A suggested grouping of documents into a shipment.
    
    Created by the shipment assembly service when documents share
    common identifiers (BOL, container, etc.)
    """
    __tablename__ = "shipment_suggestions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Linking identifier that groups these documents
    master_bl = Column(String(50), nullable=True, index=True)
    house_bl = Column(String(50), nullable=True, index=True)
    container_numbers = Column(ARRAY(String), nullable=True)
    booking_number = Column(String(50), nullable=True)
    
    # Confidence in the suggestion
    confidence_score = Column(Float, default=0.0)
    match_reasons = Column(JSON, nullable=True)  # Why documents were grouped
    
    # Status
    status = Column(SQLEnum(SuggestionStatus), default=SuggestionStatus.PENDING, nullable=False)
    
    # Document IDs included in this suggestion
    document_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=False)
    document_count = Column(String, default="0")
    
    # Suggested shipment details (extracted from documents)
    suggested_details = Column(JSON, nullable=True)
    # Example: { 
    #   "vessel_name": "EVER GIVEN",
    #   "port_of_origin": "Shanghai",
    #   "port_of_destination": "Los Angeles",
    #   "eta": "2024-02-15",
    #   "consignee": "XYZ Electronics Corp",
    #   "shipper": "Global Manufacturing Ltd"
    # }
    
    # If accepted, links to created shipment
    created_shipment_id = Column(UUID(as_uuid=True), ForeignKey("shipments.id", ondelete="SET NULL"), nullable=True)
    
    # Audit trail
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_by = Column(String(255), nullable=True)
    rejection_reason = Column(Text, nullable=True)
    
    # Tenant isolation
    tenant_id = Column(String(100), nullable=True, index=True)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "id": str(self.id),
            "master_bl": self.master_bl,
            "house_bl": self.house_bl,
            "container_numbers": self.container_numbers or [],
            "booking_number": self.booking_number,
            "confidence_score": self.confidence_score,
            "match_reasons": self.match_reasons or [],
            "status": self.status.value if self.status else None,
            "document_ids": [str(d) for d in self.document_ids] if self.document_ids else [],
            "document_count": len(self.document_ids) if self.document_ids else 0,
            "suggested_details": self.suggested_details or {},
            "created_shipment_id": str(self.created_shipment_id) if self.created_shipment_id else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "reviewed_by": self.reviewed_by,
            "rejection_reason": self.rejection_reason,
        }


class ShipmentSuggestionDocument(Base):
    """
    Links documents to shipment suggestions with role information.
    """
    __tablename__ = "shipment_suggestion_documents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    suggestion_id = Column(UUID(as_uuid=True), ForeignKey("shipment_suggestions.id", ondelete="CASCADE"), nullable=False)
    document_id = Column(UUID(as_uuid=True), ForeignKey("document_metadata.id", ondelete="CASCADE"), nullable=False)
    
    # Document role in the shipment
    document_type = Column(String(100), nullable=True)  # "Commercial Invoice", "Master BL", etc.
    document_role = Column(String(50), nullable=True)  # "primary", "supporting", etc.
    
    # Linking info extracted from this document
    extracted_identifiers = Column(JSON, nullable=True)
    # Example: {
    #   "master_bl": "MAEU123456789",
    #   "invoice_number": "INV-001",
    #   "consignee": "XYZ Corp"
    # }
    
    # Confidence that this document belongs
    match_confidence = Column(Float, default=1.0)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ClientAssemblyPreference(Base):
    """
    Per-client preference for shipment assembly mode.
    """
    __tablename__ = "client_assembly_preferences"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(String(100), unique=True, nullable=False, index=True)
    
    # Assembly mode: auto, manual, or assisted
    assembly_mode = Column(SQLEnum(AssemblyMode), default=AssemblyMode.MANUAL, nullable=False)
    
    # Auto-accept threshold (only used in assisted mode)
    auto_accept_threshold = Column(Float, default=0.9)  # Accept if confidence > 90%
    
    # Notification preferences
    notify_on_suggestion = Column(Boolean, default=True)
    notify_on_auto_accept = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "client_id": self.client_id,
            "assembly_mode": self.assembly_mode.value if self.assembly_mode else "manual",
            "auto_accept_threshold": self.auto_accept_threshold,
            "notify_on_suggestion": self.notify_on_suggestion,
            "notify_on_auto_accept": self.notify_on_auto_accept,
        }

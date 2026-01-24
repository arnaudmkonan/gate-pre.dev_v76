from enum import Enum
from sqlalchemy import Column, String, Float, ForeignKey, DateTime, Integer, Numeric, Enum as SAEnum, Index, Text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, ARRAY

from app.models.base import BaseModel


class ShipmentStatus(str, Enum):
    """Shipment completeness status."""
    PARTIAL = "partial"  # Some documents linked
    COMPLETE = "complete"  # All expected docs present
    READY_FOR_AUDIT = "ready_for_audit"  # Validated and ready
    IN_AUDIT = "in_audit"  # Currently being audited
    ARCHIVED = "archived"


class LinkMethod(str, Enum):
    """How documents were linked to shipment."""
    AUTO = "auto"  # Automatic linking via key matching
    MANUAL = "manual"  # User manually linked
    IMPORT = "import"  # Linked during data import


class Shipment(BaseModel):
    """
    Gold Layer: Reconciled shipment record (Lakehouse Architecture).
    
    Virtual folder grouping related documents via shared identifiers.
    Documents are linked through the ShipmentDocument junction table.
    """
    __tablename__ = "shipments"

    # Basic identification
    name = Column(String(500), nullable=True)  # Human-readable name
    reference_num = Column(String, nullable=True, index=True)
    
    # Primary linking key (what created this shipment)
    primary_key_type = Column(String(50), nullable=True)  # ENTRY_NUM, BOL_NUM, etc.
    primary_key_value = Column(String(500), nullable=True)
    
    # Status tracking
    status = Column(String(50), default=ShipmentStatus.PARTIAL.value, nullable=False)
    document_count = Column(Integer, default=0, nullable=False)
    document_types = Column(ARRAY(String), nullable=True, default=[])  # List of doc types in shipment
    
    # Denormalized key identifiers for fast search
    entry_number = Column(String(50), nullable=True, index=True)
    bol_number = Column(String(100), nullable=True, index=True)
    awb_number = Column(String(50), nullable=True, index=True)
    container_numbers = Column(ARRAY(String), nullable=True, default=[])
    po_numbers = Column(ARRAY(String), nullable=True, default=[])
    
    # Party information (denormalized for search)
    importer_name = Column(String(500), nullable=True, index=True)
    exporter_name = Column(String(500), nullable=True)
    manufacturer_name = Column(String(500), nullable=True)
    
    # Links to Silver Layer Parties (for resolved entities)
    shipper_id = Column(UUID(as_uuid=True), ForeignKey("parties.id"), nullable=True)
    consignee_id = Column(UUID(as_uuid=True), ForeignKey("parties.id"), nullable=True)
    
    # Transport info
    origin = Column(String, nullable=True)
    destination = Column(String, nullable=True)
    port_of_entry = Column(String(100), nullable=True)
    ship_date = Column(DateTime(timezone=True), nullable=True)
    arrival_date = Column(DateTime(timezone=True), nullable=True)
    entry_date = Column(DateTime(timezone=True), nullable=True)
    
    # Financial
    total_declared_value = Column(Numeric(precision=15, scale=2), nullable=True)
    total_duty = Column(Numeric(precision=15, scale=2), nullable=True)
    currency = Column(String(3), default="USD")
    
    # Legacy array field (kept for backward compatibility)
    documents = Column(ARRAY(UUID(as_uuid=True)), nullable=True, default=[])
    
    # Relationships
    shipper = relationship("app.models.silver_records.Party", foreign_keys=[shipper_id])
    consignee = relationship("app.models.silver_records.Party", foreign_keys=[consignee_id])
    
    invoices = relationship("CommercialInvoice", back_populates="shipment")
    compliance_screens = relationship("ComplianceScreen", back_populates="shipment", cascade="all, delete-orphan")
    
    # Junction table relationship
    linked_documents = relationship("ShipmentDocument", back_populates="shipment", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("ix_shipments_primary_key", "primary_key_type", "primary_key_value"),
        Index("ix_shipments_status", "status"),
        Index("ix_shipments_importer_name", "importer_name"),
    )


class ShipmentDocument(BaseModel):
    """
    Junction table linking documents to shipments.
    
    Tracks how and why each document was linked to a shipment.
    """
    __tablename__ = "shipment_documents"

    shipment_id = Column(UUID(as_uuid=True), ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False)
    document_id = Column(UUID(as_uuid=True), ForeignKey("raw_files.id", ondelete="CASCADE"), nullable=False)
    
    # How was this linked?
    linked_by_key_type = Column(String(50), nullable=True)  # The key type that caused the link
    linked_by_key_value = Column(String(500), nullable=True)  # The key value
    link_confidence = Column(Float, default=1.0, nullable=False)  # 0.0-1.0
    link_method = Column(String(20), default=LinkMethod.AUTO.value, nullable=False)
    
    # Relationships
    shipment = relationship("Shipment", back_populates="linked_documents")
    
    __table_args__ = (
        Index("ix_shipment_documents_shipment_id", "shipment_id"),
        Index("ix_shipment_documents_document_id", "document_id"),
        Index("ix_shipment_documents_shipment_doc", "shipment_id", "document_id", unique=True),
    )


class CommercialInvoice(BaseModel):
    """
    Gold Layer: Reconciled commercial invoice.
    PRD 4.4: id, invoice_num, vendor_id, buyer_id, invoice_date, currency, total_amount, shipment_id
    """
    __tablename__ = "commercial_invoices"

    invoice_num = Column(String, nullable=False, index=True)
    
    vendor_id = Column(UUID(as_uuid=True), ForeignKey("parties.id"), nullable=True)
    buyer_id = Column(UUID(as_uuid=True), ForeignKey("parties.id"), nullable=True)
    
    invoice_date = Column(DateTime(timezone=True), nullable=True)
    currency = Column(String, nullable=True, default="USD")
    total_amount = Column(Numeric(precision=15, scale=2), nullable=True)
    
    shipment_id = Column(UUID(as_uuid=True), ForeignKey("shipments.id"), nullable=True)

    # Relationships
    vendor = relationship("app.models.silver_records.Party", foreign_keys=[vendor_id])
    buyer = relationship("app.models.silver_records.Party", foreign_keys=[buyer_id])
    shipment = relationship("Shipment", back_populates="invoices")
    
    lines = relationship("InvoiceLine", back_populates="invoice", cascade="all, delete-orphan")


class InvoiceLine(BaseModel):
    """
    Gold Layer: Line item within an invoice.
    PRD 4.4: id, invoice_id, line_num, product_id, description, quantity, unit_price, amount, hs_code
    """
    __tablename__ = "invoice_lines"

    invoice_id = Column(UUID(as_uuid=True), ForeignKey("commercial_invoices.id"), nullable=False)
    
    line_num = Column(Integer, nullable=True)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=True)
    
    description = Column(String, nullable=True)
    quantity = Column(Numeric(precision=15, scale=4), nullable=True)
    unit_price = Column(Numeric(precision=15, scale=4), nullable=True)
    amount = Column(Numeric(precision=15, scale=2), nullable=True)
    hs_code = Column(String, nullable=True)  # Specific to this line, might match product or differ

    # Relationships
    invoice = relationship("CommercialInvoice", back_populates="lines")
    product = relationship("app.models.silver_records.Product")


class CustomsEntry(BaseModel):
    """
    Gold Layer: Customs entry filing.
    PRD 4.4: id, entry_num, entry_type, port_code, entry_date, importer_id, broker_id, duty_amount, status
    """
    __tablename__ = "customs_entries"

    entry_num = Column(String, nullable=False, unique=True, index=True)
    entry_type = Column(String, nullable=True)  # e.g., "01", "11"
    port_code = Column(String, nullable=True)
    entry_date = Column(DateTime(timezone=True), nullable=True)
    
    importer_id = Column(UUID(as_uuid=True), ForeignKey("parties.id"), nullable=True)
    broker_id = Column(UUID(as_uuid=True), ForeignKey("parties.id"), nullable=True)
    
    duty_amount = Column(Numeric(precision=15, scale=2), nullable=True)
    status = Column(String, nullable=True)

    # Relationships
    importer = relationship("app.models.silver_records.Party", foreign_keys=[importer_id])
    broker = relationship("app.models.silver_records.Party", foreign_keys=[broker_id])


class DataException(BaseModel):
    """
    Gold Layer: System or Business Logic Exceptions.
    PRD 4.4: id, exception_type, severity, source_document_id, field_name, expected_value, actual_value, status
    """
    __tablename__ = "data_exceptions"

    exception_type = Column(String, nullable=False)  # e.g., "validation_error", "reconciliation_mismatch"
    severity = Column(String, nullable=True)  # e.g., "high", "medium", "low"
    
    source_document_id = Column(UUID(as_uuid=True), ForeignKey("raw_files.id"), nullable=True)
    
    field_name = Column(String, nullable=True)
    expected_value = Column(String, nullable=True)
    actual_value = Column(String, nullable=True)
    
    status = Column(String, default="open", nullable=False)  # open, resolved, ignored
    resolution_notes = Column(String, nullable=True)

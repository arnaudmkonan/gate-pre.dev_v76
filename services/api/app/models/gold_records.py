from sqlalchemy import Column, String, Float, ForeignKey, DateTime, Integer, Numeric, Enum as SAEnum
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, ARRAY

from app.models.base import BaseModel

class Shipment(BaseModel):
    """
    Gold Layer: Reconciled shipment record.
    PRD 4.4: id, reference_num, shipper_id, consignee_id, origin, destination, ship_date, status, documents[]
    """
    __tablename__ = "shipments"

    reference_num = Column(String, nullable=True, index=True)
    
    # Links to Silver Layer Parties
    shipper_id = Column(UUID(as_uuid=True), ForeignKey("parties.id"), nullable=True)
    consignee_id = Column(UUID(as_uuid=True), ForeignKey("parties.id"), nullable=True)
    
    origin = Column(String, nullable=True)
    destination = Column(String, nullable=True)
    ship_date = Column(DateTime(timezone=True), nullable=True)
    status = Column(String, nullable=True)  # e.g., "in_transit", "arrived", "cleared"
    
    # List of document IDs associated with this shipment (Bronze layer IDs)
    documents = Column(ARRAY(UUID(as_uuid=True)), nullable=True, default=[])

    # Relationships
    shipper = relationship("app.models.silver_records.Party", foreign_keys=[shipper_id])
    consignee = relationship("app.models.silver_records.Party", foreign_keys=[consignee_id])
    
    invoices = relationship("CommercialInvoice", back_populates="shipment")


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

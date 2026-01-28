"""
Client Billing Model.

Data models for client billing and invoicing:
- Fee configurations (per-entry, percentage, flat fees)
- Billable line items (entries, amendments, ISFs)
- Invoices and line items
- Payment tracking

Task 4.6 from ROADMAP_FULL_WORKFLOW.md
"""
from enum import Enum
from datetime import datetime, date, timezone
from decimal import Decimal
from sqlalchemy import Column, String, DateTime, Date, ForeignKey, Integer, Text, Boolean, Index, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY

from app.models.base import BaseModel


class FeeType(str, Enum):
    """Types of fees."""
    FLAT = "flat"  # Flat fee per entry
    PERCENTAGE = "percentage"  # Percentage of value
    TIERED = "tiered"  # Tiered pricing based on volume


class BillableItemType(str, Enum):
    """Types of billable items."""
    ENTRY = "entry"
    AMENDMENT = "amendment"
    ISF = "isf"
    CONSULTATION = "consultation"
    CLASSIFICATION = "classification"
    POST_ENTRY = "post_entry"
    DOCUMENT_HANDLING = "document_handling"
    OTHER = "other"


class InvoiceStatus(str, Enum):
    """Invoice status."""
    DRAFT = "draft"
    PENDING = "pending"
    SENT = "sent"
    VIEWED = "viewed"
    PAID = "paid"
    PARTIAL = "partial"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"
    VOID = "void"


class PaymentMethod(str, Enum):
    """Payment methods."""
    ACH = "ach"
    WIRE = "wire"
    CHECK = "check"
    CREDIT_CARD = "credit_card"
    OTHER = "other"


class ClientFeeConfig(BaseModel):
    """
    Fee configuration for a client.
    
    Defines how the client is billed for various services.
    """
    __tablename__ = "client_fee_configs"
    
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    
    # Fee name/description
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    
    # Fee type and item
    fee_type = Column(String(30), default=FeeType.FLAT.value, nullable=False)
    billable_type = Column(String(50), default=BillableItemType.ENTRY.value, nullable=False)
    
    # Flat fee
    flat_amount = Column(Numeric(15, 2), nullable=True)
    
    # Percentage fee
    percentage_rate = Column(Numeric(8, 4), nullable=True)  # e.g., 0.0125 for 1.25%
    min_fee = Column(Numeric(15, 2), nullable=True)  # Minimum charge
    max_fee = Column(Numeric(15, 2), nullable=True)  # Maximum charge (cap)
    
    # Tiered pricing (stored as JSON)
    # Format: [{"min_qty": 0, "max_qty": 10, "rate": 125}, {"min_qty": 11, "max_qty": 50, "rate": 100}]
    tiers = Column(JSONB, nullable=True)
    
    # Active status
    is_active = Column(Boolean, default=True, nullable=False)
    effective_date = Column(Date, nullable=True)
    expiration_date = Column(Date, nullable=True)
    
    # Relationships
    client = relationship("Client", foreign_keys=[client_id])
    
    __table_args__ = (
        Index("ix_client_fee_configs_client", "client_id"),
        Index("ix_client_fee_configs_type", "billable_type"),
    )
    
    def calculate_fee(self, quantity: int = 1, value: Decimal = None) -> Decimal:
        """Calculate fee based on configuration."""
        if self.fee_type == FeeType.FLAT.value:
            return Decimal(str(self.flat_amount or 0)) * quantity
        
        elif self.fee_type == FeeType.PERCENTAGE.value and value:
            fee = value * Decimal(str(self.percentage_rate or 0))
            if self.min_fee and fee < self.min_fee:
                fee = Decimal(str(self.min_fee))
            if self.max_fee and fee > self.max_fee:
                fee = Decimal(str(self.max_fee))
            return fee * quantity
        
        elif self.fee_type == FeeType.TIERED.value and self.tiers:
            # Find applicable tier
            for tier in sorted(self.tiers, key=lambda x: x.get("min_qty", 0)):
                min_qty = tier.get("min_qty", 0)
                max_qty = tier.get("max_qty", float("inf"))
                if min_qty <= quantity <= max_qty:
                    return Decimal(str(tier.get("rate", 0))) * quantity
        
        return Decimal("0")
    
    def to_dict(self):
        return {
            "id": str(self.id),
            "client_id": str(self.client_id),
            "name": self.name,
            "description": self.description,
            "fee_type": self.fee_type,
            "billable_type": self.billable_type,
            "flat_amount": float(self.flat_amount) if self.flat_amount else None,
            "percentage_rate": float(self.percentage_rate) if self.percentage_rate else None,
            "min_fee": float(self.min_fee) if self.min_fee else None,
            "max_fee": float(self.max_fee) if self.max_fee else None,
            "tiers": self.tiers,
            "is_active": self.is_active,
            "effective_date": self.effective_date.isoformat() if self.effective_date else None,
            "expiration_date": self.expiration_date.isoformat() if self.expiration_date else None,
        }


class BillableItem(BaseModel):
    """
    Billable item for a client.
    
    Tracks work done that should be invoiced.
    """
    __tablename__ = "billable_items"
    
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    
    # Item type and reference
    item_type = Column(String(50), default=BillableItemType.ENTRY.value, nullable=False)
    reference_id = Column(UUID(as_uuid=True), nullable=True)  # Entry ID, ISF ID, etc.
    reference_number = Column(String(50), nullable=True)  # Entry number, etc.
    
    # Description
    description = Column(Text, nullable=False)
    
    # Service date
    service_date = Column(Date, nullable=False, default=date.today)
    
    # Pricing
    quantity = Column(Integer, default=1, nullable=False)
    unit_price = Column(Numeric(15, 2), nullable=False)
    total_amount = Column(Numeric(15, 2), nullable=False)
    
    # Value (for percentage-based fees)
    reference_value = Column(Numeric(15, 2), nullable=True)
    
    # Fee config used
    fee_config_id = Column(UUID(as_uuid=True), ForeignKey("client_fee_configs.id"), nullable=True)
    
    # Invoice linking
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("client_invoices.id"), nullable=True)
    is_invoiced = Column(Boolean, default=False, nullable=False)
    invoiced_at = Column(DateTime(timezone=True), nullable=True)
    
    # Notes
    notes = Column(Text, nullable=True)
    
    # Relationships
    client = relationship("Client", foreign_keys=[client_id])
    fee_config = relationship("ClientFeeConfig", foreign_keys=[fee_config_id])
    invoice = relationship("ClientInvoice", back_populates="items")
    
    __table_args__ = (
        Index("ix_billable_items_client", "client_id"),
        Index("ix_billable_items_type", "item_type"),
        Index("ix_billable_items_invoiced", "is_invoiced"),
        Index("ix_billable_items_invoice", "invoice_id"),
        Index("ix_billable_items_service_date", "service_date"),
    )
    
    def to_dict(self):
        return {
            "id": str(self.id),
            "client_id": str(self.client_id),
            "item_type": self.item_type,
            "reference_id": str(self.reference_id) if self.reference_id else None,
            "reference_number": self.reference_number,
            "description": self.description,
            "service_date": self.service_date.isoformat() if self.service_date else None,
            "quantity": self.quantity,
            "unit_price": float(self.unit_price),
            "total_amount": float(self.total_amount),
            "reference_value": float(self.reference_value) if self.reference_value else None,
            "is_invoiced": self.is_invoiced,
            "invoice_id": str(self.invoice_id) if self.invoice_id else None,
        }


class ClientInvoice(BaseModel):
    """
    Invoice for a client.
    
    Groups billable items into an invoice.
    """
    __tablename__ = "client_invoices"
    
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    
    # Invoice number
    invoice_number = Column(String(50), unique=True, nullable=False)
    
    # Status
    status = Column(String(30), default=InvoiceStatus.DRAFT.value, nullable=False)
    
    # Dates
    invoice_date = Column(Date, nullable=False, default=date.today)
    due_date = Column(Date, nullable=True)
    period_start = Column(Date, nullable=True)
    period_end = Column(Date, nullable=True)
    
    # Amounts
    subtotal = Column(Numeric(15, 2), default=0, nullable=False)
    tax_amount = Column(Numeric(15, 2), default=0, nullable=False)
    discount_amount = Column(Numeric(15, 2), default=0, nullable=False)
    total_amount = Column(Numeric(15, 2), default=0, nullable=False)
    
    # Payment
    amount_paid = Column(Numeric(15, 2), default=0, nullable=False)
    amount_due = Column(Numeric(15, 2), default=0, nullable=False)
    
    # Payment tracking
    paid_date = Column(Date, nullable=True)
    payment_method = Column(String(30), nullable=True)
    payment_reference = Column(String(100), nullable=True)  # Check #, transaction ID
    
    # Sent tracking
    sent_at = Column(DateTime(timezone=True), nullable=True)
    viewed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Notes
    notes = Column(Text, nullable=True)
    internal_notes = Column(Text, nullable=True)
    
    # External integration
    external_id = Column(String(100), nullable=True)  # QuickBooks/Xero ID
    external_system = Column(String(50), nullable=True)  # quickbooks, xero
    
    # Relationships
    client = relationship("Client", foreign_keys=[client_id])
    items = relationship("BillableItem", back_populates="invoice", lazy="selectin")
    payments = relationship("InvoicePayment", back_populates="invoice", lazy="selectin")
    
    __table_args__ = (
        Index("ix_client_invoices_client", "client_id"),
        Index("ix_client_invoices_status", "status"),
        Index("ix_client_invoices_date", "invoice_date"),
        Index("ix_client_invoices_due", "due_date"),
    )
    
    def calculate_totals(self):
        """Recalculate invoice totals from items."""
        self.subtotal = sum(Decimal(str(item.total_amount)) for item in (self.items or []))
        self.total_amount = self.subtotal + Decimal(str(self.tax_amount or 0)) - Decimal(str(self.discount_amount or 0))
        self.amount_due = self.total_amount - Decimal(str(self.amount_paid or 0))
    
    def to_dict(self):
        return {
            "id": str(self.id),
            "client_id": str(self.client_id),
            "invoice_number": self.invoice_number,
            "status": self.status,
            "invoice_date": self.invoice_date.isoformat() if self.invoice_date else None,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "period_start": self.period_start.isoformat() if self.period_start else None,
            "period_end": self.period_end.isoformat() if self.period_end else None,
            "subtotal": float(self.subtotal),
            "tax_amount": float(self.tax_amount),
            "discount_amount": float(self.discount_amount),
            "total_amount": float(self.total_amount),
            "amount_paid": float(self.amount_paid),
            "amount_due": float(self.amount_due),
            "paid_date": self.paid_date.isoformat() if self.paid_date else None,
            "payment_method": self.payment_method,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "item_count": len(self.items) if self.items else 0,
            "items": [item.to_dict() for item in (self.items or [])],
        }


class InvoicePayment(BaseModel):
    """
    Payment record for an invoice.
    
    Tracks partial or full payments.
    """
    __tablename__ = "invoice_payments"
    
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("client_invoices.id", ondelete="CASCADE"), nullable=False)
    
    # Payment details
    payment_date = Column(Date, nullable=False, default=date.today)
    amount = Column(Numeric(15, 2), nullable=False)
    payment_method = Column(String(30), nullable=True)
    reference = Column(String(100), nullable=True)  # Check #, transaction ID
    
    # Notes
    notes = Column(Text, nullable=True)
    
    # Relationships
    invoice = relationship("ClientInvoice", back_populates="payments")
    
    __table_args__ = (
        Index("ix_invoice_payments_invoice", "invoice_id"),
        Index("ix_invoice_payments_date", "payment_date"),
    )
    
    def to_dict(self):
        return {
            "id": str(self.id),
            "invoice_id": str(self.invoice_id),
            "payment_date": self.payment_date.isoformat() if self.payment_date else None,
            "amount": float(self.amount),
            "payment_method": self.payment_method,
            "reference": self.reference,
            "notes": self.notes,
        }

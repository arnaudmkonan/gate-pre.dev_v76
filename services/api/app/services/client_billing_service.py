"""
Client Billing Service.

Manages client billing:
- Fee configuration CRUD
- Billable item tracking
- Invoice generation
- Payment recording

Task 4.6 from ROADMAP_FULL_WORKFLOW.md
"""
from datetime import datetime, date, timezone, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from decimal import Decimal

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.client_billing import (
    ClientFeeConfig, BillableItem, ClientInvoice, InvoicePayment,
    FeeType, BillableItemType, InvoiceStatus, PaymentMethod
)
from app.models.client import Client


class ClientBillingService:
    """Service for managing client billing and invoicing."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    # ==================== Fee Configuration ====================
    
    async def create_fee_config(
        self,
        client_id: UUID,
        data: Dict[str, Any],
    ) -> ClientFeeConfig:
        """Create a fee configuration for a client."""
        config = ClientFeeConfig(
            client_id=client_id,
            name=data.get("name", "Entry Fee"),
            description=data.get("description"),
            fee_type=data.get("fee_type", FeeType.FLAT.value),
            billable_type=data.get("billable_type", BillableItemType.ENTRY.value),
            flat_amount=Decimal(str(data["flat_amount"])) if data.get("flat_amount") else None,
            percentage_rate=Decimal(str(data["percentage_rate"])) if data.get("percentage_rate") else None,
            min_fee=Decimal(str(data["min_fee"])) if data.get("min_fee") else None,
            max_fee=Decimal(str(data["max_fee"])) if data.get("max_fee") else None,
            tiers=data.get("tiers"),
            is_active=data.get("is_active", True),
            effective_date=self._parse_date(data.get("effective_date")),
            expiration_date=self._parse_date(data.get("expiration_date")),
        )
        
        self.db.add(config)
        await self.db.commit()
        await self.db.refresh(config)
        
        return config
    
    async def get_fee_config(self, config_id: UUID) -> Optional[ClientFeeConfig]:
        """Get fee configuration by ID."""
        query = select(ClientFeeConfig).where(ClientFeeConfig.id == config_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def list_fee_configs(
        self,
        client_id: UUID,
        active_only: bool = True,
    ) -> List[ClientFeeConfig]:
        """List fee configurations for a client."""
        query = select(ClientFeeConfig).where(ClientFeeConfig.client_id == client_id)
        
        if active_only:
            query = query.where(ClientFeeConfig.is_active == True)
        
        query = query.order_by(ClientFeeConfig.billable_type)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def get_fee_for_type(
        self,
        client_id: UUID,
        billable_type: str,
    ) -> Optional[ClientFeeConfig]:
        """Get active fee config for a specific billable type."""
        query = select(ClientFeeConfig).where(
            and_(
                ClientFeeConfig.client_id == client_id,
                ClientFeeConfig.billable_type == billable_type,
                ClientFeeConfig.is_active == True,
            )
        ).order_by(ClientFeeConfig.created_at.desc())
        
        result = await self.db.execute(query)
        return result.scalars().first()
    
    async def update_fee_config(
        self,
        config_id: UUID,
        data: Dict[str, Any],
    ) -> ClientFeeConfig:
        """Update a fee configuration."""
        config = await self.get_fee_config(config_id)
        if not config:
            raise ValueError(f"Fee config {config_id} not found")
        
        updatable = [
            'name', 'description', 'fee_type', 'flat_amount',
            'percentage_rate', 'min_fee', 'max_fee', 'tiers',
            'is_active', 'effective_date', 'expiration_date'
        ]
        
        for field in updatable:
            if field in data:
                value = data[field]
                if field in ['flat_amount', 'percentage_rate', 'min_fee', 'max_fee'] and value is not None:
                    value = Decimal(str(value))
                elif field in ['effective_date', 'expiration_date']:
                    value = self._parse_date(value)
                setattr(config, field, value)
        
        await self.db.commit()
        await self.db.refresh(config)
        
        return config
    
    # ==================== Billable Items ====================
    
    async def create_billable_item(
        self,
        client_id: UUID,
        item_type: str,
        description: str,
        quantity: int = 1,
        unit_price: Optional[float] = None,
        reference_id: Optional[UUID] = None,
        reference_number: Optional[str] = None,
        reference_value: Optional[float] = None,
        service_date: Optional[date] = None,
    ) -> BillableItem:
        """Create a billable item for a client."""
        # If no unit price, try to get from fee config
        if unit_price is None:
            fee_config = await self.get_fee_for_type(client_id, item_type)
            if fee_config:
                value = Decimal(str(reference_value)) if reference_value else None
                unit_price = float(fee_config.calculate_fee(1, value))
            else:
                unit_price = 0
        
        total = Decimal(str(unit_price)) * quantity
        
        item = BillableItem(
            client_id=client_id,
            item_type=item_type,
            reference_id=reference_id,
            reference_number=reference_number,
            description=description,
            service_date=service_date or date.today(),
            quantity=quantity,
            unit_price=Decimal(str(unit_price)),
            total_amount=total,
            reference_value=Decimal(str(reference_value)) if reference_value else None,
        )
        
        self.db.add(item)
        await self.db.commit()
        await self.db.refresh(item)
        
        return item
    
    async def get_billable_item(self, item_id: UUID) -> Optional[BillableItem]:
        """Get billable item by ID."""
        query = select(BillableItem).where(BillableItem.id == item_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def list_billable_items(
        self,
        client_id: UUID,
        invoiced: Optional[bool] = None,
        item_type: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[BillableItem]:
        """List billable items for a client."""
        query = select(BillableItem).where(BillableItem.client_id == client_id)
        
        if invoiced is not None:
            query = query.where(BillableItem.is_invoiced == invoiced)
        
        if item_type:
            query = query.where(BillableItem.item_type == item_type)
        
        if start_date:
            query = query.where(BillableItem.service_date >= start_date)
        
        if end_date:
            query = query.where(BillableItem.service_date <= end_date)
        
        query = query.order_by(BillableItem.service_date.desc())
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def get_uninvoiced_summary(
        self,
        client_id: UUID,
    ) -> Dict[str, Any]:
        """Get summary of uninvoiced items for a client."""
        items = await self.list_billable_items(client_id, invoiced=False)
        
        by_type = {}
        total = Decimal("0")
        
        for item in items:
            item_type = item.item_type
            if item_type not in by_type:
                by_type[item_type] = {"count": 0, "amount": Decimal("0")}
            by_type[item_type]["count"] += item.quantity
            by_type[item_type]["amount"] += Decimal(str(item.total_amount))
            total += Decimal(str(item.total_amount))
        
        return {
            "client_id": str(client_id),
            "uninvoiced_items": len(items),
            "total_amount": float(total),
            "by_type": {k: {"count": v["count"], "amount": float(v["amount"])} for k, v in by_type.items()},
        }
    
    # ==================== Invoices ====================
    
    async def create_invoice(
        self,
        client_id: UUID,
        item_ids: Optional[List[UUID]] = None,
        period_start: Optional[date] = None,
        period_end: Optional[date] = None,
        due_days: int = 30,
        notes: Optional[str] = None,
    ) -> ClientInvoice:
        """
        Create an invoice for a client.
        
        If item_ids provided, includes those specific items.
        Otherwise, includes all uninvoiced items for the period.
        """
        # Get items
        if item_ids:
            items = []
            for item_id in item_ids:
                item = await self.get_billable_item(item_id)
                if item and not item.is_invoiced and item.client_id == client_id:
                    items.append(item)
        else:
            items = await self.list_billable_items(
                client_id,
                invoiced=False,
                start_date=period_start,
                end_date=period_end,
            )
        
        if not items:
            raise ValueError("No uninvoiced items found")
        
        # Generate invoice number
        invoice_number = await self._generate_invoice_number()
        
        # Calculate totals
        subtotal = sum(Decimal(str(item.total_amount)) for item in items)
        
        # Create invoice
        invoice = ClientInvoice(
            client_id=client_id,
            invoice_number=invoice_number,
            status=InvoiceStatus.DRAFT.value,
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=due_days),
            period_start=period_start or min(item.service_date for item in items),
            period_end=period_end or max(item.service_date for item in items),
            subtotal=subtotal,
            tax_amount=Decimal("0"),
            discount_amount=Decimal("0"),
            total_amount=subtotal,
            amount_paid=Decimal("0"),
            amount_due=subtotal,
            notes=notes,
        )
        
        self.db.add(invoice)
        await self.db.flush()
        
        # Link items to invoice
        for item in items:
            item.invoice_id = invoice.id
            item.is_invoiced = True
            item.invoiced_at = datetime.now(timezone.utc)
        
        await self.db.commit()
        await self.db.refresh(invoice)
        
        return invoice
    
    async def _generate_invoice_number(self) -> str:
        """Generate unique invoice number."""
        # Format: INV-YYYYMMDD-XXXX
        today = date.today().strftime("%Y%m%d")
        
        # Get count of invoices today
        query = select(func.count(ClientInvoice.id)).where(
            ClientInvoice.invoice_number.like(f"INV-{today}-%")
        )
        result = await self.db.execute(query)
        count = result.scalar() or 0
        
        return f"INV-{today}-{count + 1:04d}"
    
    async def get_invoice(self, invoice_id: UUID) -> Optional[ClientInvoice]:
        """Get invoice by ID."""
        query = (
            select(ClientInvoice)
            .options(selectinload(ClientInvoice.items))
            .where(ClientInvoice.id == invoice_id)
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_invoice_by_number(self, invoice_number: str) -> Optional[ClientInvoice]:
        """Get invoice by number."""
        query = (
            select(ClientInvoice)
            .options(selectinload(ClientInvoice.items))
            .where(ClientInvoice.invoice_number == invoice_number)
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def list_invoices(
        self,
        client_id: Optional[UUID] = None,
        status: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[ClientInvoice]:
        """List invoices with optional filtering."""
        query = select(ClientInvoice).options(selectinload(ClientInvoice.items))
        
        if client_id:
            query = query.where(ClientInvoice.client_id == client_id)
        
        if status:
            query = query.where(ClientInvoice.status == status)
        
        if start_date:
            query = query.where(ClientInvoice.invoice_date >= start_date)
        
        if end_date:
            query = query.where(ClientInvoice.invoice_date <= end_date)
        
        query = query.order_by(ClientInvoice.invoice_date.desc())
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def send_invoice(self, invoice_id: UUID) -> ClientInvoice:
        """Mark invoice as sent."""
        invoice = await self.get_invoice(invoice_id)
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")
        
        invoice.status = InvoiceStatus.SENT.value
        invoice.sent_at = datetime.now(timezone.utc)
        
        await self.db.commit()
        await self.db.refresh(invoice)
        
        return invoice
    
    async def void_invoice(self, invoice_id: UUID) -> ClientInvoice:
        """Void an invoice."""
        invoice = await self.get_invoice(invoice_id)
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")
        
        if invoice.status == InvoiceStatus.PAID.value:
            raise ValueError("Cannot void a paid invoice")
        
        # Unlink items
        for item in invoice.items:
            item.invoice_id = None
            item.is_invoiced = False
            item.invoiced_at = None
        
        invoice.status = InvoiceStatus.VOID.value
        
        await self.db.commit()
        await self.db.refresh(invoice)
        
        return invoice
    
    # ==================== Payments ====================
    
    async def record_payment(
        self,
        invoice_id: UUID,
        amount: float,
        payment_date: Optional[date] = None,
        payment_method: Optional[str] = None,
        reference: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> InvoicePayment:
        """Record a payment for an invoice."""
        invoice = await self.get_invoice(invoice_id)
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")
        
        payment = InvoicePayment(
            invoice_id=invoice_id,
            payment_date=payment_date or date.today(),
            amount=Decimal(str(amount)),
            payment_method=payment_method,
            reference=reference,
            notes=notes,
        )
        
        self.db.add(payment)
        
        # Update invoice
        invoice.amount_paid = Decimal(str(invoice.amount_paid or 0)) + Decimal(str(amount))
        invoice.amount_due = Decimal(str(invoice.total_amount)) - invoice.amount_paid
        
        if invoice.amount_due <= 0:
            invoice.status = InvoiceStatus.PAID.value
            invoice.paid_date = payment_date or date.today()
        elif invoice.amount_paid > 0:
            invoice.status = InvoiceStatus.PARTIAL.value
        
        await self.db.commit()
        await self.db.refresh(payment)
        
        return payment
    
    async def get_payment_history(self, invoice_id: UUID) -> List[InvoicePayment]:
        """Get payment history for an invoice."""
        query = select(InvoicePayment).where(
            InvoicePayment.invoice_id == invoice_id
        ).order_by(InvoicePayment.payment_date)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    # ==================== Auto-billing ====================
    
    async def auto_bill_entry(
        self,
        client_id: UUID,
        entry_id: UUID,
        entry_number: str,
        entry_value: float,
    ) -> Optional[BillableItem]:
        """Automatically create billable item for an entry."""
        fee_config = await self.get_fee_for_type(client_id, BillableItemType.ENTRY.value)
        if not fee_config:
            return None
        
        unit_price = fee_config.calculate_fee(1, Decimal(str(entry_value)))
        
        return await self.create_billable_item(
            client_id=client_id,
            item_type=BillableItemType.ENTRY.value,
            description=f"Entry filing: {entry_number}",
            quantity=1,
            unit_price=float(unit_price),
            reference_id=entry_id,
            reference_number=entry_number,
            reference_value=entry_value,
        )
    
    async def auto_bill_isf(
        self,
        client_id: UUID,
        isf_id: UUID,
        isf_number: str,
    ) -> Optional[BillableItem]:
        """Automatically create billable item for an ISF."""
        fee_config = await self.get_fee_for_type(client_id, BillableItemType.ISF.value)
        if not fee_config:
            return None
        
        unit_price = fee_config.calculate_fee(1)
        
        return await self.create_billable_item(
            client_id=client_id,
            item_type=BillableItemType.ISF.value,
            description=f"ISF filing: {isf_number}",
            quantity=1,
            unit_price=float(unit_price),
            reference_id=isf_id,
            reference_number=isf_number,
        )
    
    # ==================== Helpers ====================
    
    def _parse_date(self, value) -> Optional[date]:
        """Parse date from various formats."""
        if not value:
            return None
        if isinstance(value, date):
            return value
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
            except:
                pass
            try:
                return datetime.strptime(value[:10], "%Y-%m-%d").date()
            except:
                pass
        return None

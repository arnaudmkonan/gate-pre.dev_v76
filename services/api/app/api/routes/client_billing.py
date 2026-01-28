"""
Client Billing API Routes.

Endpoints for client billing and invoicing.

Task 4.6 from ROADMAP_FULL_WORKFLOW.md
"""
from typing import Optional, List
from uuid import UUID
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db


router = APIRouter(prefix="/api/billing", tags=["Client Billing"])


# ==================== Request Models ====================

class FeeConfigCreate(BaseModel):
    """Create fee configuration."""
    name: str
    description: Optional[str] = None
    fee_type: str = "flat"
    billable_type: str = "entry"
    flat_amount: Optional[float] = None
    percentage_rate: Optional[float] = None
    min_fee: Optional[float] = None
    max_fee: Optional[float] = None
    tiers: Optional[List[dict]] = None
    effective_date: Optional[str] = None
    expiration_date: Optional[str] = None


class FeeConfigUpdate(BaseModel):
    """Update fee configuration."""
    name: Optional[str] = None
    description: Optional[str] = None
    flat_amount: Optional[float] = None
    percentage_rate: Optional[float] = None
    min_fee: Optional[float] = None
    max_fee: Optional[float] = None
    is_active: Optional[bool] = None


class BillableItemCreate(BaseModel):
    """Create billable item."""
    item_type: str = "entry"
    description: str
    quantity: int = 1
    unit_price: Optional[float] = None
    reference_id: Optional[str] = None
    reference_number: Optional[str] = None
    reference_value: Optional[float] = None
    service_date: Optional[str] = None


class InvoiceCreate(BaseModel):
    """Create invoice."""
    item_ids: Optional[List[str]] = None
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    due_days: int = 30
    notes: Optional[str] = None


class PaymentRecord(BaseModel):
    """Record payment."""
    amount: float
    payment_date: Optional[str] = None
    payment_method: Optional[str] = None
    reference: Optional[str] = None
    notes: Optional[str] = None


# ==================== Fee Configuration Endpoints ====================

@router.post("/clients/{client_id}/fee-configs")
async def create_fee_config(
    client_id: str,
    request: FeeConfigCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a fee configuration for a client."""
    from app.services.client_billing_service import ClientBillingService
    
    try:
        client_uuid = UUID(client_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid client ID")
    
    service = ClientBillingService(db)
    config = await service.create_fee_config(client_uuid, request.model_dump())
    
    return {
        "fee_config": config.to_dict(),
        "message": "Fee configuration created",
    }


@router.get("/clients/{client_id}/fee-configs")
async def list_fee_configs(
    client_id: str,
    active_only: bool = Query(True),
    db: AsyncSession = Depends(get_db),
):
    """List fee configurations for a client."""
    from app.services.client_billing_service import ClientBillingService
    
    try:
        client_uuid = UUID(client_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid client ID")
    
    service = ClientBillingService(db)
    configs = await service.list_fee_configs(client_uuid, active_only)
    
    return {
        "client_id": client_id,
        "fee_configs": [c.to_dict() for c in configs],
        "count": len(configs),
    }


@router.put("/fee-configs/{config_id}")
async def update_fee_config(
    config_id: str,
    request: FeeConfigUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a fee configuration."""
    from app.services.client_billing_service import ClientBillingService
    
    try:
        config_uuid = UUID(config_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid config ID")
    
    service = ClientBillingService(db)
    
    try:
        config = await service.update_fee_config(config_uuid, request.model_dump(exclude_none=True))
        return {
            "fee_config": config.to_dict(),
            "message": "Fee configuration updated",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==================== Billable Item Endpoints ====================

@router.post("/clients/{client_id}/billable-items")
async def create_billable_item(
    client_id: str,
    request: BillableItemCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a billable item for a client."""
    from app.services.client_billing_service import ClientBillingService
    
    try:
        client_uuid = UUID(client_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid client ID")
    
    service = ClientBillingService(db)
    
    item = await service.create_billable_item(
        client_id=client_uuid,
        item_type=request.item_type,
        description=request.description,
        quantity=request.quantity,
        unit_price=request.unit_price,
        reference_id=UUID(request.reference_id) if request.reference_id else None,
        reference_number=request.reference_number,
        reference_value=request.reference_value,
        service_date=datetime.strptime(request.service_date, "%Y-%m-%d").date() if request.service_date else None,
    )
    
    return {
        "billable_item": item.to_dict(),
        "message": "Billable item created",
    }


@router.get("/clients/{client_id}/billable-items")
async def list_billable_items(
    client_id: str,
    invoiced: Optional[bool] = Query(None),
    item_type: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List billable items for a client."""
    from app.services.client_billing_service import ClientBillingService
    
    try:
        client_uuid = UUID(client_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid client ID")
    
    service = ClientBillingService(db)
    
    items = await service.list_billable_items(
        client_uuid,
        invoiced=invoiced,
        item_type=item_type,
        start_date=datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else None,
        end_date=datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else None,
    )
    
    return {
        "client_id": client_id,
        "billable_items": [i.to_dict() for i in items],
        "count": len(items),
    }


@router.get("/clients/{client_id}/billable-items/uninvoiced")
async def get_uninvoiced_summary(
    client_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get summary of uninvoiced items for a client."""
    from app.services.client_billing_service import ClientBillingService
    
    try:
        client_uuid = UUID(client_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid client ID")
    
    service = ClientBillingService(db)
    summary = await service.get_uninvoiced_summary(client_uuid)
    
    return summary


# ==================== Invoice Endpoints ====================

@router.post("/clients/{client_id}/invoices")
async def create_invoice(
    client_id: str,
    request: InvoiceCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create an invoice for a client."""
    from app.services.client_billing_service import ClientBillingService
    
    try:
        client_uuid = UUID(client_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid client ID")
    
    service = ClientBillingService(db)
    
    try:
        invoice = await service.create_invoice(
            client_uuid,
            item_ids=[UUID(i) for i in request.item_ids] if request.item_ids else None,
            period_start=datetime.strptime(request.period_start, "%Y-%m-%d").date() if request.period_start else None,
            period_end=datetime.strptime(request.period_end, "%Y-%m-%d").date() if request.period_end else None,
            due_days=request.due_days,
            notes=request.notes,
        )
        
        return {
            "invoice": invoice.to_dict(),
            "message": f"Invoice {invoice.invoice_number} created",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/clients/{client_id}/invoices")
async def list_client_invoices(
    client_id: str,
    status: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List invoices for a client."""
    from app.services.client_billing_service import ClientBillingService
    
    try:
        client_uuid = UUID(client_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid client ID")
    
    service = ClientBillingService(db)
    
    invoices = await service.list_invoices(
        client_uuid,
        status=status,
        start_date=datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else None,
        end_date=datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else None,
    )
    
    return {
        "client_id": client_id,
        "invoices": [i.to_dict() for i in invoices],
        "count": len(invoices),
    }


@router.get("/invoices/{invoice_id}")
async def get_invoice(
    invoice_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get invoice details."""
    from app.services.client_billing_service import ClientBillingService
    
    try:
        invoice_uuid = UUID(invoice_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid invoice ID")
    
    service = ClientBillingService(db)
    invoice = await service.get_invoice(invoice_uuid)
    
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    return invoice.to_dict()


@router.post("/invoices/{invoice_id}/send")
async def send_invoice(
    invoice_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Mark invoice as sent."""
    from app.services.client_billing_service import ClientBillingService
    
    try:
        invoice_uuid = UUID(invoice_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid invoice ID")
    
    service = ClientBillingService(db)
    
    try:
        invoice = await service.send_invoice(invoice_uuid)
        return {
            "invoice": invoice.to_dict(),
            "message": "Invoice marked as sent",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/invoices/{invoice_id}/void")
async def void_invoice(
    invoice_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Void an invoice."""
    from app.services.client_billing_service import ClientBillingService
    
    try:
        invoice_uuid = UUID(invoice_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid invoice ID")
    
    service = ClientBillingService(db)
    
    try:
        invoice = await service.void_invoice(invoice_uuid)
        return {
            "invoice": invoice.to_dict(),
            "message": "Invoice voided",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==================== Payment Endpoints ====================

@router.post("/invoices/{invoice_id}/payments")
async def record_payment(
    invoice_id: str,
    request: PaymentRecord,
    db: AsyncSession = Depends(get_db),
):
    """Record a payment for an invoice."""
    from app.services.client_billing_service import ClientBillingService
    
    try:
        invoice_uuid = UUID(invoice_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid invoice ID")
    
    service = ClientBillingService(db)
    
    try:
        payment = await service.record_payment(
            invoice_uuid,
            request.amount,
            payment_date=datetime.strptime(request.payment_date, "%Y-%m-%d").date() if request.payment_date else None,
            payment_method=request.payment_method,
            reference=request.reference,
            notes=request.notes,
        )
        
        return {
            "payment": payment.to_dict(),
            "message": f"Payment of ${request.amount:.2f} recorded",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/invoices/{invoice_id}/payments")
async def get_payment_history(
    invoice_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get payment history for an invoice."""
    from app.services.client_billing_service import ClientBillingService
    
    try:
        invoice_uuid = UUID(invoice_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid invoice ID")
    
    service = ClientBillingService(db)
    payments = await service.get_payment_history(invoice_uuid)
    
    return {
        "invoice_id": invoice_id,
        "payments": [p.to_dict() for p in payments],
        "count": len(payments),
        "total_paid": sum(float(p.amount) for p in payments),
    }


# ==================== All Invoices ====================

@router.get("/invoices")
async def list_all_invoices(
    status: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List all invoices (across all clients)."""
    from app.services.client_billing_service import ClientBillingService
    
    service = ClientBillingService(db)
    
    invoices = await service.list_invoices(
        status=status,
        start_date=datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else None,
        end_date=datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else None,
    )
    
    return {
        "invoices": [i.to_dict() for i in invoices],
        "count": len(invoices),
    }


# ==================== Reference Data ====================

@router.get("/reference/fee-types")
async def get_fee_types():
    """Get available fee types."""
    from app.models.client_billing import FeeType
    
    return {
        "fee_types": [{"value": e.value, "name": e.name} for e in FeeType],
    }


@router.get("/reference/billable-types")
async def get_billable_types():
    """Get available billable item types."""
    from app.models.client_billing import BillableItemType
    
    return {
        "billable_types": [{"value": e.value, "name": e.name} for e in BillableItemType],
    }


@router.get("/reference/payment-methods")
async def get_payment_methods():
    """Get available payment methods."""
    from app.models.client_billing import PaymentMethod
    
    return {
        "payment_methods": [{"value": e.value, "name": e.name} for e in PaymentMethod],
    }

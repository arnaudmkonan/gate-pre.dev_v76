"""
Client Management API Routes.

CRUD operations for managing importer clients.

Task 4.1 & 4.2 from ROADMAP_FULL_WORKFLOW.md
"""
from typing import Optional, List
from uuid import UUID
from datetime import datetime, timezone, date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, EmailStr
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.client import (
    Client, ClientContact, ClientBond, ClientSettings,
    ClientStatus, ClientType, BondType, ContactType
)

router = APIRouter(prefix="/api/clients", tags=["Clients"])


# ==================== Request/Response Models ====================

class ClientCreate(BaseModel):
    """Create a new client."""
    name: str = Field(..., min_length=1, max_length=500)
    legal_name: Optional[str] = None
    dba_name: Optional[str] = None
    client_type: str = Field(default="corporation")
    
    # Identifiers
    ior_number: Optional[str] = None
    ein: Optional[str] = None
    duns: Optional[str] = None
    
    # Address
    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None
    city: Optional[str] = None
    state_province: Optional[str] = None
    postal_code: Optional[str] = None
    country: str = Field(default="US")
    
    # Contact
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    
    # Customs
    primary_port: Optional[str] = None
    
    # Compliance
    c_tpat_member: bool = False
    
    notes: Optional[str] = None
    internal_code: Optional[str] = None


class ClientUpdate(BaseModel):
    """Update client."""
    name: Optional[str] = None
    legal_name: Optional[str] = None
    dba_name: Optional[str] = None
    client_type: Optional[str] = None
    status: Optional[str] = None
    
    ior_number: Optional[str] = None
    ein: Optional[str] = None
    duns: Optional[str] = None
    cbp_assigned_number: Optional[str] = None
    
    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None
    city: Optional[str] = None
    state_province: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    
    phone: Optional[str] = None
    fax: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    
    primary_port: Optional[str] = None
    common_hts_chapters: Optional[List[str]] = None
    common_origin_countries: Optional[List[str]] = None
    
    c_tpat_member: Optional[bool] = None
    c_tpat_svi_number: Optional[str] = None
    trusted_trader: Optional[bool] = None
    known_importer: Optional[bool] = None
    ace_portal_account: Optional[str] = None
    
    credit_limit: Optional[float] = None
    payment_terms: Optional[str] = None
    billing_method: Optional[str] = None
    
    assigned_broker: Optional[str] = None
    notes: Optional[str] = None
    internal_code: Optional[str] = None
    preferences: Optional[dict] = None


class ContactCreate(BaseModel):
    """Create a client contact."""
    first_name: str
    last_name: str
    title: Optional[str] = None
    contact_type: str = Field(default="primary")
    is_primary: bool = False
    email: Optional[str] = None
    phone: Optional[str] = None
    mobile: Optional[str] = None
    receives_notifications: bool = True
    receives_status_updates: bool = True
    notes: Optional[str] = None


class BondCreate(BaseModel):
    """Create a client bond."""
    bond_type: str  # continuous, single_transaction, isf
    bond_number: str
    surety_code: str = Field(..., min_length=3, max_length=3)
    surety_name: Optional[str] = None
    bond_amount: Optional[float] = None
    coverage_start: Optional[date] = None
    coverage_end: Optional[date] = None
    is_active: bool = True
    notes: Optional[str] = None


class ClientSettingsUpdate(BaseModel):
    """Update client settings."""
    default_entry_type: Optional[str] = None
    default_port: Optional[str] = None
    require_approval_before_file: Optional[bool] = None
    auto_calculate_duties: Optional[bool] = None
    notify_on_entry_file: Optional[bool] = None
    notify_on_cbp_response: Optional[bool] = None
    notify_on_document_ready: Optional[bool] = None
    notify_on_duty_payment: Optional[bool] = None
    notification_emails: Optional[List[str]] = None
    store_document_copies: Optional[bool] = None
    document_retention_days: Optional[int] = None
    preferred_fta: Optional[str] = None
    binding_ruling_numbers: Optional[List[str]] = None
    invoice_delivery_method: Optional[str] = None
    consolidate_invoices: Optional[bool] = None
    custom_fields: Optional[dict] = None


# ==================== Client CRUD Endpoints ====================

@router.post("", status_code=201)
async def create_client(
    client_data: ClientCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new importer client.
    
    Required:
    - name: Company name
    
    Important fields:
    - ior_number: Importer of Record number (XX-XXXXXXX format)
    - ein: Employer ID Number
    """
    # Check for duplicate IOR/EIN
    if client_data.ior_number:
        existing = await db.execute(
            select(Client).where(Client.ior_number == client_data.ior_number)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="IOR number already exists")
    
    if client_data.ein:
        existing = await db.execute(
            select(Client).where(Client.ein == client_data.ein)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="EIN already exists")
    
    # Create client
    client = Client(
        name=client_data.name,
        legal_name=client_data.legal_name,
        dba_name=client_data.dba_name,
        client_type=client_data.client_type,
        status=ClientStatus.ONBOARDING.value,
        ior_number=client_data.ior_number,
        ein=client_data.ein,
        duns=client_data.duns,
        address_line_1=client_data.address_line_1,
        address_line_2=client_data.address_line_2,
        city=client_data.city,
        state_province=client_data.state_province,
        postal_code=client_data.postal_code,
        country=client_data.country,
        phone=client_data.phone,
        email=client_data.email,
        website=client_data.website,
        primary_port=client_data.primary_port,
        c_tpat_member=client_data.c_tpat_member,
        notes=client_data.notes,
        internal_code=client_data.internal_code,
        onboarding_date=date.today(),
    )
    
    db.add(client)
    await db.flush()  # Flush to generate client.id
    
    # Create default settings using the flushed client id
    settings = ClientSettings(client_id=client.id)
    db.add(settings)
    
    await db.commit()
    await db.refresh(client)
    
    return {
        "id": str(client.id),
        "name": client.name,
        "status": client.status,
        "ior_number": client.ior_number,
        "created_at": client.created_at.isoformat(),
    }


@router.get("")
async def list_clients(
    status: Optional[str] = Query(None, description="Filter by status"),
    search: Optional[str] = Query(None, description="Search by name, IOR, or EIN"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """
    List all clients with optional filtering.
    """
    query = select(Client)
    
    if status:
        query = query.where(Client.status == status)
    
    if search:
        search_term = f"%{search}%"
        query = query.where(
            or_(
                Client.name.ilike(search_term),
                Client.ior_number.ilike(search_term),
                Client.ein.ilike(search_term),
                Client.internal_code.ilike(search_term),
            )
        )
    
    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()
    
    # Get page
    query = query.order_by(Client.name).offset(offset).limit(limit)
    result = await db.execute(query)
    clients = result.scalars().all()
    
    return {
        "count": len(clients),
        "total": total,
        "offset": offset,
        "limit": limit,
        "clients": [
            {
                "id": str(c.id),
                "name": c.name,
                "display_name": c.display_name,
                "status": c.status,
                "client_type": c.client_type,
                "ior_number": c.ior_number,
                "ein": c.ein,
                "city": c.city,
                "state_province": c.state_province,
                "country": c.country,
                "primary_port": c.primary_port,
                "c_tpat_member": c.c_tpat_member,
                "internal_code": c.internal_code,
                "created_at": c.created_at.isoformat(),
            }
            for c in clients
        ],
    }


@router.get("/{client_id}")
async def get_client(
    client_id: str,
    include_contacts: bool = Query(True, description="Include contacts"),
    include_bonds: bool = Query(True, description="Include bonds"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get detailed client information.
    """
    try:
        client_uuid = UUID(client_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid client ID format")
    
    query = select(Client).where(Client.id == client_uuid)
    
    if include_contacts:
        query = query.options(selectinload(Client.contacts))
    if include_bonds:
        query = query.options(selectinload(Client.bonds))
    
    query = query.options(selectinload(Client.settings))
    
    result = await db.execute(query)
    client = result.scalar_one_or_none()
    
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    response = {
        "id": str(client.id),
        "name": client.name,
        "legal_name": client.legal_name,
        "dba_name": client.dba_name,
        "display_name": client.display_name,
        "client_type": client.client_type,
        "status": client.status,
        "identifiers": {
            "ior_number": client.ior_number,
            "ein": client.ein,
            "duns": client.duns,
            "cbp_assigned_number": client.cbp_assigned_number,
        },
        "address": {
            "line_1": client.address_line_1,
            "line_2": client.address_line_2,
            "city": client.city,
            "state_province": client.state_province,
            "postal_code": client.postal_code,
            "country": client.country,
            "full": client.full_address,
        },
        "contact_info": {
            "phone": client.phone,
            "fax": client.fax,
            "email": client.email,
            "website": client.website,
        },
        "customs": {
            "primary_port": client.primary_port,
            "common_hts_chapters": client.common_hts_chapters,
            "common_origin_countries": client.common_origin_countries,
            "ace_portal_account": client.ace_portal_account,
        },
        "compliance": {
            "c_tpat_member": client.c_tpat_member,
            "c_tpat_svi_number": client.c_tpat_svi_number,
            "trusted_trader": client.trusted_trader,
            "known_importer": client.known_importer,
        },
        "financial": {
            "credit_limit": float(client.credit_limit) if client.credit_limit else None,
            "payment_terms": client.payment_terms,
            "billing_method": client.billing_method,
        },
        "broker_relationship": {
            "assigned_broker": client.assigned_broker,
            "onboarding_date": client.onboarding_date.isoformat() if client.onboarding_date else None,
            "first_entry_date": client.first_entry_date.isoformat() if client.first_entry_date else None,
        },
        "notes": client.notes,
        "internal_code": client.internal_code,
        "preferences": client.preferences,
        "created_at": client.created_at.isoformat(),
        "updated_at": client.updated_at.isoformat() if client.updated_at else None,
    }
    
    # Include contacts
    if include_contacts and client.contacts:
        response["contacts"] = [
            {
                "id": str(c.id),
                "first_name": c.first_name,
                "last_name": c.last_name,
                "full_name": c.full_name,
                "title": c.title,
                "contact_type": c.contact_type,
                "is_primary": c.is_primary,
                "email": c.email,
                "phone": c.phone,
                "mobile": c.mobile,
            }
            for c in client.contacts
        ]
    
    # Include bonds
    if include_bonds and client.bonds:
        response["bonds"] = [
            {
                "id": str(b.id),
                "bond_type": b.bond_type,
                "bond_number": b.bond_number,
                "surety_code": b.surety_code,
                "surety_name": b.surety_name,
                "bond_amount": float(b.bond_amount) if b.bond_amount else None,
                "coverage_start": b.coverage_start.isoformat() if b.coverage_start else None,
                "coverage_end": b.coverage_end.isoformat() if b.coverage_end else None,
                "is_active": b.is_active,
                "is_expired": b.is_expired,
                "days_until_expiration": b.days_until_expiration,
            }
            for b in client.bonds
        ]
    
    # Include settings
    if client.settings:
        response["settings"] = {
            "default_entry_type": client.settings.default_entry_type,
            "default_port": client.settings.default_port,
            "require_approval_before_file": client.settings.require_approval_before_file,
            "auto_calculate_duties": client.settings.auto_calculate_duties,
            "notifications": {
                "on_entry_file": client.settings.notify_on_entry_file,
                "on_cbp_response": client.settings.notify_on_cbp_response,
                "on_document_ready": client.settings.notify_on_document_ready,
                "on_duty_payment": client.settings.notify_on_duty_payment,
                "emails": client.settings.notification_emails,
            },
            "preferred_fta": client.settings.preferred_fta,
            "invoice_delivery_method": client.settings.invoice_delivery_method,
        }
    
    return response


@router.patch("/{client_id}")
async def update_client(
    client_id: str,
    updates: ClientUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    Update client information.
    """
    try:
        client_uuid = UUID(client_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid client ID format")
    
    result = await db.execute(select(Client).where(Client.id == client_uuid))
    client = result.scalar_one_or_none()
    
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Update fields
    update_data = updates.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if hasattr(client, field):
            setattr(client, field, value)
    
    client.updated_at = datetime.now(timezone.utc)
    
    await db.commit()
    await db.refresh(client)
    
    return {
        "id": str(client.id),
        "name": client.name,
        "status": client.status,
        "updated_at": client.updated_at.isoformat(),
        "message": "Client updated successfully",
    }


@router.delete("/{client_id}")
async def delete_client(
    client_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a client (soft delete by setting status to terminated).
    """
    try:
        client_uuid = UUID(client_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid client ID format")
    
    result = await db.execute(select(Client).where(Client.id == client_uuid))
    client = result.scalar_one_or_none()
    
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Soft delete
    client.status = ClientStatus.TERMINATED.value
    client.updated_at = datetime.now(timezone.utc)
    
    await db.commit()
    
    return {"message": "Client terminated", "id": str(client.id)}


# ==================== Contact Endpoints ====================

@router.post("/{client_id}/contacts", status_code=201)
async def add_contact(
    client_id: str,
    contact_data: ContactCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Add a contact to a client.
    """
    try:
        client_uuid = UUID(client_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid client ID format")
    
    # Verify client exists
    result = await db.execute(select(Client).where(Client.id == client_uuid))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Client not found")
    
    contact = ClientContact(
        client_id=client_uuid,
        **contact_data.model_dump(),
    )
    
    db.add(contact)
    await db.commit()
    await db.refresh(contact)
    
    return {
        "id": str(contact.id),
        "full_name": contact.full_name,
        "email": contact.email,
        "contact_type": contact.contact_type,
    }


@router.get("/{client_id}/contacts")
async def list_contacts(
    client_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    List all contacts for a client.
    """
    try:
        client_uuid = UUID(client_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid client ID format")
    
    result = await db.execute(
        select(ClientContact)
        .where(ClientContact.client_id == client_uuid)
        .order_by(ClientContact.is_primary.desc(), ClientContact.last_name)
    )
    contacts = result.scalars().all()
    
    return {
        "count": len(contacts),
        "contacts": [
            {
                "id": str(c.id),
                "first_name": c.first_name,
                "last_name": c.last_name,
                "full_name": c.full_name,
                "title": c.title,
                "contact_type": c.contact_type,
                "is_primary": c.is_primary,
                "email": c.email,
                "phone": c.phone,
                "mobile": c.mobile,
                "receives_notifications": c.receives_notifications,
            }
            for c in contacts
        ],
    }


# ==================== Bond Endpoints ====================

@router.post("/{client_id}/bonds", status_code=201)
async def add_bond(
    client_id: str,
    bond_data: BondCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Add a customs bond to a client.
    """
    try:
        client_uuid = UUID(client_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid client ID format")
    
    # Verify client exists
    result = await db.execute(select(Client).where(Client.id == client_uuid))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Client not found")
    
    bond = ClientBond(
        client_id=client_uuid,
        **bond_data.model_dump(),
    )
    
    db.add(bond)
    await db.commit()
    await db.refresh(bond)
    
    return {
        "id": str(bond.id),
        "bond_type": bond.bond_type,
        "bond_number": bond.bond_number,
        "surety_code": bond.surety_code,
        "is_active": bond.is_active,
    }


@router.get("/{client_id}/bonds")
async def list_bonds(
    client_id: str,
    active_only: bool = Query(False, description="Show only active bonds"),
    db: AsyncSession = Depends(get_db),
):
    """
    List all bonds for a client.
    """
    try:
        client_uuid = UUID(client_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid client ID format")
    
    query = select(ClientBond).where(ClientBond.client_id == client_uuid)
    
    if active_only:
        query = query.where(ClientBond.is_active == True)
    
    result = await db.execute(query.order_by(ClientBond.is_active.desc()))
    bonds = result.scalars().all()
    
    return {
        "count": len(bonds),
        "bonds": [
            {
                "id": str(b.id),
                "bond_type": b.bond_type,
                "bond_number": b.bond_number,
                "surety_code": b.surety_code,
                "surety_name": b.surety_name,
                "bond_amount": float(b.bond_amount) if b.bond_amount else None,
                "coverage_start": b.coverage_start.isoformat() if b.coverage_start else None,
                "coverage_end": b.coverage_end.isoformat() if b.coverage_end else None,
                "is_active": b.is_active,
                "is_expired": b.is_expired,
                "days_until_expiration": b.days_until_expiration,
            }
            for b in bonds
        ],
        "warnings": [
            f"Bond {b.bond_number} expires in {b.days_until_expiration} days"
            for b in bonds
            if b.is_active and b.days_until_expiration is not None and 0 < b.days_until_expiration <= 30
        ],
    }


# ==================== Settings Endpoints ====================

@router.get("/{client_id}/settings")
async def get_settings(
    client_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get client settings.
    """
    try:
        client_uuid = UUID(client_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid client ID format")
    
    result = await db.execute(
        select(ClientSettings).where(ClientSettings.client_id == client_uuid)
    )
    settings = result.scalar_one_or_none()
    
    if not settings:
        raise HTTPException(status_code=404, detail="Client settings not found")
    
    return {
        "client_id": str(settings.client_id),
        "entry": {
            "default_entry_type": settings.default_entry_type,
            "default_port": settings.default_port,
            "require_approval_before_file": settings.require_approval_before_file,
            "auto_calculate_duties": settings.auto_calculate_duties,
        },
        "notifications": {
            "on_entry_file": settings.notify_on_entry_file,
            "on_cbp_response": settings.notify_on_cbp_response,
            "on_document_ready": settings.notify_on_document_ready,
            "on_duty_payment": settings.notify_on_duty_payment,
            "emails": settings.notification_emails,
        },
        "documents": {
            "store_copies": settings.store_document_copies,
            "retention_days": settings.document_retention_days,
        },
        "classification": {
            "preferred_fta": settings.preferred_fta,
            "binding_ruling_numbers": settings.binding_ruling_numbers,
        },
        "billing": {
            "invoice_delivery_method": settings.invoice_delivery_method,
            "consolidate_invoices": settings.consolidate_invoices,
        },
        "custom_fields": settings.custom_fields,
    }


@router.patch("/{client_id}/settings")
async def update_settings(
    client_id: str,
    updates: ClientSettingsUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    Update client settings.
    """
    try:
        client_uuid = UUID(client_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid client ID format")
    
    result = await db.execute(
        select(ClientSettings).where(ClientSettings.client_id == client_uuid)
    )
    settings = result.scalar_one_or_none()
    
    if not settings:
        # Create settings if they don't exist
        settings = ClientSettings(client_id=client_uuid)
        db.add(settings)
    
    update_data = updates.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if hasattr(settings, field):
            setattr(settings, field, value)
    
    await db.commit()
    
    return {"message": "Settings updated", "client_id": str(client_uuid)}


# ==================== Statistics Endpoint ====================

@router.get("/{client_id}/stats")
async def get_client_stats(
    client_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get statistics for a client's entries.
    """
    try:
        client_uuid = UUID(client_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid client ID format")
    
    # Verify client exists
    result = await db.execute(select(Client).where(Client.id == client_uuid))
    client = result.scalar_one_or_none()
    
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Get entry stats
    from app.models.entry import Entry
    
    # Total entries
    entry_count = (await db.execute(
        select(func.count()).select_from(Entry).where(Entry.client_id == client_uuid)
    )).scalar() or 0
    
    # Total value
    total_value = (await db.execute(
        select(func.sum(Entry.total_entered_value))
        .where(Entry.client_id == client_uuid)
    )).scalar() or 0
    
    # Total duties
    total_duties = (await db.execute(
        select(func.sum(Entry.total_amount_due))
        .where(Entry.client_id == client_uuid)
    )).scalar() or 0
    
    return {
        "client_id": str(client_uuid),
        "client_name": client.name,
        "statistics": {
            "total_entries": entry_count,
            "total_entered_value": float(total_value),
            "total_duties_paid": float(total_duties),
        },
    }

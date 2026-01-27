"""
Client Preferences API Routes.

Endpoints for managing client-specific document preferences.

Task 4.4 from ROADMAP_FULL_WORKFLOW.md
"""
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db


router = APIRouter(prefix="/api/clients", tags=["Client Preferences"])


# ==================== Request/Response Models ====================

class UpdatePreferencesRequest(BaseModel):
    """Update preferences request."""
    default_port_of_entry: Optional[str] = None
    default_entry_type: Optional[str] = None
    auto_apply_fta: Optional[bool] = None
    default_fta_program: Optional[str] = None
    default_payment_terms: Optional[str] = None
    billing_email: Optional[str] = None
    consolidate_invoices: Optional[bool] = None
    auto_calculate_duties: Optional[bool] = None
    auto_validate_entries: Optional[bool] = None
    default_transport_mode: Optional[str] = None
    default_carrier: Optional[str] = None
    preserve_document_naming: Optional[bool] = None
    auto_link_documents: Optional[bool] = None
    notify_on_acceptance: Optional[bool] = None
    notify_on_rejection: Optional[bool] = None
    notify_on_release: Optional[bool] = None
    notify_on_hold: Optional[bool] = None


class FTAPreferencesRequest(BaseModel):
    """FTA preferences request."""
    auto_apply: bool
    default_program: Optional[str] = None


class HTSAliasRequest(BaseModel):
    """HTS alias request."""
    client_code: str
    hts_code: str
    description: Optional[str] = None


# ==================== Endpoints ====================

@router.get("/{client_id}/preferences")
async def get_client_preferences(
    client_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get all preferences for a client."""
    from app.services.client_preferences_service import ClientPreferencesService
    
    try:
        client_uuid = UUID(client_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid client ID")
    
    service = ClientPreferencesService(db)
    prefs = await service.get_preferences(client_uuid)
    
    return {
        "client_id": client_id,
        "preferences": prefs,
    }


@router.patch("/{client_id}/preferences")
async def update_client_preferences(
    client_id: str,
    request: UpdatePreferencesRequest,
    db: AsyncSession = Depends(get_db),
):
    """Update client preferences."""
    from app.services.client_preferences_service import ClientPreferencesService
    
    try:
        client_uuid = UUID(client_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid client ID")
    
    service = ClientPreferencesService(db)
    prefs = await service.update_preferences(
        client_uuid,
        request.model_dump(exclude_none=True),
    )
    
    return {
        "client_id": client_id,
        "preferences": prefs,
        "message": "Preferences updated successfully",
    }


@router.put("/{client_id}/preferences/port")
async def set_default_port(
    client_id: str,
    port_code: str = Query(..., description="Port code (e.g., 2704 for Los Angeles)"),
    db: AsyncSession = Depends(get_db),
):
    """Set default port of entry for a client."""
    from app.services.client_preferences_service import ClientPreferencesService
    
    try:
        client_uuid = UUID(client_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid client ID")
    
    service = ClientPreferencesService(db)
    prefs = await service.set_default_port(client_uuid, port_code)
    
    return {
        "client_id": client_id,
        "default_port_of_entry": port_code,
        "message": f"Default port set to {port_code}",
    }


@router.put("/{client_id}/preferences/entry-type")
async def set_default_entry_type(
    client_id: str,
    entry_type: str = Query(..., description="Entry type (01, 11, 21, etc.)"),
    db: AsyncSession = Depends(get_db),
):
    """Set default entry type for a client."""
    from app.services.client_preferences_service import ClientPreferencesService
    
    try:
        client_uuid = UUID(client_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid client ID")
    
    service = ClientPreferencesService(db)
    prefs = await service.set_default_entry_type(client_uuid, entry_type)
    
    return {
        "client_id": client_id,
        "default_entry_type": entry_type,
        "message": f"Default entry type set to {entry_type}",
    }


@router.put("/{client_id}/preferences/fta")
async def set_fta_preferences(
    client_id: str,
    request: FTAPreferencesRequest,
    db: AsyncSession = Depends(get_db),
):
    """Set FTA (Free Trade Agreement) preferences."""
    from app.services.client_preferences_service import ClientPreferencesService
    
    try:
        client_uuid = UUID(client_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid client ID")
    
    service = ClientPreferencesService(db)
    prefs = await service.set_fta_preferences(
        client_uuid,
        request.auto_apply,
        request.default_program,
    )
    
    return {
        "client_id": client_id,
        "auto_apply_fta": request.auto_apply,
        "default_fta_program": request.default_program,
        "message": "FTA preferences updated",
    }


# ==================== HTS Alias Endpoints ====================

@router.get("/{client_id}/hts-aliases")
async def get_hts_aliases(
    client_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get all HTS code aliases for a client."""
    from app.services.client_preferences_service import ClientPreferencesService
    
    try:
        client_uuid = UUID(client_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid client ID")
    
    service = ClientPreferencesService(db)
    prefs = await service.get_preferences(client_uuid)
    aliases = prefs.get("hts_aliases", {})
    
    return {
        "client_id": client_id,
        "hts_aliases": aliases,
        "count": len(aliases),
    }


@router.post("/{client_id}/hts-aliases")
async def add_hts_alias(
    client_id: str,
    request: HTSAliasRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Add a client-specific HTS code alias.
    
    Maps client's product code to official HTS code.
    """
    from app.services.client_preferences_service import ClientPreferencesService
    
    try:
        client_uuid = UUID(client_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid client ID")
    
    service = ClientPreferencesService(db)
    prefs = await service.add_hts_alias(
        client_uuid,
        request.client_code,
        request.hts_code,
        request.description,
    )
    
    return {
        "client_id": client_id,
        "alias_added": {
            "client_code": request.client_code,
            "hts_code": request.hts_code,
        },
        "message": f"Mapped '{request.client_code}' to HTS {request.hts_code}",
    }


@router.delete("/{client_id}/hts-aliases/{client_code}")
async def remove_hts_alias(
    client_id: str,
    client_code: str,
    db: AsyncSession = Depends(get_db),
):
    """Remove a client-specific HTS code alias."""
    from app.services.client_preferences_service import ClientPreferencesService
    
    try:
        client_uuid = UUID(client_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid client ID")
    
    service = ClientPreferencesService(db)
    await service.remove_hts_alias(client_uuid, client_code)
    
    return {
        "message": f"Removed alias for '{client_code}'",
    }


@router.get("/{client_id}/hts-aliases/resolve")
async def resolve_hts_code(
    client_id: str,
    client_code: str = Query(..., description="Client's product code"),
    db: AsyncSession = Depends(get_db),
):
    """Resolve a client's product code to HTS code."""
    from app.services.client_preferences_service import ClientPreferencesService
    
    try:
        client_uuid = UUID(client_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid client ID")
    
    service = ClientPreferencesService(db)
    hts_code = await service.resolve_hts_code(client_uuid, client_code)
    
    if not hts_code:
        return {
            "client_code": client_code,
            "hts_code": None,
            "found": False,
            "message": f"No HTS alias found for '{client_code}'",
        }
    
    return {
        "client_code": client_code,
        "hts_code": hts_code,
        "found": True,
    }


# ==================== Apply Defaults ====================

@router.post("/{client_id}/apply-defaults")
async def apply_defaults_to_entry(
    client_id: str,
    entry_data: dict,
    db: AsyncSession = Depends(get_db),
):
    """
    Apply client's default preferences to entry data.
    
    Returns entry data with defaults filled in for empty fields.
    """
    from app.services.client_preferences_service import EntryDefaultsApplicator
    
    try:
        client_uuid = UUID(client_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid client ID")
    
    applicator = EntryDefaultsApplicator(db)
    result = await applicator.apply_to_entry(entry_data, client_uuid)
    
    return {
        "entry_data": result,
        "message": "Defaults applied",
    }

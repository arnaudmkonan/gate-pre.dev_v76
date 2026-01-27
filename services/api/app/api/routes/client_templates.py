"""
Client Template API Routes.

Endpoints for managing client-specific extraction templates.

Task 4.3 from ROADMAP_FULL_WORKFLOW.md
"""
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db


router = APIRouter(prefix="/api/clients", tags=["Client Templates"])


# ==================== Request/Response Models ====================

class TemplateFieldDefinition(BaseModel):
    """Field definition for a template."""
    field_name: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    field_type: str = "string"
    required: bool = False
    extraction_hints: Optional[List[str]] = None


class CreateClientTemplateRequest(BaseModel):
    """Create client template request."""
    name: str
    description: Optional[str] = None
    document_type: str
    template_type: str = "field_list"
    field_definitions: Optional[List[dict]] = None
    extraction_prompt: Optional[str] = None
    matching_keywords: Optional[List[str]] = None
    confidence_threshold: float = 0.7


class UpdateClientTemplateRequest(BaseModel):
    """Update client template request."""
    name: Optional[str] = None
    description: Optional[str] = None
    field_definitions: Optional[List[dict]] = None
    extraction_prompt: Optional[str] = None
    matching_keywords: Optional[List[str]] = None
    confidence_threshold: Optional[float] = None
    is_active: Optional[bool] = None


class FieldMappingRequest(BaseModel):
    """Field mapping request."""
    client_field_name: str
    standard_field_name: str
    description: Optional[str] = None


class FieldAliasRequest(BaseModel):
    """Field alias request."""
    client_term: str
    standard_term: str


# ==================== Endpoints ====================

@router.get("/{client_id}/templates")
async def list_client_templates(
    client_id: str,
    db: AsyncSession = Depends(get_db),
):
    """List all extraction templates for a client."""
    from app.services.client_template_service import ClientTemplateService
    
    try:
        client_uuid = UUID(client_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid client ID")
    
    service = ClientTemplateService(db)
    templates = await service.list_client_templates(client_uuid)
    
    return {
        "client_id": client_id,
        "templates": [t.to_dict() for t in templates],
        "count": len(templates),
    }


@router.post("/{client_id}/templates")
async def create_client_template(
    client_id: str,
    request: CreateClientTemplateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a new extraction template for a client."""
    from app.services.client_template_service import ClientTemplateService
    
    try:
        client_uuid = UUID(client_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid client ID")
    
    service = ClientTemplateService(db)
    
    try:
        template = await service.create_client_template(
            client_uuid,
            request.model_dump(exclude_none=True),
        )
        
        return {
            "template": template.to_dict(),
            "message": "Template created successfully",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{client_id}/templates/from-global/{template_id}")
async def assign_global_template(
    client_id: str,
    template_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Assign a global template to a client.
    
    Creates a client-specific copy of the global template.
    """
    from app.services.client_template_service import ClientTemplateService
    
    try:
        client_uuid = UUID(client_id)
        template_uuid = UUID(template_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ID format")
    
    service = ClientTemplateService(db)
    
    try:
        template = await service.assign_template_to_client(template_uuid, client_uuid)
        
        return {
            "template": template.to_dict(),
            "message": "Global template assigned to client",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{client_id}/templates/{template_id}")
async def get_client_template(
    client_id: str,
    template_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific client template."""
    from sqlalchemy import select
    from app.models.extraction_template import ExtractionTemplate
    
    try:
        template_uuid = UUID(template_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid template ID")
    
    query = select(ExtractionTemplate).where(ExtractionTemplate.id == template_uuid)
    result = await db.execute(query)
    template = result.scalar_one_or_none()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    return template.to_dict()


@router.put("/{client_id}/templates/{template_id}")
async def update_client_template(
    client_id: str,
    template_id: str,
    request: UpdateClientTemplateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Update a client-specific template."""
    from app.services.client_template_service import ClientTemplateService
    
    try:
        template_uuid = UUID(template_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid template ID")
    
    service = ClientTemplateService(db)
    
    try:
        template = await service.update_client_template(
            template_uuid,
            request.model_dump(exclude_none=True),
        )
        
        return {
            "template": template.to_dict(),
            "message": "Template updated successfully",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{client_id}/templates/{template_id}")
async def delete_client_template(
    client_id: str,
    template_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete (deactivate) a client-specific template."""
    from app.services.client_template_service import ClientTemplateService
    
    try:
        template_uuid = UUID(template_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid template ID")
    
    service = ClientTemplateService(db)
    
    try:
        await service.delete_client_template(template_uuid)
        
        return {
            "message": "Template deleted successfully",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==================== Field Mapping Endpoints ====================

@router.post("/{client_id}/templates/{template_id}/field-mappings")
async def add_field_mapping(
    client_id: str,
    template_id: str,
    request: FieldMappingRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Add a field mapping to a client template.
    
    Maps client's terminology to standard field names.
    E.g., Client calls it "PO Number", we map to "purchase_order_number"
    """
    from app.services.client_template_service import ClientTemplateService
    
    try:
        template_uuid = UUID(template_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid template ID")
    
    service = ClientTemplateService(db)
    
    try:
        template = await service.add_field_mapping(
            template_uuid,
            request.client_field_name,
            request.standard_field_name,
            request.description,
        )
        
        return {
            "template": template.to_dict(),
            "message": f"Mapped '{request.client_field_name}' to '{request.standard_field_name}'",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{client_id}/templates/{template_id}/field-mappings")
async def get_field_mappings(
    client_id: str,
    template_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get all field mappings for a template."""
    from app.services.client_template_service import ClientTemplateService
    
    try:
        template_uuid = UUID(template_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid template ID")
    
    service = ClientTemplateService(db)
    mappings = await service.get_field_mappings(template_uuid)
    
    return {
        "template_id": template_id,
        "mappings": mappings,
        "count": len(mappings),
    }


# ==================== Field Alias Endpoints ====================

@router.get("/{client_id}/field-aliases")
async def get_field_aliases(
    client_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get all field aliases for a client."""
    from app.services.client_template_service import ClientFieldAliasService
    
    try:
        client_uuid = UUID(client_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid client ID")
    
    service = ClientFieldAliasService(db)
    aliases = await service.get_client_aliases(client_uuid)
    
    return {
        "client_id": client_id,
        "aliases": aliases,
        "count": len(aliases),
    }


@router.post("/{client_id}/field-aliases")
async def set_field_alias(
    client_id: str,
    request: FieldAliasRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Set a field alias for a client.
    
    Translates client terminology to standard terminology.
    """
    from app.services.client_template_service import ClientFieldAliasService
    
    try:
        client_uuid = UUID(client_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid client ID")
    
    service = ClientFieldAliasService(db)
    await service.set_field_alias(client_uuid, request.client_term, request.standard_term)
    
    return {
        "message": f"Set alias: '{request.client_term}' -> '{request.standard_term}'",
    }


@router.get("/{client_id}/field-aliases/translate")
async def translate_field(
    client_id: str,
    term: str = Query(..., description="Term to translate"),
    direction: str = Query("to_standard", description="'to_standard' or 'to_client'"),
    db: AsyncSession = Depends(get_db),
):
    """Translate a field name between client and standard terminology."""
    from app.services.client_template_service import ClientFieldAliasService
    
    try:
        client_uuid = UUID(client_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid client ID")
    
    service = ClientFieldAliasService(db)
    
    if direction == "to_standard":
        result = await service.translate_field_name(client_uuid, term)
    else:
        result = await service.translate_to_client_term(client_uuid, term)
    
    return {
        "input": term,
        "output": result,
        "direction": direction,
    }


# ==================== Template Resolution ====================

@router.get("/{client_id}/resolve-template")
async def resolve_template_for_document(
    client_id: str,
    document_type: str = Query(..., description="Document type"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the best template for a document and client.
    
    Priority:
    1. Client-specific template
    2. Global template
    """
    from app.services.client_template_service import ClientTemplateService
    
    try:
        client_uuid = UUID(client_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid client ID")
    
    service = ClientTemplateService(db)
    template = await service.get_template_for_client_document(client_uuid, document_type)
    
    if not template:
        return {
            "template": None,
            "source": None,
            "message": f"No template found for document type '{document_type}'",
        }
    
    is_client_specific = template.customer_id and template.customer_id == str(client_uuid)
    
    return {
        "template": template.to_dict(),
        "source": "client" if is_client_specific else "global",
        "message": f"Using {'client-specific' if is_client_specific else 'global'} template",
    }


# ==================== Global Templates (for reference) ====================

@router.get("/global-templates")
async def list_global_templates(
    db: AsyncSession = Depends(get_db),
):
    """List all global (non-client-specific) templates."""
    from app.services.client_template_service import ClientTemplateService
    
    service = ClientTemplateService(db)
    templates = await service.list_global_templates()
    
    return {
        "templates": [t.to_dict() for t in templates],
        "count": len(templates),
    }

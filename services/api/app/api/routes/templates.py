"""
Templates API Routes.

Endpoints for managing extraction templates.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.template_service import TemplateService

router = APIRouter(prefix="/api/templates", tags=["templates"])


# Request/Response Models
class FieldDefinition(BaseModel):
    field_name: str
    display_name: Optional[str] = None
    field_type: str = "string"  # string, number, date, money, entity
    description: Optional[str] = None
    required: bool = False
    validation_regex: Optional[str] = None
    extraction_hints: Optional[List[str]] = None
    default_value: Optional[str] = None
    entity_type: Optional[str] = None  # For entity extraction: person, organization, etc.


class CreateTemplateRequest(BaseModel):
    name: str
    document_type: str
    field_definitions: List[FieldDefinition]
    template_type: str = "field_list"
    description: Optional[str] = None
    customer_id: Optional[str] = None
    extraction_prompt: Optional[str] = None
    few_shot_examples: Optional[List[dict]] = None
    matching_keywords: Optional[List[str]] = None
    classification_categories: Optional[List[str]] = None
    confidence_threshold: float = 0.7
    source_document_id: Optional[str] = None
    visual_regions: Optional[List[dict]] = None


class UpdateTemplateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    field_definitions: Optional[List[FieldDefinition]] = None
    extraction_prompt: Optional[str] = None
    few_shot_examples: Optional[List[dict]] = None
    matching_keywords: Optional[List[str]] = None
    classification_categories: Optional[List[str]] = None
    confidence_threshold: Optional[float] = None
    is_active: Optional[bool] = None
    visual_regions: Optional[List[dict]] = None


class GenerateFromDocumentRequest(BaseModel):
    document_id: str
    name: str
    field_hints: Optional[List[FieldDefinition]] = None
    customer_id: Optional[str] = None


class CloneTemplateRequest(BaseModel):
    new_name: str
    customer_id: Optional[str] = None


class TemplateResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    document_type: str
    customer_id: Optional[str]
    version: int
    is_active: bool
    template_type: str
    source_document_id: Optional[str]
    field_definitions: List[dict]
    field_count: int
    visual_regions: Optional[List[dict]]
    extraction_prompt: Optional[str]
    few_shot_examples: Optional[List[dict]]
    matching_keywords: Optional[List[str]]
    classification_categories: Optional[List[str]]
    confidence_threshold: float
    usage_count: int
    last_used_at: Optional[str]
    avg_confidence: Optional[float]
    created_at: Optional[str]
    updated_at: Optional[str]


class TemplateMatchResponse(BaseModel):
    template_id: str
    template_name: str
    document_type: str
    confidence: float
    match_reasons: List[str]
    field_count: int


# Routes
@router.get("", response_model=List[TemplateResponse])
async def list_templates(
    document_type: Optional[str] = None,
    customer_id: Optional[str] = None,
    is_active: Optional[bool] = True,
    template_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_db)
):
    """
    List extraction templates with optional filters.
    """
    templates = await TemplateService.list_templates(
        session=session,
        document_type=document_type,
        customer_id=customer_id,
        is_active=is_active,
        template_type=template_type,
        limit=limit,
        offset=offset
    )
    return [t.to_dict() for t in templates]


@router.post("", response_model=TemplateResponse)
async def create_template(
    request: CreateTemplateRequest,
    session: AsyncSession = Depends(get_db)
):
    """
    Create a new extraction template.
    """
    template = await TemplateService.create_template(
        session=session,
        name=request.name,
        document_type=request.document_type,
        field_definitions=[f.model_dump() for f in request.field_definitions],
        template_type=request.template_type,
        description=request.description,
        customer_id=request.customer_id,
        extraction_prompt=request.extraction_prompt,
        few_shot_examples=request.few_shot_examples,
        matching_keywords=request.matching_keywords,
        classification_categories=request.classification_categories,
        confidence_threshold=request.confidence_threshold,
        source_document_id=request.source_document_id,
        visual_regions=request.visual_regions,
    )
    return template.to_dict()


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: str,
    session: AsyncSession = Depends(get_db)
):
    """
    Get a template by ID.
    """
    template = await TemplateService.get_template(session, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template.to_dict()


@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: str,
    request: UpdateTemplateRequest,
    session: AsyncSession = Depends(get_db)
):
    """
    Update a template.
    """
    updates = request.model_dump(exclude_unset=True)
    if "field_definitions" in updates and updates["field_definitions"]:
        updates["field_definitions"] = [f.model_dump() if hasattr(f, 'model_dump') else f for f in updates["field_definitions"]]

    template = await TemplateService.update_template(
        session=session,
        template_id=template_id,
        **updates
    )
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template.to_dict()


@router.delete("/{template_id}")
async def delete_template(
    template_id: str,
    hard_delete: bool = False,
    session: AsyncSession = Depends(get_db)
):
    """
    Delete a template (soft delete by default).
    """
    success = await TemplateService.delete_template(
        session=session,
        template_id=template_id,
        soft_delete=not hard_delete
    )
    if not success:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"status": "deleted", "template_id": template_id}


@router.post("/{template_id}/clone", response_model=TemplateResponse)
async def clone_template(
    template_id: str,
    request: CloneTemplateRequest,
    session: AsyncSession = Depends(get_db)
):
    """
    Clone a template for customization.
    """
    template = await TemplateService.clone_template(
        session=session,
        template_id=template_id,
        new_name=request.new_name,
        customer_id=request.customer_id
    )
    if not template:
        raise HTTPException(status_code=404, detail="Original template not found")
    return template.to_dict()


@router.post("/from-document", response_model=TemplateResponse)
async def generate_from_document(
    request: GenerateFromDocumentRequest,
    session: AsyncSession = Depends(get_db)
):
    """
    Generate a template from a sample document.
    """
    field_hints = None
    if request.field_hints:
        field_hints = [f.model_dump() for f in request.field_hints]

    template = await TemplateService.generate_template_from_sample(
        session=session,
        document_id=request.document_id,
        name=request.name,
        field_hints=field_hints,
        customer_id=request.customer_id
    )
    if not template:
        raise HTTPException(status_code=404, detail="Document not found")
    return template.to_dict()


@router.get("/match/{document_id}", response_model=List[TemplateMatchResponse])
async def match_templates(
    document_id: str,
    classification: Optional[str] = None,
    customer_id: Optional[str] = None,
    session: AsyncSession = Depends(get_db)
):
    """
    Find templates that match a document.
    """
    matches = await TemplateService.match_template(
        session=session,
        document_id=document_id,
        classification=classification,
        customer_id=customer_id
    )
    return matches


@router.post("/{template_id}/test")
async def test_template(
    template_id: str,
    document_id: str,
    session: AsyncSession = Depends(get_db)
):
    """
    Test template extraction on a document.

    This is a placeholder - actual extraction would use the template agents.
    """
    template = await TemplateService.get_template(session, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # For now, return template info and note that extraction would happen
    return {
        "template_id": template_id,
        "document_id": document_id,
        "template_name": template.name,
        "field_count": len(template.field_definitions) if template.field_definitions else 0,
        "status": "test_pending",
        "message": "Template extraction test would run using TemplateExtractionAgent"
    }


# ============================================
# Template Seeding Endpoints (Admin)
# ============================================

class SeedTemplatesRequest(BaseModel):
    force_update: bool = False
    document_types: Optional[List[str]] = None


class AvailableTemplateInfo(BaseModel):
    document_type: str
    name: str
    description: Optional[str]
    field_count: int
    version: str
    has_prompt: bool


class SeedResult(BaseModel):
    seeded_count: int
    templates: List[dict]


class TemplateStatsResponse(BaseModel):
    total_templates: int
    active_templates: int
    available_on_disk: int
    usage_by_template: List[dict]


@router.get("/admin/available", response_model=List[AvailableTemplateInfo])
async def list_available_templates():
    """
    List predefined templates available for seeding.
    
    Returns templates defined on disk that can be seeded into the database.
    """
    from app.services.template_loader_service import TemplateLoaderService
    
    templates = TemplateLoaderService.list_available_templates()
    return templates


@router.post("/admin/seed", response_model=SeedResult)
async def seed_templates(
    request: SeedTemplatesRequest,
    session: AsyncSession = Depends(get_db)
):
    """
    Seed predefined document type templates into the database.
    
    Loads the complete set of Customs Brokerage workflow templates:
    
    **Setup Phase:**
    - Power of Attorney (POA)
    - Customs Bond
    
    **Pre-Loading Phase:**
    - Commercial Invoice
    - ISF Filing (10+2)
    - Purchase Order
    
    **In Transit Phase:**
    - Arrival Notice
    - Bill of Lading
    - Packing List
    
    **Arrival/Clearance Phase:**
    - Entry Manifest (CBP 3461)
    - Customs Entry (CBP 7501)
    
    **Final Delivery Phase:**
    - Delivery Order
    - Broker Invoice (Billing of Services)
    
    Use force_update=true to update existing templates with latest definitions.
    """
    from app.services.template_loader_service import TemplateLoaderService, DOCUMENT_TYPES
    
    doc_types = request.document_types or DOCUMENT_TYPES
    
    # Validate document types
    invalid = [dt for dt in doc_types if dt not in DOCUMENT_TYPES]
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid document types: {invalid}. Available: {DOCUMENT_TYPES}"
        )
    
    results = {}
    for doc_type in doc_types:
        template = await TemplateLoaderService.seed_template(
            session, doc_type, request.force_update
        )
        if template:
            results[doc_type] = template
    
    return {
        "seeded_count": len(results),
        "templates": [
            {
                "document_type": dtype,
                "template_id": str(t.id),
                "name": t.name,
                "field_count": len(t.field_definitions) if t.field_definitions else 0,
                "version": t.version,
            }
            for dtype, t in results.items()
        ]
    }


@router.get("/admin/stats", response_model=TemplateStatsResponse)
async def get_template_stats(
    session: AsyncSession = Depends(get_db)
):
    """
    Get template usage statistics.
    """
    from app.services.template_loader_service import TemplateLoaderService
    
    stats = await TemplateLoaderService.get_template_stats(session)
    return stats


@router.get("/admin/schema/{document_type}")
async def get_template_schema(document_type: str):
    """
    Get the raw schema definition for a template type.
    
    Useful for inspecting field definitions before seeding.
    """
    from app.services.template_loader_service import TemplateLoaderService
    
    schema = TemplateLoaderService.load_template_schema(document_type)
    if not schema:
        raise HTTPException(
            status_code=404,
            detail=f"Template schema not found: {document_type}"
        )
    
    prompt = TemplateLoaderService.load_template_prompt(document_type)
    
    return {
        "schema": schema,
        "has_prompt": prompt is not None,
        "prompt_preview": prompt[:500] + "..." if prompt and len(prompt) > 500 else prompt,
    }


@router.post("/admin/validate/{document_type}")
async def validate_template_schema(document_type: str):
    """
    Validate a template schema definition.
    
    Checks for required fields, field name uniqueness, and valid configuration.
    """
    from app.services.template_loader_service import TemplateLoaderService
    
    schema = TemplateLoaderService.load_template_schema(document_type)
    if not schema:
        raise HTTPException(
            status_code=404,
            detail=f"Template schema not found: {document_type}"
        )
    
    errors = TemplateLoaderService.validate_template_schema(schema)
    
    return {
        "document_type": document_type,
        "valid": len(errors) == 0,
        "errors": errors,
        "field_count": len(schema.get("field_definitions", [])),
    }

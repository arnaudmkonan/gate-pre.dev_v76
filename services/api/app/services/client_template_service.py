"""
Client-Specific Template Service.

Manages client-specific extraction templates:
- Assign templates to specific clients
- Client templates take priority over global
- Per-client field mappings/aliases
- Fall back to global templates if no client match

Task 4.3 from ROADMAP_FULL_WORKFLOW.md
"""
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.extraction_template import ExtractionTemplate
from app.models.client import Client


class ClientTemplateService:
    """Service for managing client-specific extraction templates."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def assign_template_to_client(
        self,
        template_id: UUID,
        client_id: UUID,
    ) -> ExtractionTemplate:
        """
        Assign a global template to a specific client.
        
        This creates a copy of the template with the client_id set.
        """
        # Get the original template
        query = select(ExtractionTemplate).where(ExtractionTemplate.id == template_id)
        result = await self.db.execute(query)
        template = result.scalar_one_or_none()
        
        if not template:
            raise ValueError(f"Template {template_id} not found")
        
        # Check if client exists
        client_query = select(Client).where(Client.id == client_id)
        client_result = await self.db.execute(client_query)
        client = client_result.scalar_one_or_none()
        
        if not client:
            raise ValueError(f"Client {client_id} not found")
        
        # Check if client already has this template for this document type
        existing = await self.get_client_template(client_id, template.document_type)
        if existing:
            raise ValueError(
                f"Client already has a template for document type '{template.document_type}'. "
                f"Update the existing template or remove it first."
            )
        
        # Create a copy for the client
        client_template = ExtractionTemplate(
            name=f"{template.name} - {client.name}",
            description=template.description,
            document_type=template.document_type,
            customer_id=str(client_id),  # Link to client
            version=1,
            is_active=True,
            template_type=template.template_type,
            source_document_id=template.source_document_id,
            field_definitions=template.field_definitions,
            visual_regions=template.visual_regions,
            extraction_prompt=template.extraction_prompt,
            few_shot_examples=template.few_shot_examples,
            matching_keywords=template.matching_keywords,
            classification_categories=template.classification_categories,
            confidence_threshold=template.confidence_threshold,
        )
        
        self.db.add(client_template)
        await self.db.commit()
        await self.db.refresh(client_template)
        
        return client_template
    
    async def create_client_template(
        self,
        client_id: UUID,
        data: Dict[str, Any],
    ) -> ExtractionTemplate:
        """Create a new template specifically for a client."""
        # Verify client exists
        client_query = select(Client).where(Client.id == client_id)
        client_result = await self.db.execute(client_query)
        client = client_result.scalar_one_or_none()
        
        if not client:
            raise ValueError(f"Client {client_id} not found")
        
        # Create template with client_id
        template = ExtractionTemplate(
            name=data.get("name", "Client Template"),
            description=data.get("description"),
            document_type=data.get("document_type", "general"),
            customer_id=str(client_id),
            version=1,
            is_active=True,
            template_type=data.get("template_type", "field_list"),
            field_definitions=data.get("field_definitions", []),
            visual_regions=data.get("visual_regions"),
            extraction_prompt=data.get("extraction_prompt"),
            few_shot_examples=data.get("few_shot_examples"),
            matching_keywords=data.get("matching_keywords"),
            classification_categories=data.get("classification_categories"),
            confidence_threshold=data.get("confidence_threshold", 0.7),
        )
        
        self.db.add(template)
        await self.db.commit()
        await self.db.refresh(template)
        
        return template
    
    async def get_client_template(
        self,
        client_id: UUID,
        document_type: str,
    ) -> Optional[ExtractionTemplate]:
        """Get client-specific template for a document type."""
        query = select(ExtractionTemplate).where(
            and_(
                ExtractionTemplate.customer_id == str(client_id),
                ExtractionTemplate.document_type == document_type,
                ExtractionTemplate.is_active == True
            )
        ).order_by(ExtractionTemplate.version.desc())
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_template_for_client_document(
        self,
        client_id: Optional[UUID],
        document_type: str,
    ) -> Optional[ExtractionTemplate]:
        """
        Get the best template for a document.
        
        Priority:
        1. Client-specific template for this document type
        2. Global template for this document type
        """
        # First try client-specific
        if client_id:
            client_template = await self.get_client_template(client_id, document_type)
            if client_template:
                return client_template
        
        # Fall back to global (customer_id is null)
        query = select(ExtractionTemplate).where(
            and_(
                or_(
                    ExtractionTemplate.customer_id == None,
                    ExtractionTemplate.customer_id == ""
                ),
                ExtractionTemplate.document_type == document_type,
                ExtractionTemplate.is_active == True
            )
        ).order_by(ExtractionTemplate.version.desc())
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def list_client_templates(
        self,
        client_id: UUID,
    ) -> List[ExtractionTemplate]:
        """List all templates for a client."""
        query = select(ExtractionTemplate).where(
            and_(
                ExtractionTemplate.customer_id == str(client_id),
                ExtractionTemplate.is_active == True
            )
        ).order_by(ExtractionTemplate.document_type)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def list_global_templates(self) -> List[ExtractionTemplate]:
        """List all global (non-client-specific) templates."""
        query = select(ExtractionTemplate).where(
            and_(
                or_(
                    ExtractionTemplate.customer_id == None,
                    ExtractionTemplate.customer_id == ""
                ),
                ExtractionTemplate.is_active == True
            )
        ).order_by(ExtractionTemplate.document_type)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def update_client_template(
        self,
        template_id: UUID,
        data: Dict[str, Any],
    ) -> ExtractionTemplate:
        """Update a client-specific template."""
        query = select(ExtractionTemplate).where(ExtractionTemplate.id == template_id)
        result = await self.db.execute(query)
        template = result.scalar_one_or_none()
        
        if not template:
            raise ValueError(f"Template {template_id} not found")
        
        # Update fields
        updatable_fields = [
            'name', 'description', 'field_definitions', 'visual_regions',
            'extraction_prompt', 'few_shot_examples', 'matching_keywords',
            'classification_categories', 'confidence_threshold', 'is_active'
        ]
        
        for field in updatable_fields:
            if field in data:
                setattr(template, field, data[field])
        
        # Increment version
        template.version = (template.version or 0) + 1
        
        await self.db.commit()
        await self.db.refresh(template)
        
        return template
    
    async def delete_client_template(self, template_id: UUID):
        """Delete (deactivate) a client-specific template."""
        query = select(ExtractionTemplate).where(ExtractionTemplate.id == template_id)
        result = await self.db.execute(query)
        template = result.scalar_one_or_none()
        
        if not template:
            raise ValueError(f"Template {template_id} not found")
        
        # Soft delete
        template.is_active = False
        
        await self.db.commit()
    
    async def add_field_mapping(
        self,
        template_id: UUID,
        client_field_name: str,
        standard_field_name: str,
        description: Optional[str] = None,
    ) -> ExtractionTemplate:
        """
        Add a field mapping to a client template.
        
        Used when clients call fields by different names.
        E.g., Client A: "PO Number" -> standard: "purchase_order_number"
        """
        query = select(ExtractionTemplate).where(ExtractionTemplate.id == template_id)
        result = await self.db.execute(query)
        template = result.scalar_one_or_none()
        
        if not template:
            raise ValueError(f"Template {template_id} not found")
        
        # Get or create field definitions
        field_defs = list(template.field_definitions or [])
        
        # Add the mapping as a field with alias
        new_field = {
            "field_name": standard_field_name,
            "display_name": client_field_name,
            "description": description or f"Mapped from client field: {client_field_name}",
            "field_type": "string",
            "required": False,
            "extraction_hints": [f"Client calls this: {client_field_name}"],
        }
        
        # Check if field already exists
        existing_idx = next(
            (i for i, f in enumerate(field_defs) if f.get("field_name") == standard_field_name),
            None
        )
        
        if existing_idx is not None:
            # Update existing
            field_defs[existing_idx]["display_name"] = client_field_name
            field_defs[existing_idx]["extraction_hints"] = [f"Client calls this: {client_field_name}"]
        else:
            # Add new
            field_defs.append(new_field)
        
        template.field_definitions = field_defs
        
        await self.db.commit()
        await self.db.refresh(template)
        
        return template
    
    async def get_field_mappings(self, template_id: UUID) -> List[Dict[str, str]]:
        """Get all field mappings for a template."""
        query = select(ExtractionTemplate).where(ExtractionTemplate.id == template_id)
        result = await self.db.execute(query)
        template = result.scalar_one_or_none()
        
        if not template:
            return []
        
        mappings = []
        for field in (template.field_definitions or []):
            if field.get("display_name") != field.get("field_name"):
                mappings.append({
                    "client_field": field.get("display_name"),
                    "standard_field": field.get("field_name"),
                    "description": field.get("description"),
                })
        
        return mappings


# ==================== Client Field Alias Model ====================

class ClientFieldAliasService:
    """
    Service for managing client-specific field aliases.
    
    Allows clients to use their own terminology for fields.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_client_aliases(self, client_id: UUID) -> Dict[str, str]:
        """Get all field aliases for a client."""
        from app.models.client import ClientSettings
        
        query = select(ClientSettings).where(ClientSettings.client_id == client_id)
        result = await self.db.execute(query)
        settings = result.scalar_one_or_none()
        
        if not settings or not settings.custom_fields:
            return {}
        
        return settings.custom_fields.get("field_aliases", {})
    
    async def set_field_alias(
        self,
        client_id: UUID,
        client_term: str,
        standard_term: str,
    ):
        """Set a field alias for a client."""
        from app.models.client import ClientSettings
        
        query = select(ClientSettings).where(ClientSettings.client_id == client_id)
        result = await self.db.execute(query)
        settings = result.scalar_one_or_none()
        
        if not settings:
            # Create settings
            settings = ClientSettings(
                client_id=client_id,
                custom_fields={"field_aliases": {client_term: standard_term}},
            )
            self.db.add(settings)
        else:
            # Update
            custom_fields = dict(settings.custom_fields or {})
            aliases = custom_fields.get("field_aliases", {})
            aliases[client_term] = standard_term
            custom_fields["field_aliases"] = aliases
            settings.custom_fields = custom_fields
        
        await self.db.commit()
    
    async def translate_field_name(
        self,
        client_id: UUID,
        client_term: str,
    ) -> str:
        """Translate a client's term to the standard field name."""
        aliases = await self.get_client_aliases(client_id)
        return aliases.get(client_term, client_term)
    
    async def translate_to_client_term(
        self,
        client_id: UUID,
        standard_term: str,
    ) -> str:
        """Translate a standard field name to client's term."""
        aliases = await self.get_client_aliases(client_id)
        
        # Reverse lookup
        for client_term, std_term in aliases.items():
            if std_term == standard_term:
                return client_term
        
        return standard_term

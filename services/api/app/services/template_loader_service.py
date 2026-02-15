"""
Template Loader Service.

Loads predefined document type templates from the templates directory
into the database for use in document extraction workflows.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.extraction_template import ExtractionTemplate

logger = logging.getLogger(__name__)

# Base path for template definitions
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

# Document types to load - Complete Customs Brokerage Workflow
# Phase: Setup
DOCUMENT_TYPES = [
    "power-of-attorney",     # POA - Importer authorizes broker
    "customs-bond",          # Bond - Required for importing
    # Phase: Pre-Loading
    "commercial-invoice",    # Commercial Invoice from seller
    "isf-filing",           # ISF 10+2 for ocean freight
    "purchase-order",        # Purchase Order reference
    # Phase: In Transit
    "arrival-notice",        # Arrival Notice from carrier
    "bill-of-lading",        # BOL - Transport document
    "packing-list",          # Packing List
    # Phase: Arrival/Clearance
    "entry-manifest",        # CBP 3461 - Immediate Delivery
    "customs-entry",         # CBP 7501 - Entry Summary
    # Phase: Final Delivery
    "delivery-order",        # Delivery Order - Cargo release
    "broker-invoice",        # Broker Invoice - Billing of Services
]


class TemplateLoaderService:
    """
    Service for loading predefined document templates into the database.
    
    Templates are defined as JSON schema files in the templates directory
    and can be seeded into the database for use in extraction workflows.
    """
    
    @staticmethod
    def get_template_path(doc_type: str) -> Path:
        """Get the path to a template's schema file."""
        return TEMPLATES_DIR / doc_type / "schema.json"
    
    @staticmethod
    def get_prompt_path(doc_type: str) -> Path:
        """Get the path to a template's prompt file."""
        return TEMPLATES_DIR / doc_type / "prompts.txt"
    
    @staticmethod
    def load_template_schema(doc_type: str) -> Optional[Dict]:
        """
        Load a template schema from disk.
        
        Args:
            doc_type: Document type name (e.g., 'commercial-invoice')
            
        Returns:
            Template schema dict or None if not found
        """
        schema_path = TemplateLoaderService.get_template_path(doc_type)
        
        if not schema_path.exists():
            logger.warning(f"Template schema not found: {schema_path}")
            return None
        
        try:
            with open(schema_path, "r") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in template {doc_type}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error loading template {doc_type}: {e}")
            return None
    
    @staticmethod
    def load_template_prompt(doc_type: str) -> Optional[str]:
        """
        Load a template's extraction prompt from disk.
        
        Args:
            doc_type: Document type name
            
        Returns:
            Prompt text or None if not found
        """
        prompt_path = TemplateLoaderService.get_prompt_path(doc_type)
        
        if not prompt_path.exists():
            return None
        
        try:
            with open(prompt_path, "r") as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error loading prompt for {doc_type}: {e}")
            return None
    
    @staticmethod
    async def seed_template(
        session: AsyncSession,
        doc_type: str,
        force_update: bool = False,
    ) -> Optional[ExtractionTemplate]:
        """
        Seed a single template into the database.
        
        Args:
            session: Database session
            doc_type: Document type to seed
            force_update: If True, update existing templates
            
        Returns:
            Created or updated ExtractionTemplate
        """
        schema = TemplateLoaderService.load_template_schema(doc_type)
        if not schema:
            logger.warning(f"Skipping template {doc_type}: schema not found")
            return None
        
        prompt = TemplateLoaderService.load_template_prompt(doc_type)
        
        # Check if template already exists
        existing = await session.execute(
            select(ExtractionTemplate).where(
                ExtractionTemplate.document_type == schema.get("document_type")
            )
        )
        existing_template = existing.scalar_one_or_none()
        
        if existing_template:
            if not force_update:
                logger.info(f"Template {doc_type} already exists, skipping")
                return existing_template
            
            # Update existing template
            existing_template.name = schema.get("template_name")
            existing_template.description = schema.get("description")
            existing_template.template_type = schema.get("template_type", "field_list")
            existing_template.field_definitions = schema.get("field_definitions", [])
            existing_template.matching_keywords = schema.get("matching_keywords", [])
            existing_template.classification_categories = schema.get("classification_categories", [])
            existing_template.confidence_threshold = schema.get("confidence_threshold", 0.75)
            existing_template.extraction_prompt = prompt
            existing_template.version += 1
            
            await session.commit()
            await session.refresh(existing_template)
            
            logger.info(f"Updated template: {doc_type} (v{existing_template.version})")
            return existing_template
        
        # Create new template
        template = ExtractionTemplate(
            name=schema.get("template_name"),
            description=schema.get("description"),
            document_type=schema.get("document_type"),
            template_type=schema.get("template_type", "field_list"),
            field_definitions=schema.get("field_definitions", []),
            matching_keywords=schema.get("matching_keywords", []),
            classification_categories=schema.get("classification_categories", []),
            confidence_threshold=schema.get("confidence_threshold", 0.75),
            extraction_prompt=prompt,
            is_active=True,
            version=1,
        )
        
        session.add(template)
        await session.commit()
        await session.refresh(template)
        
        logger.info(f"Created template: {doc_type} (ID: {template.id})")
        return template
    
    @staticmethod
    async def seed_all_templates(
        session: AsyncSession,
        force_update: bool = False,
    ) -> Dict[str, ExtractionTemplate]:
        """
        Seed all predefined templates into the database.
        
        Args:
            session: Database session
            force_update: If True, update existing templates
            
        Returns:
            Dict mapping document type to ExtractionTemplate
        """
        results = {}
        
        for doc_type in DOCUMENT_TYPES:
            template = await TemplateLoaderService.seed_template(
                session, doc_type, force_update
            )
            if template:
                results[doc_type] = template
        
        logger.info(f"Seeded {len(results)} templates")
        return results
    
    @staticmethod
    def list_available_templates() -> List[Dict]:
        """
        List all template definitions available on disk.
        
        Returns:
            List of template info dicts
        """
        templates = []
        
        for doc_type in DOCUMENT_TYPES:
            schema = TemplateLoaderService.load_template_schema(doc_type)
            if schema:
                templates.append({
                    "document_type": doc_type,
                    "name": schema.get("template_name"),
                    "description": schema.get("description"),
                    "field_count": len(schema.get("field_definitions", [])),
                    "version": schema.get("version", "1.0.0"),
                    "has_prompt": TemplateLoaderService.get_prompt_path(doc_type).exists(),
                })
        
        return templates
    
    @staticmethod
    async def get_template_stats(session: AsyncSession) -> Dict:
        """
        Get statistics about templates in the database.
        
        Args:
            session: Database session
            
        Returns:
            Stats dict with counts and usage info
        """
        from sqlalchemy import func
        
        # Get total count
        total_result = await session.execute(
            select(func.count(ExtractionTemplate.id))
        )
        total_count = total_result.scalar() or 0
        
        # Get active count
        active_result = await session.execute(
            select(func.count(ExtractionTemplate.id)).where(
                ExtractionTemplate.is_active == True
            )
        )
        active_count = active_result.scalar() or 0
        
        # Get usage stats
        usage_result = await session.execute(
            select(
                ExtractionTemplate.document_type,
                ExtractionTemplate.name,
                ExtractionTemplate.usage_count,
                ExtractionTemplate.avg_confidence,
            ).order_by(ExtractionTemplate.usage_count.desc())
        )
        usage_stats = [
            {
                "document_type": row.document_type,
                "name": row.name,
                "usage_count": row.usage_count,
                "avg_confidence": row.avg_confidence,
            }
            for row in usage_result
        ]
        
        return {
            "total_templates": total_count,
            "active_templates": active_count,
            "available_on_disk": len(DOCUMENT_TYPES),
            "usage_by_template": usage_stats,
        }
    
    @staticmethod
    def validate_template_schema(schema: Dict) -> List[str]:
        """
        Validate a template schema definition.
        
        Args:
            schema: Template schema dict
            
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        # Required fields
        if not schema.get("template_name"):
            errors.append("Missing required field: template_name")
        if not schema.get("document_type"):
            errors.append("Missing required field: document_type")
        if not schema.get("field_definitions"):
            errors.append("Missing required field: field_definitions")
        
        # Validate field definitions
        field_defs = schema.get("field_definitions", [])
        if not isinstance(field_defs, list):
            errors.append("field_definitions must be an array")
        else:
            field_names = set()
            for i, field in enumerate(field_defs):
                if not field.get("field_name"):
                    errors.append(f"Field {i}: missing field_name")
                elif field["field_name"] in field_names:
                    errors.append(f"Field {i}: duplicate field_name '{field['field_name']}'")
                else:
                    field_names.add(field["field_name"])
                
                if not field.get("field_type"):
                    errors.append(f"Field {i}: missing field_type")
        
        # Validate confidence threshold
        threshold = schema.get("confidence_threshold")
        if threshold is not None:
            if not isinstance(threshold, (int, float)) or threshold < 0 or threshold > 1:
                errors.append("confidence_threshold must be a number between 0 and 1")
        
        return errors

"""
Template Service.

Manages extraction templates for guided field extraction from documents.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.extraction_template import ExtractionTemplate
from app.models.document_metadata import DocumentMetadata

logger = logging.getLogger(__name__)


class TemplateService:
    """
    Service for managing extraction templates.
    """

    @staticmethod
    async def create_template(
        session: AsyncSession,
        name: str,
        document_type: str,
        field_definitions: List[Dict],
        template_type: str = "field_list",
        description: Optional[str] = None,
        customer_id: Optional[str] = None,
        extraction_prompt: Optional[str] = None,
        few_shot_examples: Optional[List[Dict]] = None,
        matching_keywords: Optional[List[str]] = None,
        classification_categories: Optional[List[str]] = None,
        confidence_threshold: float = 0.7,
        source_document_id: Optional[str] = None,
        visual_regions: Optional[List[Dict]] = None,
    ) -> ExtractionTemplate:
        """
        Create a new extraction template.
        """
        template = ExtractionTemplate(
            name=name,
            description=description,
            document_type=document_type,
            customer_id=customer_id,
            template_type=template_type,
            source_document_id=UUID(source_document_id) if source_document_id else None,
            field_definitions=field_definitions,
            visual_regions=visual_regions,
            extraction_prompt=extraction_prompt,
            few_shot_examples=few_shot_examples,
            matching_keywords=matching_keywords,
            classification_categories=classification_categories,
            confidence_threshold=confidence_threshold,
        )

        session.add(template)
        await session.commit()
        await session.refresh(template)

        logger.info(f"Created template '{name}' for document type '{document_type}'")
        return template

    @staticmethod
    async def get_template(
        session: AsyncSession,
        template_id: str
    ) -> Optional[ExtractionTemplate]:
        """
        Get a template by ID.
        """
        template_uuid = UUID(template_id)
        result = await session.execute(
            select(ExtractionTemplate).where(ExtractionTemplate.id == template_uuid)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_templates(
        session: AsyncSession,
        document_type: Optional[str] = None,
        customer_id: Optional[str] = None,
        is_active: Optional[bool] = True,
        template_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[ExtractionTemplate]:
        """
        List templates with optional filters.
        """
        query = select(ExtractionTemplate)

        conditions = []
        if document_type:
            conditions.append(ExtractionTemplate.document_type == document_type)
        if customer_id:
            # Include customer-specific and global templates
            conditions.append(
                or_(
                    ExtractionTemplate.customer_id == customer_id,
                    ExtractionTemplate.customer_id.is_(None)
                )
            )
        if is_active is not None:
            conditions.append(ExtractionTemplate.is_active == is_active)
        if template_type:
            conditions.append(ExtractionTemplate.template_type == template_type)

        if conditions:
            query = query.where(and_(*conditions))

        query = query.order_by(
            ExtractionTemplate.usage_count.desc(),
            ExtractionTemplate.created_at.desc()
        ).limit(limit).offset(offset)

        result = await session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def update_template(
        session: AsyncSession,
        template_id: str,
        **updates
    ) -> Optional[ExtractionTemplate]:
        """
        Update a template.
        """
        template = await TemplateService.get_template(session, template_id)
        if not template:
            return None

        for key, value in updates.items():
            if hasattr(template, key) and value is not None:
                setattr(template, key, value)

        # Increment version on significant changes
        if any(k in updates for k in ["field_definitions", "extraction_prompt", "visual_regions"]):
            template.version += 1

        await session.commit()
        await session.refresh(template)

        logger.info(f"Updated template {template_id}")
        return template

    @staticmethod
    async def delete_template(
        session: AsyncSession,
        template_id: str,
        soft_delete: bool = True
    ) -> bool:
        """
        Delete a template (soft delete by default).
        """
        template = await TemplateService.get_template(session, template_id)
        if not template:
            return False

        if soft_delete:
            template.is_active = False
            await session.commit()
        else:
            await session.delete(template)
            await session.commit()

        logger.info(f"Deleted template {template_id} (soft={soft_delete})")
        return True

    @staticmethod
    async def match_template(
        session: AsyncSession,
        document_id: str,
        classification: Optional[str] = None,
        customer_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Find templates that match a document based on classification and keywords.

        Returns list of matches with confidence scores.
        """
        doc_uuid = UUID(document_id)

        # Get document
        doc_result = await session.execute(
            select(DocumentMetadata).where(DocumentMetadata.id == doc_uuid)
        )
        doc = doc_result.scalar_one_or_none()

        if not doc:
            return []

        # Get content for keyword matching
        content = (doc.extracted_text_snippet or "").lower()

        # Build query for potential templates
        query = select(ExtractionTemplate).where(
            ExtractionTemplate.is_active == True
        )

        # Filter by customer (include global templates)
        if customer_id:
            query = query.where(
                or_(
                    ExtractionTemplate.customer_id == customer_id,
                    ExtractionTemplate.customer_id.is_(None)
                )
            )

        result = await session.execute(query)
        templates = result.scalars().all()

        matches = []
        for template in templates:
            score = 0.0
            reasons = []

            # Check classification match
            if classification and template.classification_categories:
                if classification.lower() in [c.lower() for c in template.classification_categories]:
                    score += 0.5
                    reasons.append(f"Classification match: {classification}")

            # Check document type match
            if template.document_type:
                doc_type = doc.file_type or ""
                if template.document_type.lower() in doc_type.lower():
                    score += 0.2
                    reasons.append(f"Document type match: {template.document_type}")

            # Check keyword match
            if template.matching_keywords and content:
                keyword_matches = sum(
                    1 for kw in template.matching_keywords
                    if kw.lower() in content
                )
                if keyword_matches > 0:
                    keyword_score = min(0.3, keyword_matches * 0.1)
                    score += keyword_score
                    reasons.append(f"Keyword matches: {keyword_matches}")

            # Only include templates with some match
            if score > 0:
                matches.append({
                    "template_id": str(template.id),
                    "template_name": template.name,
                    "document_type": template.document_type,
                    "confidence": min(1.0, score),
                    "match_reasons": reasons,
                    "field_count": len(template.field_definitions) if template.field_definitions else 0,
                })

        # Sort by confidence
        matches.sort(key=lambda x: x["confidence"], reverse=True)

        return matches

    @staticmethod
    async def record_template_usage(
        session: AsyncSession,
        template_id: str,
        extraction_confidence: Optional[float] = None
    ):
        """
        Record that a template was used and update statistics.
        """
        template = await TemplateService.get_template(session, template_id)
        if not template:
            return

        template.usage_count += 1
        template.last_used_at = datetime.now(timezone.utc)

        # Update rolling average confidence
        if extraction_confidence is not None:
            if template.avg_confidence is None:
                template.avg_confidence = extraction_confidence
            else:
                # Exponential moving average
                alpha = 0.1
                template.avg_confidence = (
                    alpha * extraction_confidence +
                    (1 - alpha) * template.avg_confidence
                )

        await session.commit()

    @staticmethod
    async def clone_template(
        session: AsyncSession,
        template_id: str,
        new_name: str,
        customer_id: Optional[str] = None
    ) -> Optional[ExtractionTemplate]:
        """
        Clone a template for customization.
        """
        original = await TemplateService.get_template(session, template_id)
        if not original:
            return None

        clone = ExtractionTemplate(
            name=new_name,
            description=f"Cloned from {original.name}",
            document_type=original.document_type,
            customer_id=customer_id or original.customer_id,
            template_type=original.template_type,
            field_definitions=original.field_definitions.copy() if original.field_definitions else [],
            visual_regions=original.visual_regions.copy() if original.visual_regions else None,
            extraction_prompt=original.extraction_prompt,
            few_shot_examples=original.few_shot_examples.copy() if original.few_shot_examples else None,
            matching_keywords=original.matching_keywords.copy() if original.matching_keywords else None,
            classification_categories=original.classification_categories.copy() if original.classification_categories else None,
            confidence_threshold=original.confidence_threshold,
        )

        session.add(clone)
        await session.commit()
        await session.refresh(clone)

        logger.info(f"Cloned template {template_id} to {clone.id}")
        return clone

    @staticmethod
    async def generate_template_from_sample(
        session: AsyncSession,
        document_id: str,
        name: str,
        field_hints: Optional[List[Dict]] = None,
        customer_id: Optional[str] = None
    ) -> Optional[ExtractionTemplate]:
        """
        Generate a template from a sample document.

        This is a placeholder for AI-assisted template generation.
        In production, this would analyze the document and suggest fields.
        """
        doc_uuid = UUID(document_id)

        # Get document
        doc_result = await session.execute(
            select(DocumentMetadata).where(DocumentMetadata.id == doc_uuid)
        )
        doc = doc_result.scalar_one_or_none()

        if not doc:
            return None

        # For now, create template with provided hints or empty fields
        field_definitions = field_hints or []

        template = ExtractionTemplate(
            name=name,
            description=f"Generated from sample: {doc.filename}",
            document_type=doc.file_type or "unknown",
            customer_id=customer_id,
            template_type="field_list",
            source_document_id=doc_uuid,
            field_definitions=field_definitions,
        )

        session.add(template)
        await session.commit()
        await session.refresh(template)

        logger.info(f"Generated template from sample document {document_id}")
        return template

    # ===== Sync versions for Celery worker context =====

    @staticmethod
    def get_template_sync(session, template_id: str) -> Optional[ExtractionTemplate]:
        """
        Get a template by ID (sync version for Celery workers).
        """
        from sqlalchemy.orm import Session
        template_uuid = UUID(template_id)
        result = session.execute(
            select(ExtractionTemplate).where(ExtractionTemplate.id == template_uuid)
        )
        return result.scalar_one_or_none()

    @staticmethod
    def match_template_sync(
        session,
        document_id: str,
        classification: Optional[str] = None,
        customer_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Find templates that match a document (sync version for Celery workers).
        """
        doc_uuid = UUID(document_id)

        # Get document
        doc_result = session.execute(
            select(DocumentMetadata).where(DocumentMetadata.id == doc_uuid)
        )
        doc = doc_result.scalar_one_or_none()

        if not doc:
            return []

        # Get content for keyword matching
        content = (doc.extracted_text_snippet or "").lower()

        # Build query for potential templates
        query = select(ExtractionTemplate).where(
            ExtractionTemplate.is_active == True
        )

        # Filter by customer (include global templates)
        if customer_id:
            query = query.where(
                or_(
                    ExtractionTemplate.customer_id == customer_id,
                    ExtractionTemplate.customer_id.is_(None)
                )
            )

        result = session.execute(query)
        templates = result.scalars().all()

        matches = []
        for template in templates:
            score = 0.0
            reasons = []

            # Check classification match
            if classification and template.classification_categories:
                if classification.lower() in [c.lower() for c in template.classification_categories]:
                    score += 0.5
                    reasons.append(f"Classification match: {classification}")

            # Check document type match
            if template.document_type:
                if classification and classification.lower() == template.document_type.lower():
                    score += 0.3
                    reasons.append(f"Document type match: {template.document_type}")

            # Check keyword matches
            if template.matching_keywords:
                keyword_matches = [kw for kw in template.matching_keywords if kw.lower() in content]
                if keyword_matches:
                    keyword_score = min(len(keyword_matches) * 0.1, 0.4)
                    score += keyword_score
                    reasons.append(f"Keyword matches: {', '.join(keyword_matches[:3])}")

            # Only include if there's some match
            if score > 0:
                matches.append({
                    "template_id": str(template.id),
                    "template_name": template.name,
                    "document_type": template.document_type,
                    "confidence": min(score, 1.0),
                    "reasons": reasons,
                    "field_count": len(template.field_definitions) if template.field_definitions else 0,
                })

        # Sort by confidence
        matches.sort(key=lambda x: x["confidence"], reverse=True)
        return matches

    @staticmethod
    def record_template_usage_sync(
        session,
        template_id: str,
        extraction_confidence: Optional[float] = None
    ):
        """
        Record that a template was used (sync version for Celery workers).
        """
        template = TemplateService.get_template_sync(session, template_id)
        if not template:
            return

        template.usage_count += 1
        template.last_used_at = datetime.now(timezone.utc)

        # Update rolling average confidence
        if extraction_confidence is not None:
            if template.avg_confidence is None:
                template.avg_confidence = extraction_confidence
            else:
                # Exponential moving average
                alpha = 0.1
                template.avg_confidence = (
                    alpha * extraction_confidence +
                    (1 - alpha) * template.avg_confidence
                )

        session.commit()

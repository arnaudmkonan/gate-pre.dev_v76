"""
Review Service.

Manages the human-in-the-loop review workflow for document extractions.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document_metadata import DocumentMetadata
from app.models.extraction_result import ExtractionResult
from app.models.review_queue import ReviewQueueItem, ReviewAction

logger = logging.getLogger(__name__)


# Confidence thresholds for routing
CONFIDENCE_AUTO_APPROVE = 0.95  # Auto-approve above this
CONFIDENCE_REVIEW_THRESHOLD = 0.70  # Require review below this
CONFIDENCE_REJECT_THRESHOLD = 0.50  # Auto-reject below this


class ReviewService:
    """
    Service for managing the review queue and workflow.
    """
    
    @staticmethod
    async def add_to_review_queue(
        session: AsyncSession,
        document_id: str,
        reason: str,
        reason_code: str = "low_confidence",
        confidence_score: float = 0.0,
        priority: int = 0,
        agent_results: Optional[Dict] = None,
        issues_detected: Optional[List[Dict]] = None
    ) -> ReviewQueueItem:
        """
        Add a document to the review queue.
        """
        doc_uuid = UUID(document_id)
        
        # Check if already in queue
        existing = await session.execute(
            select(ReviewQueueItem).where(
                and_(
                    ReviewQueueItem.document_id == doc_uuid,
                    ReviewQueueItem.status.in_(["pending", "in_review"])
                )
            )
        )
        if existing.scalar_one_or_none():
            logger.info(f"Document {document_id} already in review queue")
            return existing.scalar_one()
        
        # Calculate priority based on confidence and other factors
        if priority == 0:
            # Auto-calculate priority
            if confidence_score < 0.6:
                priority = 3  # High priority for very low confidence
            elif confidence_score < 0.8:
                priority = 2  # Medium priority
            else:
                priority = 1  # Low priority
        
        item = ReviewQueueItem(
            document_id=doc_uuid,
            reason=reason,
            reason_code=reason_code,
            confidence_score=confidence_score,
            priority=priority,
            agent_results=agent_results,
            issues_detected=issues_detected,
            status="pending",
        )
        
        session.add(item)
        await session.commit()
        await session.refresh(item)
        
        logger.info(f"Added document {document_id} to review queue with priority {priority}")
        return item
    
    @staticmethod
    async def get_review_queue(
        session: AsyncSession,
        status: Optional[str] = None,
        assigned_to: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get items from the review queue with document details.
        """
        query = select(ReviewQueueItem).order_by(
            ReviewQueueItem.priority.desc(),
            ReviewQueueItem.created_at.asc()
        )
        
        if status:
            query = query.where(ReviewQueueItem.status == status)
        else:
            # Default: show pending and in_review
            query = query.where(ReviewQueueItem.status.in_(["pending", "in_review"]))
        
        if assigned_to:
            query = query.where(ReviewQueueItem.assigned_to == assigned_to)
        
        query = query.limit(limit).offset(offset)
        
        result = await session.execute(query)
        items = result.scalars().all()
        
        # Enrich with document details
        enriched = []
        for item in items:
            doc_result = await session.execute(
                select(DocumentMetadata).where(DocumentMetadata.id == item.document_id)
            )
            doc = doc_result.scalar_one_or_none()
            
            item_dict = item.to_dict()
            if doc:
                item_dict["document"] = {
                    "filename": doc.filename,
                    "file_type": doc.file_type,
                    "size": doc.size,
                    "ingestion_status": doc.ingestion_status,
                }
            enriched.append(item_dict)
        
        return enriched
    
    @staticmethod
    async def get_review_item_detail(
        session: AsyncSession,
        item_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get detailed view of a review item with all extractions.
        """
        item_uuid = UUID(item_id)
        
        # Get review item
        result = await session.execute(
            select(ReviewQueueItem).where(ReviewQueueItem.id == item_uuid)
        )
        item = result.scalar_one_or_none()
        
        if not item:
            return None
        
        # Get document
        doc_result = await session.execute(
            select(DocumentMetadata).where(DocumentMetadata.id == item.document_id)
        )
        doc = doc_result.scalar_one_or_none()
        
        # Get extraction results
        ext_result = await session.execute(
            select(ExtractionResult).where(
                ExtractionResult.document_id == item.document_id
            ).order_by(ExtractionResult.confidence.desc())
        )
        extractions = ext_result.scalars().all()
        
        # Get review history
        history_result = await session.execute(
            select(ReviewAction).where(
                ReviewAction.review_item_id == item_uuid
            ).order_by(ReviewAction.created_at.desc())
        )
        history = history_result.scalars().all()
        
        return {
            "review_item": item.to_dict(),
            "document": {
                "id": str(doc.id),
                "filename": doc.filename,
                "file_type": doc.file_type,
                "size": doc.size,
                "extracted_text_snippet": doc.extracted_text_snippet,
                "ingestion_status": doc.ingestion_status,
                "page_count": doc.page_count,
                "mime_type": doc.mime_type,
                "title": doc.title,
                "author": doc.author,
            } if doc else None,
            "extractions": [e.to_dict() for e in extractions],
            "extraction_count": len(extractions),
            "low_confidence_count": len([e for e in extractions if e.confidence < 0.9]),
            "history": [h.to_dict() for h in history],
        }
    
    @staticmethod
    async def assign_item(
        session: AsyncSession,
        item_id: str,
        reviewer: str
    ) -> ReviewQueueItem:
        """
        Assign a review item to a reviewer.
        """
        item_uuid = UUID(item_id)
        
        result = await session.execute(
            select(ReviewQueueItem).where(ReviewQueueItem.id == item_uuid)
        )
        item = result.scalar_one_or_none()
        
        if not item:
            raise ValueError(f"Review item {item_id} not found")
        
        item.assigned_to = reviewer
        item.assigned_at = datetime.now(timezone.utc)
        item.status = "in_review"
        
        # Log action
        action = ReviewAction(
            review_item_id=item_uuid,
            action="assign",
            actor=reviewer,
            notes=f"Assigned to {reviewer}",
        )
        session.add(action)
        
        await session.commit()
        await session.refresh(item)
        
        return item
    
    @staticmethod
    async def approve_item(
        session: AsyncSession,
        item_id: str,
        reviewer: str,
        notes: Optional[str] = None
    ) -> ReviewQueueItem:
        """
        Approve an item (extractions are correct).
        """
        item_uuid = UUID(item_id)
        
        result = await session.execute(
            select(ReviewQueueItem).where(ReviewQueueItem.id == item_uuid)
        )
        item = result.scalar_one_or_none()
        
        if not item:
            raise ValueError(f"Review item {item_id} not found")
        
        # Calculate review time
        review_time = None
        if item.assigned_at:
            review_time = int((datetime.now(timezone.utc) - item.assigned_at).total_seconds())
        
        item.status = "approved"
        item.reviewed_at = datetime.now(timezone.utc)
        item.reviewed_by = reviewer
        item.review_notes = notes
        item.time_to_review_seconds = review_time
        
        # Update all extractions to reviewed status
        await session.execute(
            update(ExtractionResult)
            .where(ExtractionResult.document_id == item.document_id)
            .values(
                status="reviewed",
                reviewed_by=reviewer,
                reviewed_at=datetime.now(timezone.utc)
            )
        )
        
        # Log action
        action = ReviewAction(
            review_item_id=item_uuid,
            action="approve",
            actor=reviewer,
            notes=notes,
        )
        session.add(action)

        await session.commit()
        await session.refresh(item)

        # Process for feedback learning (async, don't wait)
        try:
            from app.services.feedback_service import FeedbackService
            await FeedbackService.process_approved_review(session, item_id)
            logger.info(f"Processed feedback for approved review {item_id}")
        except Exception as e:
            logger.warning(f"Failed to process feedback for {item_id}: {e}")

        return item

    @staticmethod
    async def reject_item(
        session: AsyncSession,
        item_id: str,
        reviewer: str,
        reason: str
    ) -> ReviewQueueItem:
        """
        Reject an item (extractions are too poor to use).
        """
        item_uuid = UUID(item_id)
        
        result = await session.execute(
            select(ReviewQueueItem).where(ReviewQueueItem.id == item_uuid)
        )
        item = result.scalar_one_or_none()
        
        if not item:
            raise ValueError(f"Review item {item_id} not found")
        
        item.status = "rejected"
        item.reviewed_at = datetime.now(timezone.utc)
        item.reviewed_by = reviewer
        item.review_notes = reason
        
        # Update extractions to rejected
        await session.execute(
            update(ExtractionResult)
            .where(ExtractionResult.document_id == item.document_id)
            .values(status="rejected")
        )
        
        # Log action
        action = ReviewAction(
            review_item_id=item_uuid,
            action="reject",
            actor=reviewer,
            notes=reason,
        )
        session.add(action)
        
        await session.commit()
        await session.refresh(item)
        
        return item
    
    @staticmethod
    async def correct_extraction(
        session: AsyncSession,
        item_id: str,
        extraction_id: str,
        corrected_value: Any,
        reviewer: str,
        notes: Optional[str] = None
    ) -> ExtractionResult:
        """
        Correct a specific extraction field.
        """
        ext_uuid = UUID(extraction_id)
        item_uuid = UUID(item_id)
        
        result = await session.execute(
            select(ExtractionResult).where(ExtractionResult.id == ext_uuid)
        )
        extraction = result.scalar_one_or_none()
        
        if not extraction:
            raise ValueError(f"Extraction {extraction_id} not found")
        
        # Store correction
        old_value = extraction.field_value
        extraction.correction_value = corrected_value
        extraction.correction_notes = notes
        extraction.status = "corrected"
        extraction.reviewed_by = reviewer
        extraction.reviewed_at = datetime.now(timezone.utc)
        
        # Log action
        action = ReviewAction(
            review_item_id=item_uuid,
            action="correct",
            actor=reviewer,
            field_corrections={
                "extraction_id": str(extraction_id),
                "field_name": extraction.field_name,
                "old_value": old_value,
                "new_value": corrected_value,
            },
            notes=notes,
        )
        session.add(action)

        await session.commit()
        await session.refresh(extraction)

        # Log correction for feedback learning
        try:
            from app.services.feedback_service import FeedbackService

            # Get template ID from agent_name if available
            template_id = None
            if extraction.agent_name and extraction.agent_name.startswith("template:"):
                parts = extraction.agent_name.split(":")
                if len(parts) >= 3:
                    template_id = parts[2]

            await FeedbackService.log_correction(
                session=session,
                review_item_id=item_id,
                extraction_id=extraction_id,
                field_name=extraction.field_name,
                original_value=old_value,
                corrected_value=corrected_value,
                reviewer=reviewer,
                original_confidence=extraction.confidence,
                document_snippet=extraction.context_snippet,
                review_notes=notes,
                template_id=template_id,
                document_id=str(extraction.document_id),
            )
            logger.info(f"Logged correction for extraction {extraction_id}")
        except Exception as e:
            logger.warning(f"Failed to log correction for {extraction_id}: {e}")

        return extraction
    
    @staticmethod
    async def get_review_stats(
        session: AsyncSession,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        Get review queue statistics.
        """
        from datetime import timedelta
        
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        # Count by status
        status_counts = {}
        for status in ["pending", "in_review", "approved", "rejected", "skipped"]:
            result = await session.execute(
                select(func.count(ReviewQueueItem.id)).where(
                    ReviewQueueItem.status == status
                )
            )
            status_counts[status] = result.scalar() or 0
        
        # Recent reviews
        result = await session.execute(
            select(func.count(ReviewQueueItem.id)).where(
                and_(
                    ReviewQueueItem.reviewed_at >= cutoff,
                    ReviewQueueItem.status.in_(["approved", "rejected"])
                )
            )
        )
        reviews_last_period = result.scalar() or 0
        
        # Average review time
        result = await session.execute(
            select(func.avg(ReviewQueueItem.time_to_review_seconds)).where(
                ReviewQueueItem.time_to_review_seconds.isnot(None)
            )
        )
        avg_review_time = result.scalar() or 0
        
        # Approval rate
        total_reviewed = status_counts.get("approved", 0) + status_counts.get("rejected", 0)
        approval_rate = (
            status_counts.get("approved", 0) / total_reviewed
            if total_reviewed > 0 else 0
        )
        
        return {
            "queue_counts": status_counts,
            "pending_count": status_counts.get("pending", 0),
            "reviews_last_period": reviews_last_period,
            "avg_review_time_seconds": round(avg_review_time, 1),
            "approval_rate": round(approval_rate * 100, 1),
            "period_days": days,
        }
    
    @staticmethod
    def should_require_review(
        confidence: float,
        issues: Optional[List] = None
    ) -> tuple[bool, str]:
        """
        Determine if a document should require human review.
        
        Returns:
            (should_review, reason)
        """
        if confidence < CONFIDENCE_REJECT_THRESHOLD:
            return True, "Confidence too low for automated processing"
        
        if confidence < CONFIDENCE_REVIEW_THRESHOLD:
            return True, f"Extraction confidence ({confidence:.0%}) below threshold"
        
        if issues and len(issues) > 0:
            high_severity = [i for i in issues if i.get("severity") in ["high", "critical"]]
            if high_severity:
                return True, f"Quality issues detected: {len(high_severity)} high-severity"
        
        if confidence >= CONFIDENCE_AUTO_APPROVE:
            return False, "Auto-approved (high confidence)"
        
        return True, "Moderate confidence - review recommended"

    # ===== Sync versions for Celery worker context =====

    @staticmethod
    def add_to_review_queue_sync(
        session,
        document_id: str,
        reason: str,
        reason_code: str = "low_confidence",
        confidence_score: float = 0.0,
        priority: int = 0,
        agent_results: Optional[Dict] = None,
        issues_detected: Optional[List[Dict]] = None
    ) -> ReviewQueueItem:
        """
        Add a document to the review queue (sync version for Celery workers).
        """
        doc_uuid = UUID(document_id)

        # Check if already in queue
        existing = session.execute(
            select(ReviewQueueItem).where(
                and_(
                    ReviewQueueItem.document_id == doc_uuid,
                    ReviewQueueItem.status.in_(["pending", "in_review"])
                )
            )
        )
        existing_item = existing.scalar_one_or_none()
        if existing_item:
            logger.info(f"Document {document_id} already in review queue")
            return existing_item

        # Calculate priority based on confidence and other factors
        if priority == 0:
            # Auto-calculate priority
            if confidence_score < 0.6:
                priority = 3  # High priority for very low confidence
            elif confidence_score < 0.8:
                priority = 2  # Medium priority
            else:
                priority = 1  # Low priority

        item = ReviewQueueItem(
            document_id=doc_uuid,
            reason=reason,
            reason_code=reason_code,
            confidence_score=confidence_score,
            priority=priority,
            agent_results=agent_results,
            issues_detected=issues_detected,
            status="pending",
        )

        session.add(item)
        session.commit()
        session.refresh(item)

        logger.info(f"Added document {document_id} to review queue with priority {priority}")
        return item

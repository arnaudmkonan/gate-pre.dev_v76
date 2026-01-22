"""
Feedback API Routes.

Endpoints for the feedback learning system that improves
extraction accuracy based on human corrections.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.feedback_service import FeedbackService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/feedback", tags=["Feedback Learning"])


# Request/Response Models

class CorrectionPatternResponse(BaseModel):
    """Response containing correction pattern analysis."""
    total_corrections: int
    correction_types: dict
    fields_by_correction_rate: list
    patterns: list
    period_days: int


class AccuracyReportResponse(BaseModel):
    """Response containing template accuracy report."""
    template_id: str
    template_name: str
    overall_accuracy: float
    total_extractions: int
    total_correct: int
    total_corrected: int
    field_metrics: list
    fields_needing_improvement: list
    correction_patterns: dict
    suggestions: list
    few_shot_count: int


class CalibrationResponse(BaseModel):
    """Response from confidence threshold recalibration."""
    status: str
    old_threshold: Optional[float] = None
    new_threshold: Optional[float] = None
    threshold: Optional[float] = None
    calibration_factor: Optional[float] = None
    message: Optional[str] = None


class FeedbackStatsResponse(BaseModel):
    """Overall feedback system statistics."""
    total_corrections: int
    total_examples: int
    templates_with_feedback: int
    avg_accuracy_improvement: Optional[float]
    most_corrected_fields: list


# API Endpoints

@router.get("/stats", response_model=FeedbackStatsResponse)
async def get_feedback_stats(
    session: AsyncSession = Depends(get_db)
):
    """
    Get overall feedback system statistics.

    Shows how much the system has learned from corrections.
    """
    from sqlalchemy import select, func
    from app.models.feedback_metrics import CorrectionLog, FewShotExample, TemplateFieldMetrics

    try:
        # Count total corrections
        result = await session.execute(select(func.count(CorrectionLog.id)))
        total_corrections = result.scalar() or 0

        # Count total examples
        result = await session.execute(
            select(func.count(FewShotExample.id)).where(FewShotExample.is_active == "active")
        )
        total_examples = result.scalar() or 0

        # Count templates with metrics
        result = await session.execute(
            select(func.count(func.distinct(TemplateFieldMetrics.template_id)))
        )
        templates_with_feedback = result.scalar() or 0

        # Get most corrected fields
        result = await session.execute(
            select(
                CorrectionLog.field_name,
                func.count(CorrectionLog.id).label("count")
            )
            .group_by(CorrectionLog.field_name)
            .order_by(func.count(CorrectionLog.id).desc())
            .limit(5)
        )
        most_corrected = [{"field": row[0], "corrections": row[1]} for row in result.fetchall()]

        return FeedbackStatsResponse(
            total_corrections=total_corrections,
            total_examples=total_examples,
            templates_with_feedback=templates_with_feedback,
            avg_accuracy_improvement=None,  # Would need historical data
            most_corrected_fields=most_corrected,
        )

    except Exception as e:
        logger.error(f"Error getting feedback stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/patterns")
async def get_correction_patterns(
    template_id: Optional[str] = Query(default=None, description="Filter by template ID"),
    field_name: Optional[str] = Query(default=None, description="Filter by field name"),
    days: int = Query(default=30, le=365, description="Analysis period in days"),
    session: AsyncSession = Depends(get_db)
):
    """
    Analyze correction patterns to identify systematic errors.

    Returns:
    - Most common correction types
    - Fields with highest correction rates
    - Patterns that could be automated
    """
    try:
        patterns = await FeedbackService.get_correction_patterns(
            session=session,
            template_id=template_id,
            field_name=field_name,
            days=days,
        )
        return patterns

    except Exception as e:
        logger.error(f"Error analyzing correction patterns: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/template/{template_id}/report")
async def get_template_accuracy_report(
    template_id: str,
    session: AsyncSession = Depends(get_db)
):
    """
    Get detailed accuracy report for a template.

    Shows overall accuracy, per-field breakdown, and improvement suggestions.
    """
    try:
        report = await FeedbackService.get_template_accuracy_report(
            session=session,
            template_id=template_id,
        )

        if "error" in report:
            raise HTTPException(status_code=404, detail=report["error"])

        return report

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating accuracy report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/template/{template_id}/metrics")
async def get_template_field_metrics(
    template_id: str,
    session: AsyncSession = Depends(get_db)
):
    """
    Get field-level accuracy metrics for a template.

    Shows accuracy rate, correction rate, and confidence calibration per field.
    """
    try:
        metrics = await FeedbackService.get_field_metrics(
            session=session,
            template_id=template_id,
        )

        return {
            "template_id": template_id,
            "fields": [m.to_dict() for m in metrics],
            "field_count": len(metrics),
        }

    except Exception as e:
        logger.error(f"Error getting field metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/template/{template_id}/recalibrate")
async def recalibrate_template_threshold(
    template_id: str,
    session: AsyncSession = Depends(get_db)
):
    """
    Recalibrate template confidence threshold based on actual performance.

    Adjusts the threshold to better match the model's actual accuracy.
    """
    try:
        result = await FeedbackService.recalibrate_confidence_threshold(
            session=session,
            template_id=template_id,
        )

        return result

    except Exception as e:
        logger.error(f"Error recalibrating threshold: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/template/{template_id}/examples")
async def get_template_few_shot_examples(
    template_id: str,
    field_name: Optional[str] = Query(default=None, description="Filter by field"),
    limit: int = Query(default=10, le=50),
    session: AsyncSession = Depends(get_db)
):
    """
    Get few-shot examples for a template.

    These are generated from human corrections and used to improve extractions.
    """
    from sqlalchemy import select, and_, desc
    from app.models.feedback_metrics import FewShotExample
    from uuid import UUID

    try:
        query = select(FewShotExample).where(
            and_(
                FewShotExample.template_id == UUID(template_id),
                FewShotExample.is_active == "active",
            )
        )

        if field_name:
            query = query.where(FewShotExample.field_name == field_name)

        query = query.order_by(desc(FewShotExample.quality_score)).limit(limit)

        result = await session.execute(query)
        examples = result.scalars().all()

        return {
            "template_id": template_id,
            "examples": [e.to_dict() for e in examples],
            "count": len(examples),
        }

    except Exception as e:
        logger.error(f"Error getting few-shot examples: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/template/{template_id}/examples/{example_id}")
async def deactivate_few_shot_example(
    template_id: str,
    example_id: str,
    session: AsyncSession = Depends(get_db)
):
    """
    Deactivate a few-shot example (soft delete).

    Use this if an example is causing incorrect extractions.
    """
    from sqlalchemy import select
    from app.models.feedback_metrics import FewShotExample
    from uuid import UUID

    try:
        result = await session.execute(
            select(FewShotExample).where(
                and_(
                    FewShotExample.id == UUID(example_id),
                    FewShotExample.template_id == UUID(template_id),
                )
            )
        )
        example = result.scalar_one_or_none()

        if not example:
            raise HTTPException(status_code=404, detail="Example not found")

        example.is_active = "archived"
        await session.commit()

        # Re-sync template few-shots
        await FeedbackService._sync_template_few_shots(session)

        return {"status": "deactivated", "example_id": example_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deactivating example: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/corrections")
async def list_corrections(
    template_id: Optional[str] = Query(default=None),
    field_name: Optional[str] = Query(default=None),
    correction_type: Optional[str] = Query(default=None),
    used_for_training: Optional[str] = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0),
    session: AsyncSession = Depends(get_db)
):
    """
    List correction logs with optional filters.

    Useful for reviewing what corrections have been made.
    """
    from sqlalchemy import select, desc
    from app.models.feedback_metrics import CorrectionLog
    from uuid import UUID

    try:
        query = select(CorrectionLog)

        if template_id:
            query = query.where(CorrectionLog.template_id == UUID(template_id))
        if field_name:
            query = query.where(CorrectionLog.field_name == field_name)
        if correction_type:
            query = query.where(CorrectionLog.correction_type == correction_type)
        if used_for_training:
            query = query.where(CorrectionLog.used_for_training == used_for_training)

        query = query.order_by(desc(CorrectionLog.created_at)).limit(limit).offset(offset)

        result = await session.execute(query)
        corrections = result.scalars().all()

        return {
            "corrections": [c.to_dict() for c in corrections],
            "count": len(corrections),
            "limit": limit,
            "offset": offset,
        }

    except Exception as e:
        logger.error(f"Error listing corrections: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync-examples")
async def sync_few_shot_examples(
    session: AsyncSession = Depends(get_db)
):
    """
    Manually trigger sync of few-shot examples to templates.

    This is normally done automatically after approvals, but can be
    triggered manually if needed.
    """
    try:
        await FeedbackService._sync_template_few_shots(session)
        return {"status": "synced", "message": "Few-shot examples synced to templates"}

    except Exception as e:
        logger.error(f"Error syncing examples: {e}")
        raise HTTPException(status_code=500, detail=str(e))

"""
Feedback Learning Service.

Analyzes human corrections to improve extraction accuracy over time.
This is the core of the continuous learning system.

Key responsibilities:
1. Log corrections when reviewers fix extractions
2. Analyze correction patterns to identify systematic errors
3. Generate few-shot examples from high-quality corrections
4. Update template confidence thresholds based on actual performance
5. Track field-level accuracy metrics
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Tuple
from uuid import UUID

from sqlalchemy import select, update, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.feedback_metrics import TemplateFieldMetrics, FewShotExample, CorrectionLog
from app.models.extraction_result import ExtractionResult
from app.models.extraction_template import ExtractionTemplate
from app.models.review_queue import ReviewQueueItem, ReviewAction
from app.models.document_metadata import DocumentMetadata

logger = logging.getLogger(__name__)


class FeedbackService:
    """
    Service for learning from human corrections and improving extraction accuracy.
    """

    # Minimum corrections needed before generating few-shot examples
    MIN_CORRECTIONS_FOR_TRAINING = 3

    # Quality threshold for few-shot examples (based on reviewer agreement)
    MIN_QUALITY_SCORE = 0.8

    # Maximum few-shot examples per template field
    MAX_EXAMPLES_PER_FIELD = 5

    @staticmethod
    async def log_correction(
        session: AsyncSession,
        review_item_id: str,
        extraction_id: str,
        field_name: str,
        original_value: Any,
        corrected_value: Any,
        reviewer: str,
        original_confidence: float = None,
        document_snippet: str = None,
        review_notes: str = None,
        template_id: str = None,
        document_id: str = None,
        field_type: str = None,
    ) -> CorrectionLog:
        """
        Log a correction made during review.

        This is called when a reviewer corrects an extraction value.
        """
        # Determine correction type
        correction_type = FeedbackService._classify_correction(
            original_value, corrected_value, field_type
        )

        correction = CorrectionLog(
            review_item_id=UUID(review_item_id),
            extraction_id=UUID(extraction_id),
            template_id=UUID(template_id) if template_id else None,
            document_id=UUID(document_id) if document_id else None,
            field_name=field_name,
            field_type=field_type,
            original_value=original_value,
            corrected_value=corrected_value,
            original_confidence=original_confidence,
            document_snippet=document_snippet,
            correction_type=correction_type,
            reviewer=reviewer,
            review_notes=review_notes,
            used_for_training="pending",
        )

        session.add(correction)
        await session.commit()
        await session.refresh(correction)

        logger.info(
            f"Logged correction for field '{field_name}': {correction_type} "
            f"(review_item={review_item_id})"
        )

        return correction

    @staticmethod
    def _classify_correction(
        original: Any, corrected: Any, field_type: str = None
    ) -> str:
        """Classify the type of correction made."""
        if original is None and corrected is not None:
            return "missing_value"
        elif original is not None and corrected is None:
            return "false_positive"
        elif original == corrected:
            return "no_change"
        elif field_type == "date":
            return "date_format"
        elif field_type == "money":
            return "amount_correction"
        elif isinstance(original, str) and isinstance(corrected, str):
            if original.lower() == corrected.lower():
                return "case_correction"
            elif original.strip() != corrected.strip():
                return "whitespace_correction"
            else:
                return "value_change"
        else:
            return "value_change"

    @staticmethod
    async def update_field_metrics(
        session: AsyncSession,
        template_id: str,
        field_name: str,
        was_correct: bool,
        was_corrected: bool,
        was_missed: bool,
        model_confidence: float = None,
    ) -> TemplateFieldMetrics:
        """
        Update accuracy metrics for a template field.

        Called after each extraction is reviewed (approved/corrected).
        """
        template_uuid = UUID(template_id)

        # Get or create metrics record
        result = await session.execute(
            select(TemplateFieldMetrics).where(
                and_(
                    TemplateFieldMetrics.template_id == template_uuid,
                    TemplateFieldMetrics.field_name == field_name,
                )
            )
        )
        metrics = result.scalar_one_or_none()

        if not metrics:
            metrics = TemplateFieldMetrics(
                template_id=template_uuid,
                field_name=field_name,
                total_extractions=0,
                correct_extractions=0,
                corrected_extractions=0,
                missed_extractions=0,
            )
            session.add(metrics)

        # Update counts
        metrics.total_extractions += 1
        if was_correct:
            metrics.correct_extractions += 1
        if was_corrected:
            metrics.corrected_extractions += 1
        if was_missed:
            metrics.missed_extractions += 1

        # Update rates
        if metrics.total_extractions > 0:
            metrics.accuracy_rate = metrics.correct_extractions / metrics.total_extractions
            metrics.correction_rate = metrics.corrected_extractions / metrics.total_extractions

        # Update confidence calibration
        if model_confidence is not None:
            if metrics.avg_model_confidence is None:
                metrics.avg_model_confidence = model_confidence
            else:
                # Exponential moving average
                alpha = 0.1
                metrics.avg_model_confidence = (
                    alpha * model_confidence + (1 - alpha) * metrics.avg_model_confidence
                )

            metrics.avg_actual_accuracy = metrics.accuracy_rate
            if metrics.avg_model_confidence and metrics.avg_actual_accuracy:
                metrics.confidence_calibration = (
                    metrics.avg_model_confidence - metrics.avg_actual_accuracy
                )

        metrics.last_updated = datetime.now(timezone.utc)

        await session.commit()
        await session.refresh(metrics)

        return metrics

    @staticmethod
    async def process_approved_review(
        session: AsyncSession,
        review_item_id: str,
    ) -> Dict[str, Any]:
        """
        Process an approved review to update metrics and generate examples.

        Called when a review item is approved (with or without corrections).
        """
        item_uuid = UUID(review_item_id)

        # Get review item with extractions
        result = await session.execute(
            select(ReviewQueueItem).where(ReviewQueueItem.id == item_uuid)
        )
        review_item = result.scalar_one_or_none()

        if not review_item:
            logger.warning(f"Review item {review_item_id} not found")
            return {"status": "not_found"}

        # Get all extractions for this document
        result = await session.execute(
            select(ExtractionResult).where(
                ExtractionResult.document_id == review_item.document_id
            )
        )
        extractions = result.scalars().all()

        # Get document for context
        result = await session.execute(
            select(DocumentMetadata).where(
                DocumentMetadata.id == review_item.document_id
            )
        )
        document = result.scalar_one_or_none()

        # Track metrics
        metrics_updated = 0
        examples_generated = 0

        for extraction in extractions:
            # Determine template from agent_name (format: "template:name:id")
            template_id = None
            if extraction.agent_name and extraction.agent_name.startswith("template:"):
                parts = extraction.agent_name.split(":")
                if len(parts) >= 3:
                    template_id = parts[2]

            if not template_id:
                continue

            # Determine if correct/corrected
            was_corrected = extraction.status == "corrected"
            was_correct = extraction.status in ("auto", "extracted") and not was_corrected

            # Update field metrics
            await FeedbackService.update_field_metrics(
                session=session,
                template_id=template_id,
                field_name=extraction.field_name,
                was_correct=was_correct,
                was_corrected=was_corrected,
                was_missed=extraction.field_value is None,
                model_confidence=extraction.confidence,
            )
            metrics_updated += 1

            # If corrected, consider generating few-shot example
            if was_corrected and extraction.correction_value is not None:
                example = await FeedbackService._maybe_generate_example(
                    session=session,
                    template_id=template_id,
                    extraction=extraction,
                    document=document,
                    reviewer=review_item.reviewed_by,
                )
                if example:
                    examples_generated += 1

        # Check if we should update template few-shots
        if examples_generated > 0:
            await FeedbackService._sync_template_few_shots(session)

        logger.info(
            f"Processed approved review {review_item_id}: "
            f"{metrics_updated} metrics updated, {examples_generated} examples generated"
        )

        return {
            "status": "processed",
            "metrics_updated": metrics_updated,
            "examples_generated": examples_generated,
        }

    @staticmethod
    async def _maybe_generate_example(
        session: AsyncSession,
        template_id: str,
        extraction: ExtractionResult,
        document: DocumentMetadata,
        reviewer: str,
    ) -> Optional[FewShotExample]:
        """
        Potentially generate a few-shot example from a correction.

        Only generates if:
        1. We don't have too many examples for this field already
        2. The correction is high quality (not ambiguous)
        """
        template_uuid = UUID(template_id)

        # Check existing example count for this field
        result = await session.execute(
            select(func.count(FewShotExample.id)).where(
                and_(
                    FewShotExample.template_id == template_uuid,
                    FewShotExample.field_name == extraction.field_name,
                    FewShotExample.is_active == "active",
                )
            )
        )
        count = result.scalar()

        if count >= FeedbackService.MAX_EXAMPLES_PER_FIELD:
            logger.debug(
                f"Skipping example generation: already have {count} examples for "
                f"{extraction.field_name}"
            )
            return None

        # Build input text (document snippet around the extracted value)
        input_text = document.extracted_text_snippet or ""
        if len(input_text) > 2000:
            input_text = input_text[:2000] + "..."

        # Build expected output
        expected_output = {
            "field_name": extraction.field_name,
            "value": extraction.correction_value,
            "original_value": extraction.field_value,
        }

        # Create example
        example = FewShotExample(
            template_id=template_uuid,
            source_document_id=extraction.document_id,
            source_extraction_id=extraction.id,
            input_text=input_text,
            expected_output=expected_output,
            field_name=extraction.field_name,
            quality_score=1.0,  # Will be adjusted based on reviewer agreement
            is_active="active",
            created_by=reviewer,
        )

        session.add(example)
        await session.commit()
        await session.refresh(example)

        # Mark correction as used for training
        await session.execute(
            update(CorrectionLog)
            .where(CorrectionLog.extraction_id == extraction.id)
            .values(used_for_training="yes")
        )
        await session.commit()

        logger.info(
            f"Generated few-shot example for template {template_id}, "
            f"field '{extraction.field_name}'"
        )

        return example

    @staticmethod
    async def _sync_template_few_shots(session: AsyncSession):
        """
        Sync few-shot examples to template's few_shot_examples JSON field.

        This updates the template so the TemplateExtractionAgent uses
        the new examples in future extractions.
        """
        # Get all templates that have associated examples
        result = await session.execute(
            select(FewShotExample.template_id)
            .where(FewShotExample.is_active == "active")
            .distinct()
        )
        template_ids = [row[0] for row in result.fetchall()]

        for template_id in template_ids:
            # Get top examples for this template
            result = await session.execute(
                select(FewShotExample)
                .where(
                    and_(
                        FewShotExample.template_id == template_id,
                        FewShotExample.is_active == "active",
                    )
                )
                .order_by(desc(FewShotExample.quality_score))
                .limit(10)  # Max 10 examples per template
            )
            examples = result.scalars().all()

            if not examples:
                continue

            # Build few-shot examples array
            few_shots = []
            for ex in examples:
                few_shots.append({
                    "input": ex.input_text[:1000],  # Truncate for prompt efficiency
                    "output": ex.expected_output,
                    "field": ex.field_name,
                })

            # Update template
            await session.execute(
                update(ExtractionTemplate)
                .where(ExtractionTemplate.id == template_id)
                .values(few_shot_examples=few_shots)
            )

        await session.commit()
        logger.info(f"Synced few-shot examples for {len(template_ids)} templates")

    @staticmethod
    async def get_field_metrics(
        session: AsyncSession,
        template_id: str,
    ) -> List[TemplateFieldMetrics]:
        """Get all field metrics for a template."""
        template_uuid = UUID(template_id)

        result = await session.execute(
            select(TemplateFieldMetrics)
            .where(TemplateFieldMetrics.template_id == template_uuid)
            .order_by(desc(TemplateFieldMetrics.total_extractions))
        )

        return list(result.scalars().all())

    @staticmethod
    async def get_correction_patterns(
        session: AsyncSession,
        template_id: str = None,
        field_name: str = None,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        Analyze correction patterns to identify systematic errors.

        Returns:
            - Most common correction types
            - Fields with highest correction rates
            - Patterns that could be automated
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        # Build query
        query = select(CorrectionLog).where(CorrectionLog.created_at >= cutoff)

        if template_id:
            query = query.where(CorrectionLog.template_id == UUID(template_id))
        if field_name:
            query = query.where(CorrectionLog.field_name == field_name)

        result = await session.execute(query)
        corrections = result.scalars().all()

        if not corrections:
            return {
                "total_corrections": 0,
                "correction_types": {},
                "fields_by_correction_rate": [],
                "patterns": [],
            }

        # Analyze correction types
        type_counts = {}
        field_counts = {}
        for c in corrections:
            type_counts[c.correction_type] = type_counts.get(c.correction_type, 0) + 1
            field_counts[c.field_name] = field_counts.get(c.field_name, 0) + 1

        # Sort by frequency
        sorted_types = sorted(type_counts.items(), key=lambda x: x[1], reverse=True)
        sorted_fields = sorted(field_counts.items(), key=lambda x: x[1], reverse=True)

        # Identify patterns (corrections that happen repeatedly)
        patterns = []
        value_corrections = {}
        for c in corrections:
            if c.correction_type == "value_change":
                key = f"{c.field_name}:{c.original_value}"
                if key not in value_corrections:
                    value_corrections[key] = {"corrected_to": {}, "count": 0}
                value_corrections[key]["count"] += 1
                corrected_str = str(c.corrected_value)
                value_corrections[key]["corrected_to"][corrected_str] = (
                    value_corrections[key]["corrected_to"].get(corrected_str, 0) + 1
                )

        # Find patterns with high frequency
        for key, data in value_corrections.items():
            if data["count"] >= 3:
                field_name, original = key.split(":", 1)
                most_common_correction = max(
                    data["corrected_to"].items(), key=lambda x: x[1]
                )
                patterns.append({
                    "field_name": field_name,
                    "original_value": original,
                    "common_correction": most_common_correction[0],
                    "frequency": data["count"],
                    "confidence": most_common_correction[1] / data["count"],
                })

        return {
            "total_corrections": len(corrections),
            "correction_types": dict(sorted_types),
            "fields_by_correction_rate": sorted_fields[:10],
            "patterns": sorted(patterns, key=lambda x: x["frequency"], reverse=True)[:10],
            "period_days": days,
        }

    @staticmethod
    async def get_template_accuracy_report(
        session: AsyncSession,
        template_id: str,
    ) -> Dict[str, Any]:
        """
        Generate an accuracy report for a template.

        Shows overall accuracy, per-field breakdown, and improvement suggestions.
        """
        template_uuid = UUID(template_id)

        # Get template
        result = await session.execute(
            select(ExtractionTemplate).where(ExtractionTemplate.id == template_uuid)
        )
        template = result.scalar_one_or_none()

        if not template:
            return {"error": "Template not found"}

        # Get field metrics
        metrics = await FeedbackService.get_field_metrics(session, template_id)

        # Get correction patterns
        patterns = await FeedbackService.get_correction_patterns(
            session, template_id=template_id
        )

        # Calculate overall stats
        total_extractions = sum(m.total_extractions for m in metrics)
        total_correct = sum(m.correct_extractions for m in metrics)
        total_corrected = sum(m.corrected_extractions for m in metrics)

        overall_accuracy = total_correct / total_extractions if total_extractions > 0 else 0

        # Find fields needing improvement
        fields_needing_improvement = [
            {
                "field_name": m.field_name,
                "accuracy_rate": m.accuracy_rate,
                "correction_rate": m.correction_rate,
                "total_extractions": m.total_extractions,
                "confidence_calibration": m.confidence_calibration,
            }
            for m in metrics
            if m.accuracy_rate and m.accuracy_rate < 0.9
        ]

        # Generate suggestions
        suggestions = []
        for field in fields_needing_improvement:
            if field["accuracy_rate"] < 0.7:
                suggestions.append({
                    "field": field["field_name"],
                    "issue": "Low accuracy",
                    "suggestion": "Add more extraction hints or few-shot examples",
                    "priority": "high",
                })
            elif field["confidence_calibration"] and field["confidence_calibration"] > 0.2:
                suggestions.append({
                    "field": field["field_name"],
                    "issue": "Overconfident predictions",
                    "suggestion": "Model confidence is higher than actual accuracy",
                    "priority": "medium",
                })

        return {
            "template_id": template_id,
            "template_name": template.name,
            "overall_accuracy": overall_accuracy,
            "total_extractions": total_extractions,
            "total_correct": total_correct,
            "total_corrected": total_corrected,
            "field_metrics": [m.to_dict() for m in metrics],
            "fields_needing_improvement": fields_needing_improvement,
            "correction_patterns": patterns,
            "suggestions": suggestions,
            "few_shot_count": len(template.few_shot_examples) if template.few_shot_examples else 0,
        }

    @staticmethod
    async def recalibrate_confidence_threshold(
        session: AsyncSession,
        template_id: str,
    ) -> Dict[str, Any]:
        """
        Recalibrate template confidence threshold based on actual performance.

        If the template's extractions are frequently wrong despite high confidence,
        raise the threshold. If they're usually correct at lower confidence, lower it.
        """
        template_uuid = UUID(template_id)

        # Get field metrics
        metrics = await FeedbackService.get_field_metrics(session, template_id)

        if not metrics:
            return {"status": "no_data", "message": "No metrics available for calibration"}

        # Calculate weighted average of confidence calibration
        total_extractions = sum(m.total_extractions for m in metrics)
        if total_extractions == 0:
            return {"status": "no_data", "message": "No extractions to analyze"}

        weighted_calibration = sum(
            (m.confidence_calibration or 0) * m.total_extractions
            for m in metrics
        ) / total_extractions

        # Get current threshold
        result = await session.execute(
            select(ExtractionTemplate).where(ExtractionTemplate.id == template_uuid)
        )
        template = result.scalar_one_or_none()

        if not template:
            return {"error": "Template not found"}

        old_threshold = template.confidence_threshold

        # Adjust threshold based on calibration
        # If model is overconfident (calibration > 0), increase threshold
        # If model is underconfident (calibration < 0), decrease threshold
        new_threshold = old_threshold + (weighted_calibration * 0.5)

        # Clamp to reasonable range
        new_threshold = max(0.5, min(0.95, new_threshold))

        # Only update if significant change
        if abs(new_threshold - old_threshold) > 0.05:
            template.confidence_threshold = new_threshold
            await session.commit()

            logger.info(
                f"Recalibrated template {template_id} confidence threshold: "
                f"{old_threshold:.2f} -> {new_threshold:.2f}"
            )

            return {
                "status": "updated",
                "old_threshold": old_threshold,
                "new_threshold": new_threshold,
                "calibration_factor": weighted_calibration,
            }
        else:
            return {
                "status": "unchanged",
                "threshold": old_threshold,
                "calibration_factor": weighted_calibration,
                "message": "Change too small to warrant update",
            }

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

    # ===== Active Learning & Calibration Dashboard =====

    @staticmethod
    async def get_calibration_dashboard(
        session: AsyncSession,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        Get data for the calibration dashboard showing model confidence vs actual accuracy.

        This is the core view for the active learning loop - shows where
        the model is overconfident or underconfident.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        # Get all templates with metrics
        result = await session.execute(
            select(ExtractionTemplate).where(ExtractionTemplate.is_active == True)
        )
        templates = result.scalars().all()

        template_health = []
        overall_calibration = []

        for template in templates:
            # Get field metrics for this template
            metrics_result = await session.execute(
                select(TemplateFieldMetrics).where(
                    TemplateFieldMetrics.template_id == template.id
                )
            )
            metrics = metrics_result.scalars().all()

            if not metrics:
                continue

            # Calculate template-level stats
            total_extractions = sum(m.total_extractions for m in metrics)
            total_correct = sum(m.correct_extractions for m in metrics)
            total_corrected = sum(m.corrected_extractions for m in metrics)

            if total_extractions == 0:
                continue

            accuracy = total_correct / total_extractions
            correction_rate = total_corrected / total_extractions

            # Calculate avg confidence vs accuracy
            avg_confidence = sum(
                (m.avg_model_confidence or 0) * m.total_extractions
                for m in metrics
            ) / total_extractions if total_extractions > 0 else 0

            calibration_error = avg_confidence - accuracy

            # Determine health status
            if accuracy >= 0.95:
                health = "excellent"
            elif accuracy >= 0.85:
                health = "good"
            elif accuracy >= 0.70:
                health = "needs_attention"
            else:
                health = "critical"

            template_data = {
                "template_id": str(template.id),
                "template_name": template.name,
                "document_type": template.document_type,
                "total_extractions": total_extractions,
                "accuracy": round(accuracy, 3),
                "correction_rate": round(correction_rate, 3),
                "avg_model_confidence": round(avg_confidence, 3),
                "calibration_error": round(calibration_error, 3),
                "health": health,
                "field_count": len(metrics),
                "few_shot_count": len(template.few_shot_examples) if template.few_shot_examples else 0,
                "usage_count": template.usage_count,
            }

            template_health.append(template_data)
            overall_calibration.append({
                "confidence": avg_confidence,
                "accuracy": accuracy,
                "extractions": total_extractions,
            })

        # Sort by health priority (critical first)
        health_priority = {"critical": 0, "needs_attention": 1, "good": 2, "excellent": 3}
        template_health.sort(key=lambda x: health_priority.get(x["health"], 4))

        # Calculate overall stats
        total_all = sum(t["total_extractions"] for t in template_health)
        weighted_accuracy = sum(
            t["accuracy"] * t["total_extractions"] for t in template_health
        ) / total_all if total_all > 0 else 0

        weighted_confidence = sum(
            t["avg_model_confidence"] * t["total_extractions"] for t in template_health
        ) / total_all if total_all > 0 else 0

        # Build calibration curve data (for plotting confidence vs accuracy)
        calibration_curve = FeedbackService._build_calibration_curve(overall_calibration)

        return {
            "period_days": days,
            "total_templates": len(template_health),
            "total_extractions": total_all,
            "overall_accuracy": round(weighted_accuracy, 3),
            "overall_confidence": round(weighted_confidence, 3),
            "overall_calibration_error": round(weighted_confidence - weighted_accuracy, 3),
            "templates_by_health": {
                "excellent": len([t for t in template_health if t["health"] == "excellent"]),
                "good": len([t for t in template_health if t["health"] == "good"]),
                "needs_attention": len([t for t in template_health if t["health"] == "needs_attention"]),
                "critical": len([t for t in template_health if t["health"] == "critical"]),
            },
            "template_details": template_health,
            "calibration_curve": calibration_curve,
        }

    @staticmethod
    def _build_calibration_curve(data: List[Dict]) -> List[Dict]:
        """
        Build calibration curve data for visualization.

        Groups extractions into confidence buckets and computes actual accuracy for each.
        """
        # Define buckets: 0-0.5, 0.5-0.6, 0.6-0.7, 0.7-0.8, 0.8-0.9, 0.9-1.0
        buckets = [
            {"min": 0.0, "max": 0.5, "total": 0, "correct": 0},
            {"min": 0.5, "max": 0.6, "total": 0, "correct": 0},
            {"min": 0.6, "max": 0.7, "total": 0, "correct": 0},
            {"min": 0.7, "max": 0.8, "total": 0, "correct": 0},
            {"min": 0.8, "max": 0.9, "total": 0, "correct": 0},
            {"min": 0.9, "max": 1.0, "total": 0, "correct": 0},
        ]

        for item in data:
            conf = item["confidence"]
            acc = item["accuracy"]
            count = item["extractions"]

            for bucket in buckets:
                if bucket["min"] <= conf < bucket["max"] or (bucket["max"] == 1.0 and conf == 1.0):
                    bucket["total"] += count
                    bucket["correct"] += int(acc * count)
                    break

        # Calculate accuracy per bucket
        curve = []
        for bucket in buckets:
            bucket_center = (bucket["min"] + bucket["max"]) / 2
            actual_accuracy = bucket["correct"] / bucket["total"] if bucket["total"] > 0 else None

            curve.append({
                "confidence_bucket": f"{bucket['min']:.1f}-{bucket['max']:.1f}",
                "bucket_center": bucket_center,
                "predicted_accuracy": bucket_center,  # Ideal: confidence = accuracy
                "actual_accuracy": round(actual_accuracy, 3) if actual_accuracy else None,
                "sample_count": bucket["total"],
            })

        return curve

    @staticmethod
    async def get_templates_needing_retraining(
        session: AsyncSession,
        accuracy_threshold: float = 0.80,
        min_extractions: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Identify templates that need retraining based on accuracy decline.

        Returns templates where:
        - Accuracy is below threshold
        - Sufficient extractions to be statistically meaningful
        - Correction rate is high
        """
        result = await session.execute(
            select(ExtractionTemplate).where(ExtractionTemplate.is_active == True)
        )
        templates = result.scalars().all()

        needing_retraining = []

        for template in templates:
            # Get accuracy report
            report = await FeedbackService.get_template_accuracy_report(
                session, str(template.id)
            )

            if report.get("error"):
                continue

            total = report.get("total_extractions", 0)
            accuracy = report.get("overall_accuracy", 1.0)

            if total >= min_extractions and accuracy < accuracy_threshold:
                needing_retraining.append({
                    "template_id": str(template.id),
                    "template_name": template.name,
                    "document_type": template.document_type,
                    "total_extractions": total,
                    "accuracy": round(accuracy, 3),
                    "correction_rate": round(
                        report.get("total_corrected", 0) / total if total > 0 else 0, 3
                    ),
                    "suggestions": report.get("suggestions", []),
                    "fields_needing_improvement": report.get("fields_needing_improvement", []),
                })

        # Sort by accuracy (worst first)
        needing_retraining.sort(key=lambda x: x["accuracy"])

        return needing_retraining

    @staticmethod
    async def suggest_auto_corrections(
        session: AsyncSession,
        template_id: str = None,
        min_frequency: int = 5,
        min_confidence: float = 0.9,
    ) -> List[Dict[str, Any]]:
        """
        Suggest corrections that can be applied automatically based on patterns.

        If a specific correction happens consistently (e.g., "USD" always gets
        corrected to "US Dollars"), suggest automating it.
        """
        patterns = await FeedbackService.get_correction_patterns(
            session,
            template_id=template_id,
            days=60,  # Longer window for pattern detection
        )

        auto_correction_candidates = []

        for pattern in patterns.get("patterns", []):
            if (pattern["frequency"] >= min_frequency and
                pattern["confidence"] >= min_confidence):
                auto_correction_candidates.append({
                    "field_name": pattern["field_name"],
                    "original_pattern": pattern["original_value"],
                    "suggested_correction": pattern["common_correction"],
                    "frequency": pattern["frequency"],
                    "confidence": round(pattern["confidence"], 3),
                    "recommendation": "auto_correct" if pattern["confidence"] >= 0.95 else "suggest",
                })

        return auto_correction_candidates

    @staticmethod
    async def trigger_learning_cycle(
        session: AsyncSession,
        template_id: str = None,
    ) -> Dict[str, Any]:
        """
        Trigger a complete learning cycle for one or all templates.

        This:
        1. Processes pending corrections
        2. Generates new few-shot examples
        3. Recalibrates confidence thresholds
        4. Updates template prompts if needed
        """
        results = {
            "templates_processed": 0,
            "examples_generated": 0,
            "thresholds_updated": 0,
            "details": [],
        }

        if template_id:
            template_ids = [template_id]
        else:
            # Get all active templates
            result = await session.execute(
                select(ExtractionTemplate.id).where(ExtractionTemplate.is_active == True)
            )
            template_ids = [str(row[0]) for row in result.fetchall()]

        for tid in template_ids:
            template_result = {
                "template_id": tid,
                "actions": [],
            }

            # 1. Sync few-shot examples
            await FeedbackService._sync_template_few_shots(session)
            template_result["actions"].append("synced_few_shots")

            # 2. Recalibrate threshold
            calibration = await FeedbackService.recalibrate_confidence_threshold(session, tid)
            if calibration.get("status") == "updated":
                results["thresholds_updated"] += 1
                template_result["actions"].append(f"threshold_updated: {calibration}")

            # 3. Count new examples
            example_result = await session.execute(
                select(func.count(FewShotExample.id)).where(
                    and_(
                        FewShotExample.template_id == UUID(tid),
                        FewShotExample.is_active == "active",
                    )
                )
            )
            example_count = example_result.scalar()
            template_result["few_shot_count"] = example_count
            results["examples_generated"] += example_count

            results["templates_processed"] += 1
            results["details"].append(template_result)

        logger.info(
            f"Learning cycle completed: {results['templates_processed']} templates, "
            f"{results['examples_generated']} examples, {results['thresholds_updated']} thresholds updated"
        )

        return results

    @staticmethod
    async def get_learning_summary(
        session: AsyncSession,
        days: int = 7,
    ) -> Dict[str, Any]:
        """
        Get a summary of learning activity over the specified period.

        Shows corrections logged, examples generated, accuracy improvements.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        # Count corrections in period
        correction_result = await session.execute(
            select(func.count(CorrectionLog.id)).where(
                CorrectionLog.created_at >= cutoff
            )
        )
        corrections_count = correction_result.scalar()

        # Count examples generated in period
        example_result = await session.execute(
            select(func.count(FewShotExample.id)).where(
                FewShotExample.created_at >= cutoff
            )
        )
        examples_count = example_result.scalar()

        # Count unique reviewers
        reviewer_result = await session.execute(
            select(func.count(func.distinct(CorrectionLog.reviewer))).where(
                CorrectionLog.created_at >= cutoff
            )
        )
        reviewers_count = reviewer_result.scalar()

        # Corrections used for training
        training_result = await session.execute(
            select(func.count(CorrectionLog.id)).where(
                and_(
                    CorrectionLog.created_at >= cutoff,
                    CorrectionLog.used_for_training == "yes",
                )
            )
        )
        used_for_training = training_result.scalar()

        # Correction types breakdown
        type_result = await session.execute(
            select(CorrectionLog.correction_type, func.count(CorrectionLog.id))
            .where(CorrectionLog.created_at >= cutoff)
            .group_by(CorrectionLog.correction_type)
        )
        correction_types = {row[0]: row[1] for row in type_result.fetchall()}

        return {
            "period_days": days,
            "corrections_logged": corrections_count,
            "examples_generated": examples_count,
            "corrections_used_for_training": used_for_training,
            "training_utilization": round(
                used_for_training / corrections_count if corrections_count > 0 else 0, 3
            ),
            "active_reviewers": reviewers_count,
            "correction_types": correction_types,
        }

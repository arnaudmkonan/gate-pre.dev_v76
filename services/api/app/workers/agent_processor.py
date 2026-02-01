"""
Celery worker for LLM-powered agent processing.

This worker runs the agent pipeline on processed documents to provide:
1. Document classification
2. Entity extraction
3. Summarization
4. Quality review

Agents are triggered after the initial extraction is complete.
"""

import logging
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_app import celery_app
from app.core.database import get_sync_db, AsyncSessionLocal
from app.core.config import settings
from app.models.document_metadata import DocumentMetadata
from app.services.review_service import ReviewService
from app.services.template_service import TemplateService
from app.services.batch_service import BatchService
from app.services.duplicate_service import DuplicateDetectionService

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=2)
def process_with_agents(self, document_id: str, pipeline_type: str = "standard"):
    """
    Process a document through the LLM agent pipeline.
    
    Args:
        document_id: UUID of the DocumentMetadata record
        pipeline_type: "standard" or "analysis" pipeline
        
    Returns:
        Dict with agent processing results
    """
    try:
        logger.info(f"Starting agent processing for document {document_id}")
        _update_agent_status(document_id, "processing")
        result = _run_agent_pipeline_sync(document_id, pipeline_type)
        logger.info(f"Agent processing completed for {document_id}")
        return result
    except Exception as e:
        logger.error(f"Agent processing failed for {document_id}: {e}")
        _update_agent_status(document_id, "failed", error=str(e))
        raise self.retry(exc=e, countdown=60)


def _update_agent_status(document_id: str, status: str, error: str = None, results: Dict = None):
    """Update agent processing status in document_metadata."""
    from datetime import datetime, timezone as tz
    try:
        doc_uuid = UUID(document_id)
        with get_sync_db() as session:
            result = session.execute(
                select(DocumentMetadata).where(DocumentMetadata.id == doc_uuid)
            )
            doc = result.scalar_one_or_none()
            if doc:
                doc.agent_status = status
                if status == "completed" or status == "failed":
                    doc.agent_processed_at = datetime.now(tz.utc)
                if results:
                    doc.agent_results = results
                elif error:
                    doc.agent_results = {"error": error}
                session.add(doc)
                session.commit()
    except Exception as e:
        logger.warning(f"Failed to update agent status: {e}")


def _run_agent_pipeline_sync(document_id: str, pipeline_type: str) -> Dict[str, Any]:
    """Synchronous wrapper for async agent pipeline."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(
            _run_agent_pipeline_async(document_id, pipeline_type)
        )
    finally:
        loop.close()


async def _run_agent_pipeline_async(document_id: str, pipeline_type: str) -> Dict[str, Any]:
    """Run the agent pipeline asynchronously."""
    from app.agents import (
        AgentContext,
        create_standard_pipeline,
        create_analysis_pipeline,
        create_triage_pipeline,
        create_mapping_pipeline,
    )
    
    # Get document from database
    with get_sync_db() as session:
        doc_uuid = UUID(document_id)
        result = session.execute(
            select(DocumentMetadata).where(DocumentMetadata.id == doc_uuid)
        )
        doc = result.scalar_one_or_none()
        
        if not doc:
            raise ValueError(f"Document {document_id} not found")
        
        # Get full text content
        content = doc.extracted_text_snippet or ""
        job_id = str(doc.job_id) if doc.job_id else None

        if not content:
            logger.warning(f"No content for document {document_id}")
            return {"status": "skipped", "reason": "no_content"}
        
        # Create agent context
        context = AgentContext(
            document_id=str(doc.id),
            filename=doc.filename,
            file_type=doc.file_type,
            content=content,
            metadata={
                "size": doc.size,
                "job_id": str(doc.job_id) if doc.job_id else None,
                "storage_path": doc.raw_storage_path,
            }
        )
    
    results = {}
    
    # --- Step 0: Triage (Intelligent Routing) ---
    # Always run triage first to determine priority and path
    logger.info(f"Running triage for document {document_id}")
    triage_orchestrator = create_triage_pipeline()
    triage_results = await triage_orchestrator.execute_pipeline(context)
    results.update(triage_results)
    
    # Analyze routing decision
    triage_output = triage_results.get("triagist_agent", {}).output or {}
    path_decision = triage_output.get("path", "path_a_semantic")
    priority = triage_output.get("priority", "medium")
    
    logger.info(f"Triagist Decision: Path={path_decision}, Priority={priority}")
    
    # --- Step 1: Main Processing ---
    
    orchestrator = None
    if path_decision == "path_b_code_mapping" and pipeline_type == "standard":
        logger.info("Path B detected - Executing Schema Mapping Pipeline (Inference Mode)")
        # For new files, defaulting to 'infer_schema' task
        context.metadata["task"] = "infer_schema"
        orchestrator = create_mapping_pipeline()
    elif pipeline_type == "analysis":
        orchestrator = create_analysis_pipeline()
    else:
        # Default Path A
        orchestrator = create_standard_pipeline()
    
    # Execute pipeline
    start_time = datetime.now(timezone.utc)
    main_results = await orchestrator.execute_pipeline(context)
    results.update(main_results)

    # After classification, check for matching templates and run template extraction
    await _run_template_extraction(document_id, context, results)

    execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()

    # Store results
    _store_agent_results(document_id, results)

    # Evaluate for human review
    _evaluate_for_review_sync(document_id, results)

    # Update batch job progress
    _update_batch_progress(document_id, context, success=True)
    
    # Log triage decision to document metadata (optional, skipping for now)

    # Format output
    output = {
        "document_id": document_id,
        "pipeline_type": pipeline_type,
        "routing": {
            "path": path_decision,
            "priority": priority
        },
        "execution_time_seconds": execution_time,
        "agents_executed": len(results),
        "results": {},
    }
    
    for agent_name, result in results.items():
        if hasattr(result, 'to_dict'):
             output["results"][agent_name] = result.to_dict()
        else:
             output["results"][agent_name] = str(result)

    # Trigger Entity Resolution (Data Fabric) after processing
    try:
        from app.workers.data_fabric_worker import process_entity_resolution
        process_entity_resolution.delay(document_id)
    except Exception as e:
        logger.warning(f"Failed to trigger entity resolution: {e}")

    return output

def _store_agent_results(document_id: str, results: Dict):
    """Store agent results in the document metadata."""
    from app.models.extraction_result import ExtractionResult
    from datetime import datetime, timezone as tz

    try:
        with get_sync_db() as session:
            doc_uuid = UUID(document_id)
            result = session.execute(
                select(DocumentMetadata).where(DocumentMetadata.id == doc_uuid)
            )
            doc = result.scalar_one_or_none()

            if doc:
                # Compile agent results
                agent_data = {}
                for agent_name, agent_result in results.items():
                    if hasattr(agent_result, 'success'):
                        agent_data[agent_name] = {
                            "success": agent_result.success,
                            "output": agent_result.output,
                            "confidence": agent_result.confidence,
                            "tokens_used": agent_result.tokens_used,
                        }

                # Store classification result
                if "document_classifier" in agent_data:
                    classifier = agent_data["document_classifier"]
                    if classifier.get("success"):
                        doc.detected_language = classifier["output"].get("category")

                # Store template extraction results as ExtractionResult records
                template_extractions_count = 0
                if "template_extraction" in agent_data:
                    template_data = agent_data["template_extraction"]
                    if template_data.get("success") and template_data.get("output"):
                        extractions = template_data["output"].get("extractions", [])
                        template_name = template_data["output"].get("template_name", "unknown")
                        template_id = template_data["output"].get("template_id")

                        for extraction in extractions:
                            if extraction.get("found", True) and extraction.get("value") is not None:
                                try:
                                    extraction_record = ExtractionResult(
                                        document_id=doc_uuid,
                                        extraction_type="template",
                                        field_name=extraction.get("field_name"),
                                        field_value=extraction.get("value"),
                                        raw_value=extraction.get("raw_value"),
                                        normalized_value=extraction.get("normalized_value"),
                                        confidence=extraction.get("confidence", 0.0),
                                        agent_name=f"template:{template_name}" + (f":{template_id}" if template_id else ""),
                                        context_snippet=extraction.get("context"),
                                        status="auto",
                                    )
                                    session.add(extraction_record)
                                    template_extractions_count += 1
                                except Exception as e:
                                    logger.warning(f"Failed to store extraction for field {extraction.get('field_name')}: {e}")

                        logger.info(
                            f"Stored {template_extractions_count} template extractions for document {document_id}"
                        )

                # Store entity_extractor results as ExtractionResult records (bronze/raw layer)
                # This ensures ALL entity extractions are persisted even when no template matches
                entity_extractions_count = 0
                if "entity_extractor" in agent_data:
                    entity_data = agent_data["entity_extractor"]
                    if entity_data.get("success") and entity_data.get("output"):
                        output = entity_data["output"]
                        default_confidence = entity_data.get("confidence", 0.0)
                        
                        # Output format: {entities: [{type, value, confidence, context, normalized_value}, ...]}
                        entities = output.get("entities", [])
                        
                        # Handle list of entity objects (actual format from EntityExtractionAgent)
                        if isinstance(entities, list):
                            for entity in entities:
                                if isinstance(entity, dict) and entity.get("value") is not None:
                                    try:
                                        extraction_record = ExtractionResult(
                                            document_id=doc_uuid,
                                            extraction_type="entity",
                                            field_name=entity.get("type", "unknown"),
                                            field_value=entity.get("value"),
                                            raw_value=str(entity.get("value")) if entity.get("value") else None,
                                            normalized_value=entity.get("normalized_value"),
                                            confidence=entity.get("confidence", default_confidence),
                                            agent_name="entity_extractor",
                                            context_snippet=entity.get("context"),
                                            status="auto",
                                        )
                                        session.add(extraction_record)
                                        entity_extractions_count += 1
                                    except Exception as e:
                                        logger.warning(f"Failed to store entity {entity.get('type')}: {e}")
                        
                        # Also handle dict format for backward compatibility: {type: [values], ...}
                        elif isinstance(entities, dict):
                            for entity_type, entity_values in entities.items():
                                values_list = entity_values if isinstance(entity_values, list) else [entity_values]
                                for value in values_list:
                                    if value is not None:
                                        try:
                                            extraction_record = ExtractionResult(
                                                document_id=doc_uuid,
                                                extraction_type="entity",
                                                field_name=entity_type,
                                                field_value=value,
                                                raw_value=str(value) if value else None,
                                                confidence=default_confidence,
                                                agent_name="entity_extractor",
                                                status="auto",
                                            )
                                            session.add(extraction_record)
                                            entity_extractions_count += 1
                                        except Exception as e:
                                            logger.warning(f"Failed to store entity {entity_type}: {e}")
                        
                        if entity_extractions_count > 0:
                            logger.info(
                                f"Stored {entity_extractions_count} entity extractions for document {document_id}"
                            )

                # Store agent processing results and status
                doc.agent_status = "completed"
                doc.agent_results = agent_data
                doc.agent_processed_at = datetime.now(tz.utc)

                session.add(doc)
                session.commit()
                logger.info(f"Stored agent results for document {document_id}")
    except Exception as e:
        logger.error(f"Failed to store agent results: {e}")


def _calculate_overall_confidence(results: Dict) -> float:
    """Calculate overall confidence from all agent results."""
    confidences = []
    for result in results.values():
        if hasattr(result, 'confidence') and result.confidence is not None:
            confidences.append(result.confidence)
    return sum(confidences) / len(confidences) if confidences else 0.0


def _update_batch_progress(document_id: str, context, success: bool = True):
    """Update batch job progress after processing a document."""
    try:
        # Check if document belongs to a batch job
        job_id = context.metadata.get("job_id") if context.metadata else None
        if not job_id:
            return

        with get_sync_db() as session:
            BatchService.update_batch_progress_sync(
                session=session,
                batch_job_id=job_id,
                processed_increment=1,
                successful_increment=1 if success else 0,
                failed_increment=0 if success else 1
            )
            logger.info(f"Updated batch progress for job {job_id}")
    except Exception as e:
        logger.warning(f"Failed to update batch progress: {e}")


def _check_duplicates_sync(document_id: str):
    """Check for duplicate documents after extraction and flag if found."""
    try:
        with get_sync_db() as session:
            # Run duplicate detection
            result = DuplicateDetectionService.check_all_duplicates_sync(
                session=session,
                document_id=document_id,
                days_back=365
            )

            if result["is_duplicate"] and result["matches"]:
                best_match = result["matches"][0]
                logger.warning(
                    f"Potential duplicate detected for document {document_id}: "
                    f"{best_match['match_type']} match with {best_match['document_id']} "
                    f"(confidence: {best_match['confidence']:.0%})"
                )

                # Update review queue item with duplicate flag
                from app.models.review_queue import ReviewQueueItem
                review_result = session.execute(
                    select(ReviewQueueItem).where(
                        ReviewQueueItem.document_id == UUID(document_id)
                    )
                )
                review_item = review_result.scalar_one_or_none()

                if review_item:
                    # Add duplicate info to issues
                    issues = review_item.issues_detected or []
                    issues.insert(0, {
                        "type": "potential_duplicate",
                        "description": f"Potential duplicate of document {best_match['filename']}",
                        "severity": "high" if best_match["confidence"] >= 0.95 else "medium",
                        "suggestion": f"Review existing document {best_match['document_id'][:8]}... before approving",
                        "duplicate_info": {
                            "match_type": best_match["match_type"],
                            "confidence": best_match["confidence"],
                            "matched_document_id": best_match["document_id"],
                            "matched_filename": best_match["filename"],
                        }
                    })
                    review_item.issues_detected = issues

                    # Increase priority for duplicates
                    if review_item.priority < 3:
                        review_item.priority = 3

                    session.commit()
                    logger.info(f"Flagged review item for document {document_id} as potential duplicate")

    except Exception as e:
        logger.error(f"Duplicate check failed for document {document_id}: {e}")


async def _run_template_extraction(document_id: str, context, results: Dict):
    """
    Check for matching templates and run template-based extraction.

    This runs after the initial classification to leverage document type
    for template matching.
    """
    from app.agents import TemplateExtractionAgent, AgentContext

    try:
        # Get classification result
        classifier_result = results.get("document_classifier")
        classification = None

        if classifier_result and hasattr(classifier_result, 'output'):
            classification = classifier_result.output.get("category")

        logger.info(f"Checking templates for document {document_id} (classification: {classification})")

        # Use sync session to avoid event loop issues in Celery worker
        with get_sync_db() as session:
            # Run sync version of template matching
            matches = TemplateService.match_template_sync(
                session=session,
                document_id=document_id,
                classification=classification,
                customer_id=context.metadata.get("customer_id") if context.metadata else None
            )

            if not matches:
                logger.info(f"No matching templates found for document {document_id}")
                return

            # Use the best matching template if confidence is above threshold
            best_match = matches[0]
            MIN_TEMPLATE_CONFIDENCE = 0.3  # Minimum confidence to use template

            if best_match["confidence"] < MIN_TEMPLATE_CONFIDENCE:
                logger.info(
                    f"Best template match '{best_match['template_name']}' has low confidence "
                    f"({best_match['confidence']:.0%}), skipping template extraction"
                )
                return

            logger.info(
                f"Using template '{best_match['template_name']}' "
                f"(confidence: {best_match['confidence']:.0%}) for document {document_id}"
            )

            # Get full template data (sync)
            template = TemplateService.get_template_sync(session, best_match["template_id"])

            if not template:
                logger.warning(f"Template {best_match['template_id']} not found")
                return

            # Convert template to dict for agent
            template_dict = template.to_dict()

        # Create and run template extraction agent (outside sync session)
        template_agent = TemplateExtractionAgent(template=template_dict)

        # Execute template extraction (async is fine here - no DB ops)
        template_result = await template_agent.execute(context)

        # Store result
        results["template_extraction"] = template_result

        # Record template usage for statistics (sync)
        extraction_confidence = template_result.confidence if template_result else None
        with get_sync_db() as session:
            TemplateService.record_template_usage_sync(
                session=session,
                template_id=best_match["template_id"],
                extraction_confidence=extraction_confidence
            )

        logger.info(
            f"Template extraction completed for document {document_id}: "
            f"{template_result.output.get('fields_found', 0)}/{template_result.output.get('fields_total', 0)} fields extracted"
            if template_result and template_result.output else "no output"
        )

        # Run post-extraction compliance checks
        if template_result and template_result.output:
            await _run_compliance_checks(
                document_id=document_id,
                extraction_results=template_result.output,
                template_name=best_match.get("template_name"),
                results=results,
            )

    except Exception as e:
        logger.error(f"Template extraction failed for document {document_id}: {e}")
        # Don't fail the whole pipeline if template extraction fails
        results["template_extraction_error"] = str(e)


async def _run_compliance_checks(
    document_id: str,
    extraction_results: Dict[str, Any],
    template_name: Optional[str],
    results: Dict,
):
    """
    Run post-extraction compliance checks on template extraction results.

    This includes:
    - HTS code validation against reference data
    - OFAC SDN screening for extracted parties
    - NAICS code suggestions based on products

    Args:
        document_id: Document ID
        extraction_results: Template extraction output
        template_name: Name of the template used
        results: Results dict to store compliance check output
    """
    from app.services.post_extraction_service import PostExtractionServiceSync

    try:
        logger.info(f"Running compliance checks for document {document_id}")

        with get_sync_db() as session:
            service = PostExtractionServiceSync(session)

            compliance_result = service.process_extraction_results(
                document_id=document_id,
                extraction_results=extraction_results,
                template_name=template_name,
            )

            # Store compliance results
            results["compliance_checks"] = compliance_result.to_dict()

            # Log summary
            logger.info(
                f"Compliance checks completed for document {document_id}: "
                f"HTS validations={len(compliance_result.hts_validations)}, "
                f"Party screenings={len(compliance_result.party_screenings)}, "
                f"Risk level={compliance_result.overall_risk_level.value}, "
                f"Issues={len(compliance_result.issues_found)}"
            )

            # If high-risk issues found, flag document for review
            if compliance_result.overall_risk_level.value in ("high", "critical"):
                _flag_for_compliance_review(document_id, compliance_result, session)

    except Exception as e:
        logger.error(f"Compliance checks failed for document {document_id}: {e}")
        results["compliance_checks_error"] = str(e)


def _flag_for_compliance_review(document_id: str, compliance_result, session):
    """Flag document for compliance review if high-risk issues found."""
    from app.models.review_queue import ReviewQueueItem

    try:
        doc_uuid = UUID(document_id)

        # Check if already in review queue
        existing = session.execute(
            select(ReviewQueueItem).where(ReviewQueueItem.document_id == doc_uuid)
        ).scalar_one_or_none()

        if existing:
            # Update existing review item with compliance issues
            issues = existing.issues_detected or []
            for issue in compliance_result.issues_found:
                issues.append({
                    "type": issue.get("type"),
                    "description": issue.get("description"),
                    "severity": issue.get("severity"),
                    "field": issue.get("field"),
                    "value": issue.get("value"),
                    "source": "compliance_check",
                })
            existing.issues_detected = issues
            existing.priority = max(existing.priority or 0, 4)  # High priority for compliance
            session.commit()
            logger.info(f"Updated review queue item for document {document_id} with compliance issues")
        else:
            # Create new review item
            from app.models.review_queue import ReviewQueueItem
            review_item = ReviewQueueItem(
                document_id=doc_uuid,
                reason=f"Compliance check: {compliance_result.overall_risk_level.value} risk",
                reason_code="compliance_risk",
                priority=4,
                confidence_score=0.0,
                issues_detected=compliance_result.issues_found,
            )
            session.add(review_item)
            session.commit()
            logger.info(f"Added document {document_id} to review queue for compliance review")

    except Exception as e:
        logger.error(f"Failed to flag document {document_id} for compliance review: {e}")


def _summarize_agent_results(results: Dict) -> Dict[str, Any]:
    """Summarize agent results for storage in review queue."""
    summary = {}
    for agent_name, result in results.items():
        if hasattr(result, 'output'):
            summary[agent_name] = {
                "success": result.success if hasattr(result, 'success') else True,
                "confidence": result.confidence if hasattr(result, 'confidence') else None,
                "output_keys": list(result.output.keys()) if isinstance(result.output, dict) else None,
            }
    return summary


def _evaluate_for_review_sync(document_id: str, results: Dict):
    """Evaluate agent results and add to review queue if needed (sync version)."""
    try:
        overall_confidence = _calculate_overall_confidence(results)

        # Get quality reviewer results if available
        quality_result = results.get("quality_reviewer")
        issues = []
        human_review_flag = False

        if quality_result and hasattr(quality_result, 'output'):
            issues = quality_result.output.get("issues", [])
            human_review_flag = quality_result.output.get("human_review_flag", False)

        # Determine if review is needed
        should_review, reason = ReviewService.should_require_review(
            confidence=overall_confidence,
            issues=issues
        )

        # Also check if quality agent flagged for review
        if human_review_flag and not should_review:
            should_review = True
            reason = "Flagged by quality reviewer"

        if should_review:
            with get_sync_db() as session:
                ReviewService.add_to_review_queue_sync(
                    session=session,
                    document_id=document_id,
                    reason=reason,
                    reason_code="auto_review",
                    confidence_score=overall_confidence,
                    agent_results=_summarize_agent_results(results),
                    issues_detected=issues if issues else None
                )
                logger.info(f"Added document {document_id} to review queue: {reason}")
        else:
            logger.info(f"Document {document_id} auto-approved (confidence: {overall_confidence:.0%})")

    except Exception as e:
        logger.error(f"Failed to evaluate document for review: {e}")


@celery_app.task(bind=True)
def process_pending_documents(self):
    """
    Periodic task to find and process documents that need agent analysis.
    
    Finds documents that:
    - Have completed extraction
    - Haven't been processed by agents yet
    - Have sufficient content for analysis
    """
    try:
        logger.info("Checking for documents needing agent processing...")
        result = _process_pending_documents_sync()
        logger.info(f"Agent processing check completed: {result}")
        return result
    except Exception as e:
        logger.error(f"Error in pending documents check: {e}")
        raise


def _process_pending_documents_sync() -> Dict[str, Any]:
    """Find and queue documents for agent processing."""
    with get_sync_db() as session:
        # Find documents that:
        # - Have content (extracted_text_snippet not null)
        # - Were recently processed (last 24 hours)
        # - Don't have agent results yet (detected_language is null - we're using this as a marker)
        
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        
        query = select(DocumentMetadata).where(
            DocumentMetadata.extracted_text_snippet.isnot(None),
            DocumentMetadata.extraction_timestamp >= cutoff,
            DocumentMetadata.detected_language.is_(None),
        ).limit(5)  # Process 5 at a time
        
        result = session.execute(query)
        docs = result.scalars().all()
        
        logger.info(f"Found {len(docs)} documents for agent processing")
        
        queued_count = 0
        for doc in docs:
            try:
                # Check if content is substantial enough
                content = doc.extracted_text_snippet or ""
                if len(content) < 50:
                    logger.info(f"Skipping {doc.filename} - content too short")
                    continue
                
                # Queue for agent processing
                process_with_agents.delay(str(doc.id), "standard")
                queued_count += 1
                logger.info(f"Queued agent processing for {doc.filename}")
                
            except Exception as e:
                logger.error(f"Error queuing {doc.id}: {e}")
        
        return {
            "status": "completed",
            "documents_found": len(docs),
            "documents_queued": queued_count,
        }

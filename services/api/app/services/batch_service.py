import logging
import zipfile
import os
import io
import csv
import mimetypes
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any, Tuple
from uuid import UUID
from io import StringIO

from croniter import croniter
from sqlalchemy import and_, desc, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.batch_schedule import BatchSchedule
from app.models.ingest_job import IngestJob, IngestJobStatus
from app.models.batch_job import BatchJob, BulkReviewSession
from app.models.document_metadata import DocumentMetadata
from app.models.extraction_result import ExtractionResult
from app.models.review_queue import ReviewQueueItem
from app.services.extractors.pdf_extractor import PDFExtractor

logger = logging.getLogger(__name__)

# Initialize PDF extractor for text extraction
pdf_extractor = PDFExtractor(enable_ocr=False)  # OCR disabled for speed in batch

# Supported file types for batch upload
SUPPORTED_EXTENSIONS = {
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.csv',
    '.txt', '.json', '.xml', '.html', '.htm',
    '.png', '.jpg', '.jpeg', '.tiff', '.tif'
}

MAX_BATCH_SIZE = 100  # Maximum documents per batch
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB per file


class BatchService:
    """Service for managing batch schedule operations."""

    @staticmethod
    def validate_cron_expression(cron_expression: str) -> bool:
        """
        Validate a cron expression.

        Args:
            cron_expression: Cron expression to validate

        Returns:
            True if valid, False otherwise
        """
        try:
            croniter(cron_expression)
            return True
        except Exception:
            return False

    @staticmethod
    async def create_schedule(
        session: AsyncSession,
        schedule_name: str,
        cron_expression: str,
        max_concurrency: int = 5,
        batch_size: int = 10,
        description: Optional[str] = None,
    ) -> BatchSchedule:
        """
        Create a new batch schedule.

        Args:
            session: Database session
            schedule_name: Unique name for the schedule
            cron_expression: Cron expression for scheduling
            max_concurrency: Maximum concurrent jobs
            batch_size: Jobs per batch
            description: Optional description

        Returns:
            Created BatchSchedule instance
        """
        try:
            # Validate cron expression
            if not BatchService.validate_cron_expression(cron_expression):
                raise ValueError(f"Invalid cron expression: {cron_expression}")

            # Calculate next run time
            cron = croniter(cron_expression, datetime.now(timezone.utc))
            next_run_at = cron.get_next(datetime)

            schedule = BatchSchedule(
                schedule_name=schedule_name,
                cron_expression=cron_expression,
                max_concurrency=max_concurrency,
                batch_size=batch_size,
                is_active=True,
                next_run_at=next_run_at,
                description=description,
            )

            session.add(schedule)
            await session.commit()
            await session.refresh(schedule)

            logger.info(f"Batch schedule created: {schedule.id} ({schedule_name})")
            return schedule

        except Exception as e:
            await session.rollback()
            logger.error(f"Error creating batch schedule: {e}")
            raise

    @staticmethod
    async def get_schedule(
        session: AsyncSession,
        schedule_id: UUID,
    ) -> Optional[BatchSchedule]:
        """Get a batch schedule by ID."""
        try:
            result = await session.execute(
                select(BatchSchedule).where(BatchSchedule.id == schedule_id)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error retrieving batch schedule: {e}")
            raise

    @staticmethod
    async def list_schedules(
        session: AsyncSession,
        is_active: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[BatchSchedule], int]:
        """
        List batch schedules.

        Returns:
            Tuple of (schedules, total_count)
        """
        try:
            query = select(BatchSchedule)

            if is_active is not None:
                query = query.where(BatchSchedule.is_active == is_active)

            # Get total count
            count_result = await session.execute(query)
            total = len(count_result.scalars().all())

            # Get paginated results
            query = query.order_by(desc(BatchSchedule.created_at)).offset(offset).limit(limit)

            result = await session.execute(query)
            schedules = result.scalars().all()

            return schedules, total

        except Exception as e:
            logger.error(f"Error listing schedules: {e}")
            raise

    @staticmethod
    async def update_schedule(
        session: AsyncSession,
        schedule_id: UUID,
        schedule_name: Optional[str] = None,
        cron_expression: Optional[str] = None,
        max_concurrency: Optional[int] = None,
        batch_size: Optional[int] = None,
        is_active: Optional[bool] = None,
        description: Optional[str] = None,
    ) -> BatchSchedule:
        """Update a batch schedule."""
        try:
            schedule = await BatchService.get_schedule(session, schedule_id)
            if not schedule:
                raise ValueError(f"Schedule {schedule_id} not found")

            if schedule_name:
                schedule.schedule_name = schedule_name
            if cron_expression:
                if not BatchService.validate_cron_expression(cron_expression):
                    raise ValueError(f"Invalid cron expression: {cron_expression}")
                schedule.cron_expression = cron_expression
                # Recalculate next run time
                cron = croniter(cron_expression, datetime.now(timezone.utc))
                schedule.next_run_at = cron.get_next(datetime)
            if max_concurrency is not None:
                schedule.max_concurrency = max_concurrency
            if batch_size is not None:
                schedule.batch_size = batch_size
            if is_active is not None:
                schedule.is_active = is_active
            if description is not None:
                schedule.description = description

            await session.commit()
            await session.refresh(schedule)

            logger.info(f"Batch schedule {schedule_id} updated")
            return schedule

        except Exception as e:
            await session.rollback()
            logger.error(f"Error updating batch schedule: {e}")
            raise

    @staticmethod
    async def delete_schedule(
        session: AsyncSession,
        schedule_id: UUID,
    ) -> None:
        """Delete a batch schedule."""
        try:
            schedule = await BatchService.get_schedule(session, schedule_id)
            if not schedule:
                raise ValueError(f"Schedule {schedule_id} not found")

            await session.delete(schedule)
            await session.commit()

            logger.info(f"Batch schedule {schedule_id} deleted")

        except Exception as e:
            await session.rollback()
            logger.error(f"Error deleting batch schedule: {e}")
            raise

    @staticmethod
    async def get_pending_schedules(session: AsyncSession) -> list[BatchSchedule]:
        """Get all schedules that are due to run."""
        try:
            now = datetime.now(timezone.utc)
            result = await session.execute(
                select(BatchSchedule).where(
                    and_(
                        BatchSchedule.is_active == True,
                        BatchSchedule.next_run_at <= now,
                    )
                )
            )
            return result.scalars().all()

        except Exception as e:
            logger.error(f"Error getting pending schedules: {e}")
            raise

    @staticmethod
    async def update_last_run(
        session: AsyncSession,
        schedule_id: UUID,
    ) -> BatchSchedule:
        """Update the last run time and calculate next run time."""
        try:
            schedule = await BatchService.get_schedule(session, schedule_id)
            if not schedule:
                raise ValueError(f"Schedule {schedule_id} not found")

            schedule.last_run_at = datetime.now(timezone.utc)

            # Calculate next run time
            cron = croniter(schedule.cron_expression, schedule.last_run_at)
            schedule.next_run_at = cron.get_next(datetime)

            await session.commit()
            await session.refresh(schedule)

            logger.info(f"Batch schedule {schedule_id} updated - last_run_at: {schedule.last_run_at}")
            return schedule

        except Exception as e:
            await session.rollback()
            logger.error(f"Error updating last run: {e}")
            raise

    @staticmethod
    async def get_jobs_for_batch(
        session: AsyncSession,
        max_jobs: int,
        priority_order: bool = True,
    ) -> list[IngestJob]:
        """
        Get jobs ready for processing in the next batch.

        Args:
            session: Database session
            max_jobs: Maximum number of jobs to retrieve
            priority_order: If True, order by priority then created_at

        Returns:
            List of IngestJob instances
        """
        try:
            query = select(IngestJob).where(IngestJob.status == IngestJobStatus.PENDING)

            if priority_order:
                query = query.order_by(IngestJob.priority.desc(), IngestJob.created_at)
            else:
                query = query.order_by(IngestJob.created_at)

            query = query.limit(max_jobs)

            result = await session.execute(query)
            return result.scalars().all()

        except Exception as e:
            logger.error(f"Error getting jobs for batch: {e}")
            raise

    # ===== Batch Upload Operations =====

    @staticmethod
    async def create_batch_job(
        session: AsyncSession,
        name: str,
        job_type: str = "upload",
        description: Optional[str] = None,
        source_filename: Optional[str] = None,
        source_type: str = "zip",
        customer_id: Optional[str] = None,
        pipeline_type: str = "standard",
        template_id: Optional[str] = None,
        auto_approve_threshold: Optional[float] = None
    ) -> BatchJob:
        """Create a new batch job for tracking batch uploads."""
        batch_job = BatchJob(
            name=name,
            description=description,
            job_type=job_type,
            source_filename=source_filename,
            source_type=source_type,
            customer_id=customer_id,
            pipeline_type=pipeline_type,
            template_id=UUID(template_id) if template_id else None,
            auto_approve_threshold=auto_approve_threshold,
            status="pending",
        )

        session.add(batch_job)
        await session.commit()
        await session.refresh(batch_job)

        logger.info(f"Created batch job {batch_job.id}: {name}")
        return batch_job

    @staticmethod
    async def process_zip_upload(
        session: AsyncSession,
        zip_content: bytes,
        batch_job_id: str,
        storage_service=None
    ) -> Dict[str, Any]:
        """
        Process a ZIP file upload, extracting and queuing individual documents.
        """
        batch_uuid = UUID(batch_job_id)
        result = await session.execute(
            select(BatchJob).where(BatchJob.id == batch_uuid)
        )
        batch_job = result.scalar_one_or_none()

        if not batch_job:
            raise ValueError(f"Batch job {batch_job_id} not found")

        batch_job.status = "extracting"
        batch_job.started_at = datetime.now(timezone.utc)

        extracted_files = []
        failed_files = []
        document_ids = []

        try:
            with zipfile.ZipFile(io.BytesIO(zip_content), 'r') as zip_ref:
                file_list = [f for f in zip_ref.namelist() if not f.endswith('/')]

                if len(file_list) > MAX_BATCH_SIZE:
                    raise ValueError(f"Too many files ({len(file_list)}). Max is {MAX_BATCH_SIZE}")

                batch_job.total_documents = len(file_list)

                for filename in file_list:
                    try:
                        if filename.startswith('.') or filename.startswith('__'):
                            continue

                        _, ext = os.path.splitext(filename.lower())
                        if ext not in SUPPORTED_EXTENSIONS:
                            failed_files.append({
                                "filename": filename,
                                "error": f"Unsupported file type: {ext}"
                            })
                            continue

                        file_info = zip_ref.getinfo(filename)

                        if file_info.file_size > MAX_FILE_SIZE:
                            failed_files.append({
                                "filename": filename,
                                "error": f"File too large: {file_info.file_size / 1024 / 1024:.1f}MB"
                            })
                            continue

                        file_content = zip_ref.read(filename)
                        mime_type, _ = mimetypes.guess_type(filename)
                        base_filename = os.path.basename(filename)

                        # Extract text content based on file type
                        extracted_text = ""
                        if ext == '.pdf':
                            try:
                                extracted_text = await pdf_extractor.extract_text(file_content)
                                logger.info(f"Extracted {len(extracted_text)} chars from {base_filename}")
                            except Exception as e:
                                logger.warning(f"Text extraction failed for {base_filename}: {e}")
                        elif ext in ['.txt', '.csv', '.json', '.xml', '.html', '.htm']:
                            try:
                                extracted_text = file_content.decode('utf-8', errors='ignore')
                            except Exception as e:
                                logger.warning(f"Text decode failed for {base_filename}: {e}")

                        doc = DocumentMetadata(
                            filename=base_filename,
                            file_type=ext.lstrip('.'),
                            size=len(file_content),
                            mime_type=mime_type,
                            job_id=batch_uuid,
                            ingestion_status="pending",
                            extracted_text_snippet=extracted_text[:10000] if extracted_text else None,
                        )

                        session.add(doc)
                        await session.flush()

                        document_ids.append(doc.id)
                        extracted_files.append({
                            "filename": base_filename,
                            "document_id": str(doc.id),
                            "size": len(file_content),
                            "mime_type": mime_type
                        })

                        if storage_service:
                            storage_path = await storage_service.store_file(
                                file_content,
                                filename=f"{doc.id}/{base_filename}",
                                content_type=mime_type
                            )
                            doc.raw_storage_path = storage_path

                    except Exception as e:
                        logger.error(f"Error processing file {filename}: {e}")
                        failed_files.append({"filename": filename, "error": str(e)})

            batch_job.document_ids = document_ids
            batch_job.failed_files = failed_files if failed_files else None
            batch_job.successful_documents = len(extracted_files)
            batch_job.failed_documents = len(failed_files)
            batch_job.status = "processing"

            await session.commit()

            logger.info(f"Batch {batch_job_id}: Extracted {len(extracted_files)} files")

            return {
                "batch_job_id": batch_job_id,
                "total_files": len(file_list),
                "extracted": len(extracted_files),
                "failed": len(failed_files),
                "document_ids": [str(d) for d in document_ids],
                "failed_files": failed_files,
            }

        except zipfile.BadZipFile:
            batch_job.status = "failed"
            batch_job.processing_errors = [{"error": "Invalid ZIP file"}]
            await session.commit()
            raise ValueError("Invalid ZIP file")

    @staticmethod
    async def get_batch_job(
        session: AsyncSession,
        batch_job_id: str
    ) -> Optional[BatchJob]:
        """Get a batch job by ID."""
        batch_uuid = UUID(batch_job_id)
        result = await session.execute(
            select(BatchJob).where(BatchJob.id == batch_uuid)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_batch_jobs(
        session: AsyncSession,
        status: Optional[str] = None,
        customer_id: Optional[str] = None,
        job_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[BatchJob]:
        """List batch jobs with filters."""
        query = select(BatchJob).order_by(BatchJob.created_at.desc())

        conditions = []
        if status:
            conditions.append(BatchJob.status == status)
        if customer_id:
            conditions.append(BatchJob.customer_id == customer_id)
        if job_type:
            conditions.append(BatchJob.job_type == job_type)

        if conditions:
            query = query.where(and_(*conditions))

        query = query.limit(limit).offset(offset)

        result = await session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def update_batch_progress(
        session: AsyncSession,
        batch_job_id: str,
        processed_increment: int = 0,
        successful_increment: int = 0,
        failed_increment: int = 0
    ):
        """Update batch job progress counters."""
        batch_uuid = UUID(batch_job_id)
        result = await session.execute(
            select(BatchJob).where(BatchJob.id == batch_uuid)
        )
        batch_job = result.scalar_one_or_none()

        if batch_job:
            batch_job.processed_documents += processed_increment
            batch_job.successful_documents += successful_increment
            batch_job.failed_documents += failed_increment

            if batch_job.processed_documents >= batch_job.total_documents:
                batch_job.status = "reviewing"
                batch_job.completed_at = datetime.now(timezone.utc)
                if batch_job.started_at:
                    batch_job.processing_time_seconds = (
                        batch_job.completed_at - batch_job.started_at
                    ).total_seconds()

            await session.commit()

    @staticmethod
    async def get_batch_documents(
        session: AsyncSession,
        batch_job_id: str,
        include_extractions: bool = False
    ) -> List[Dict[str, Any]]:
        """Get all documents in a batch with their status."""
        batch_uuid = UUID(batch_job_id)

        result = await session.execute(
            select(BatchJob).where(BatchJob.id == batch_uuid)
        )
        batch_job = result.scalar_one_or_none()

        if not batch_job or not batch_job.document_ids:
            return []

        doc_result = await session.execute(
            select(DocumentMetadata).where(
                DocumentMetadata.id.in_(batch_job.document_ids)
            )
        )
        documents = doc_result.scalars().all()

        results = []
        for doc in documents:
            doc_dict = {
                "id": str(doc.id),
                "filename": doc.filename,
                "file_type": doc.file_type,
                "size": doc.size,
                "ingestion_status": doc.ingestion_status,
                "detected_language": doc.detected_language,
            }

            if include_extractions:
                ext_result = await session.execute(
                    select(ExtractionResult).where(
                        ExtractionResult.document_id == doc.id
                    )
                )
                extractions = ext_result.scalars().all()
                doc_dict["extractions"] = [e.to_dict() for e in extractions]
                doc_dict["extraction_count"] = len(extractions)

            review_result = await session.execute(
                select(ReviewQueueItem).where(
                    ReviewQueueItem.document_id == doc.id
                )
            )
            review_item = review_result.scalar_one_or_none()
            if review_item:
                doc_dict["review_status"] = review_item.status
                doc_dict["review_item_id"] = str(review_item.id)

            results.append(doc_dict)

        return results

    # ===== Bulk Review Operations =====

    @staticmethod
    async def create_bulk_review_session(
        session: AsyncSession,
        reviewer: str,
        review_item_ids: List[str],
        name: Optional[str] = None,
        batch_job_id: Optional[str] = None,
        document_type: Optional[str] = None,
        template_id: Optional[str] = None
    ) -> BulkReviewSession:
        """Create a bulk review session."""
        bulk_session = BulkReviewSession(
            name=name or f"Bulk review - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}",
            reviewer=reviewer,
            batch_job_id=UUID(batch_job_id) if batch_job_id else None,
            document_type=document_type,
            template_id=UUID(template_id) if template_id else None,
            review_item_ids=[UUID(rid) for rid in review_item_ids],
            total_items=len(review_item_ids),
            status="in_progress",
            started_at=datetime.now(timezone.utc),
        )

        session.add(bulk_session)
        await session.commit()
        await session.refresh(bulk_session)

        logger.info(f"Created bulk review session {bulk_session.id} with {len(review_item_ids)} items")
        return bulk_session

    @staticmethod
    async def bulk_approve(
        session: AsyncSession,
        review_item_ids: List[str],
        reviewer: str,
        bulk_session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Bulk approve multiple review items."""
        from app.services.review_service import ReviewService

        approved_count = 0
        failed = []

        for item_id in review_item_ids:
            try:
                await ReviewService.approve_item(
                    session=session,
                    item_id=item_id,
                    reviewer=reviewer,
                    notes="Bulk approved"
                )
                approved_count += 1
            except Exception as e:
                failed.append({"item_id": item_id, "error": str(e)})

        if bulk_session_id:
            result = await session.execute(
                select(BulkReviewSession).where(
                    BulkReviewSession.id == UUID(bulk_session_id)
                )
            )
            bulk_session = result.scalar_one_or_none()
            if bulk_session:
                bulk_session.approved_items += approved_count
                bulk_session.reviewed_items += len(review_item_ids)
                await session.commit()

        return {
            "approved": approved_count,
            "failed": len(failed),
            "failures": failed
        }

    @staticmethod
    async def bulk_correct(
        session: AsyncSession,
        corrections: List[Dict[str, Any]],
        reviewer: str,
        bulk_session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Apply the same correction to multiple extractions."""
        from app.services.review_service import ReviewService

        corrected_count = 0
        failed = []

        for correction in corrections:
            try:
                extraction_id = correction["extraction_id"]
                corrected_value = correction["corrected_value"]

                ext_result = await session.execute(
                    select(ExtractionResult).where(
                        ExtractionResult.id == UUID(extraction_id)
                    )
                )
                extraction = ext_result.scalar_one_or_none()

                if not extraction:
                    failed.append({"extraction_id": extraction_id, "error": "Not found"})
                    continue

                review_result = await session.execute(
                    select(ReviewQueueItem).where(
                        ReviewQueueItem.document_id == extraction.document_id
                    )
                )
                review_item = review_result.scalar_one_or_none()

                if review_item:
                    await ReviewService.correct_extraction(
                        session=session,
                        item_id=str(review_item.id),
                        extraction_id=extraction_id,
                        corrected_value=corrected_value,
                        reviewer=reviewer,
                        notes="Bulk correction"
                    )
                    corrected_count += 1
                else:
                    extraction.correction_value = corrected_value
                    extraction.status = "corrected"
                    extraction.reviewed_by = reviewer
                    extraction.reviewed_at = datetime.now(timezone.utc)
                    corrected_count += 1

            except Exception as e:
                failed.append({
                    "extraction_id": correction.get("extraction_id"),
                    "error": str(e)
                })

        await session.commit()

        if bulk_session_id:
            result = await session.execute(
                select(BulkReviewSession).where(
                    BulkReviewSession.id == UUID(bulk_session_id)
                )
            )
            bulk_session = result.scalar_one_or_none()
            if bulk_session:
                bulk_session.corrected_items += corrected_count
                await session.commit()

        return {
            "corrected": corrected_count,
            "failed": len(failed),
            "failures": failed
        }

    @staticmethod
    async def find_similar_extractions(
        session: AsyncSession,
        field_name: str,
        field_value: Any,
        template_id: Optional[str] = None,
        status: str = "auto"
    ) -> List[ExtractionResult]:
        """Find extractions with similar values for bulk correction."""
        query = select(ExtractionResult).where(
            and_(
                ExtractionResult.field_name == field_name,
                ExtractionResult.status == status
            )
        )

        if template_id:
            query = query.where(
                ExtractionResult.agent_name.contains(template_id)
            )

        result = await session.execute(query)
        extractions = result.scalars().all()

        similar = [ext for ext in extractions if ext.field_value == field_value]
        return similar

    # ===== Batch Export =====

    @staticmethod
    async def export_batch(
        session: AsyncSession,
        batch_job_id: str,
        format: str = "csv",
        include_reviewed_only: bool = True
    ) -> Tuple[bytes, str]:
        """Export all extractions from a batch to CSV."""
        batch_uuid = UUID(batch_job_id)

        result = await session.execute(
            select(BatchJob).where(BatchJob.id == batch_uuid)
        )
        batch_job = result.scalar_one_or_none()

        if not batch_job or not batch_job.document_ids:
            raise ValueError("Batch not found or has no documents")

        query = select(ExtractionResult).where(
            ExtractionResult.document_id.in_(batch_job.document_ids)
        )

        if include_reviewed_only:
            query = query.where(
                ExtractionResult.status.in_(["reviewed", "corrected", "approved"])
            )

        result = await session.execute(query)
        extractions = result.scalars().all()

        docs_data = {}
        all_fields = set()

        for ext in extractions:
            doc_id = str(ext.document_id)
            if doc_id not in docs_data:
                docs_data[doc_id] = {"document_id": doc_id}

            field_name = ext.field_name
            all_fields.add(field_name)
            docs_data[doc_id][field_name] = ext.final_value

        doc_result = await session.execute(
            select(DocumentMetadata).where(
                DocumentMetadata.id.in_(batch_job.document_ids)
            )
        )
        documents = {str(d.id): d.filename for d in doc_result.scalars().all()}

        for doc_id in docs_data:
            docs_data[doc_id]["filename"] = documents.get(doc_id, "unknown")

        if format == "csv":
            output = StringIO()
            fieldnames = ["filename", "document_id"] + sorted(all_fields)
            writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()

            for doc_data in docs_data.values():
                writer.writerow(doc_data)

            content = output.getvalue().encode('utf-8')
            filename = f"batch_{batch_job_id[:8]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

            batch_job.export_status = "exported"
            batch_job.exported_at = datetime.now(timezone.utc)
            await session.commit()

            return content, filename

        else:
            raise ValueError(f"Unsupported export format: {format}")

    # ===== Sync versions for Celery workers =====

    @staticmethod
    def update_batch_progress_sync(
        session,
        batch_job_id: str,
        processed_increment: int = 0,
        successful_increment: int = 0,
        failed_increment: int = 0
    ):
        """Update batch job progress (sync version for Celery)."""
        batch_uuid = UUID(batch_job_id)
        result = session.execute(
            select(BatchJob).where(BatchJob.id == batch_uuid)
        )
        batch_job = result.scalar_one_or_none()

        if batch_job:
            batch_job.processed_documents += processed_increment
            batch_job.successful_documents += successful_increment
            batch_job.failed_documents += failed_increment

            if batch_job.processed_documents >= batch_job.total_documents:
                batch_job.status = "reviewing"
                batch_job.completed_at = datetime.now(timezone.utc)
                if batch_job.started_at:
                    batch_job.processing_time_seconds = (
                        batch_job.completed_at - batch_job.started_at
                    ).total_seconds()

            session.commit()

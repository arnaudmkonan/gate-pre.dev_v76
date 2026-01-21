"""API endpoints for normalization validation."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.celery_app import celery_app
from app.services.validation_engine import ValidationEngine, ValidationResult
from app.services.validation_reporting import (
    ValidationReport,
    ValidationReportingService,
)
from app.models.normalization_validation import NormalizationValidation
from pydantic import BaseModel
from typing import Optional, List

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/validation", tags=["validation"])


class ValidationRequest(BaseModel):
    """Request to validate normalization."""

    batch_id: UUID
    records: List[dict]  # List of records to validate
    custom_rules: Optional[dict] = None


class ValidationResponse(BaseModel):
    """Validation response."""

    batch_id: UUID
    total_records: int
    valid_count: int
    invalid_count: int
    warning_count: int
    valid_percentage: float
    status: str  # "success", "partial_failure", "failure"
    export_formats: List[str] = ["csv", "json"]


@router.post(
    "/validate-normalization",
    response_model=ValidationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def validate_normalization(
    request: ValidationRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Validate normalization of records.

    Performs type checks, required field validation, range validation,
    and cross-field consistency checks. Returns validation report with
    pass/fail status for each record and per-field error messages.

    Args:
        request: Batch of records to validate
        session: Database session

    Returns:
        202 Accepted with validation summary
    """
    try:
        if not request.records:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Records list cannot be empty",
            )

        if len(request.records) > 10000:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Batch size exceeds maximum (10000 records)",
            )

        # Validate each record
        results: List[ValidationResult] = []
        for record in request.records:
            result = ValidationEngine.validate_record(
                record,
                custom_rules=request.custom_rules,
            )
            results.append(result)

        # Store results in database
        await ValidationReportingService.store_validation_results(
            session, request.batch_id, results
        )
        await session.commit()

        # Generate response
        valid_count = sum(1 for r in results if r.is_valid)
        invalid_count = sum(1 for r in results if not r.is_valid)
        warning_count = sum(1 for r in results if r.warnings)

        status_str = "success" if invalid_count == 0 else "partial_failure"
        if invalid_count == len(results):
            status_str = "failure"

        return ValidationResponse(
            batch_id=request.batch_id,
            total_records=len(results),
            valid_count=valid_count,
            invalid_count=invalid_count,
            warning_count=warning_count,
            valid_percentage=(
                (valid_count / len(results) * 100) if results else 0
            ),
            status=status_str,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Validation error: {e}")
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Validation failed",
        )


@router.get(
    "/validation-summary/{batch_id}",
    status_code=status.HTTP_200_OK,
)
async def get_validation_summary(
    batch_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """
    Get validation summary for a batch.

    Returns counts of valid, invalid, and warning records.
    """
    try:
        summary = await ValidationReportingService.get_batch_validation_summary(
            session, batch_id
        )
        return summary
    except Exception as e:
        logger.error(f"Failed to get validation summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve validation summary",
        )


@router.get(
    "/export-invalid/{batch_id}",
    status_code=status.HTTP_200_OK,
)
async def export_invalid_records(
    batch_id: UUID,
    format: str = Query("csv", pattern="^(csv|json)$"),
    session: AsyncSession = Depends(get_db),
):
    """
    Export invalid records from validation.

    Returns a file (CSV or JSON) containing only records that failed validation.

    Args:
        batch_id: Batch ID
        format: Export format (csv or json)

    Returns:
        CSV or JSON file download
    """
    try:
        # Get validation records
        from sqlalchemy import select

        stmt = select(NormalizationValidation).where(
            NormalizationValidation.batch_id == batch_id,
            NormalizationValidation.validation_status == "fail",
        )
        result = await session.execute(stmt)
        records = result.scalars().all()

        if not records:
            return {"message": "No invalid records to export"}

        if format == "csv":
            # Convert to ValidationResult objects for reporting
            results = [
                ValidationResult(r.record_id, r.document_id) for r in records
            ]
            csv_data = ValidationReportingService.export_csv(results, include_details=True)
            return StreamingResponse(
                iter([csv_data]),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename=invalid_records_{batch_id}.csv"},
            )
        else:  # json
            results = [
                ValidationResult(r.record_id, r.document_id) for r in records
            ]
            json_data = ValidationReportingService.export_json(results)
            return StreamingResponse(
                iter([json_data]),
                media_type="application/json",
                headers={"Content-Disposition": f"attachment; filename=invalid_records_{batch_id}.json"},
            )

    except Exception as e:
        logger.error(f"Failed to export invalid records: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export invalid records",
        )

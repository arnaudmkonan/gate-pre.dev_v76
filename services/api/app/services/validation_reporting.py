"""Service for generating validation reports and exports."""

import csv
import json
import logging
from io import StringIO, BytesIO
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.normalization_validation import NormalizationValidation
from app.services.validation_engine import ValidationResult

logger = logging.getLogger(__name__)


class ValidationReport:
    """Complete validation report for a batch."""

    def __init__(self, batch_id: UUID):
        self.batch_id = batch_id
        self.total_records = 0
        self.valid_count = 0
        self.invalid_count = 0
        self.warning_count = 0
        self.results: List[ValidationResult] = []

    def add_result(self, result: ValidationResult):
        """Add a validation result."""
        self.results.append(result)
        self.total_records += 1

        if result.is_valid:
            self.valid_count += 1
        else:
            self.invalid_count += 1

        if result.warnings:
            self.warning_count += 1

    def to_dict(self) -> Dict:
        """Convert report to dictionary."""
        return {
            "batch_id": str(self.batch_id),
            "summary": {
                "total_records": self.total_records,
                "valid_count": self.valid_count,
                "invalid_count": self.invalid_count,
                "warning_count": self.warning_count,
                "valid_percentage": (
                    (self.valid_count / self.total_records * 100)
                    if self.total_records > 0
                    else 0
                ),
            },
            "results": [r.to_dict() for r in self.results],
        }

    def to_json(self) -> str:
        """Convert report to JSON string."""
        return json.dumps(self.to_dict(), indent=2)


class ValidationReportingService:
    """Service for generating and exporting validation reports."""

    @staticmethod
    def generate_report(results: List[ValidationResult]) -> ValidationReport:
        """Generate a validation report from results."""
        report = ValidationReport(batch_id=UUID("00000000-0000-0000-0000-000000000000"))

        for result in results:
            report.add_result(result)

        return report

    @staticmethod
    def export_csv(
        results: List[ValidationResult],
        include_details: bool = False,
    ) -> str:
        """
        Export invalid records to CSV format.

        Args:
            results: List of validation results
            include_details: Whether to include detailed error information

        Returns:
            CSV string
        """
        output = StringIO()

        # Filter to invalid records only
        invalid_results = [r for r in results if not r.is_valid]

        if not invalid_results:
            return "record_id,document_id,status,error_count\nNo invalid records"

        fieldnames = ["record_id", "document_id", "status", "error_count"]
        if include_details:
            fieldnames.extend(["error_message", "field_errors"])

        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for result in invalid_results:
            row = {
                "record_id": result.record_id,
                "document_id": result.document_id,
                "status": "fail",
                "error_count": len(result.errors),
            }

            if include_details:
                error_msgs = [f"{e.field}: {e.message}" for e in result.errors]
                row["error_message"] = "; ".join(error_msgs)
                row["field_errors"] = json.dumps(
                    {e.field: e.message for e in result.errors}
                )

            writer.writerow(row)

        return output.getvalue()

    @staticmethod
    def export_json(results: List[ValidationResult]) -> str:
        """
        Export validation results to JSON format.

        Args:
            results: List of validation results

        Returns:
            JSON string
        """
        data = {
            "summary": {
                "total_records": len(results),
                "valid_count": sum(1 for r in results if r.is_valid),
                "invalid_count": sum(1 for r in results if not r.is_valid),
                "warning_count": sum(1 for r in results if r.warnings),
            },
            "invalid_records": [r.to_dict() for r in results if not r.is_valid],
        }
        return json.dumps(data, indent=2)

    @staticmethod
    async def store_validation_results(
        session: AsyncSession,
        batch_id: UUID,
        results: List[ValidationResult],
    ) -> int:
        """
        Store validation results in database.

        Args:
            session: Database session
            batch_id: Batch ID being validated
            results: List of validation results

        Returns:
            Number of records stored
        """
        count = 0
        for result in results:
            validation_record = NormalizationValidation(
                batch_id=batch_id,
                record_id=result.record_id,
                document_id=result.document_id,
                validation_status="pass" if result.is_valid else "fail",
                field_errors={e.field: e.message for e in result.errors},
                validation_details=result.to_dict(),
                error_message=(
                    "; ".join([e.message for e in result.errors])
                    if result.errors
                    else None
                ),
            )
            session.add(validation_record)
            count += 1

        await session.flush()
        return count

    @staticmethod
    async def get_batch_validation_summary(
        session: AsyncSession,
        batch_id: UUID,
    ) -> Dict:
        """Get validation summary for a batch."""
        stmt = select(NormalizationValidation).where(
            NormalizationValidation.batch_id == batch_id
        )
        result = await session.execute(stmt)
        records = result.scalars().all()

        if not records:
            return {
                "batch_id": str(batch_id),
                "total": 0,
                "valid": 0,
                "invalid": 0,
                "warnings": 0,
            }

        total = len(records)
        valid = sum(1 for r in records if r.validation_status == "pass")
        invalid = sum(1 for r in records if r.validation_status == "fail")
        warnings = sum(1 for r in records if r.validation_status == "warning")

        return {
            "batch_id": str(batch_id),
            "total": total,
            "valid": valid,
            "invalid": invalid,
            "warnings": warnings,
            "valid_percentage": (valid / total * 100) if total > 0 else 0,
        }

"""
Export Service.

Handles exporting extracted data to Excel, CSV, and other formats
with configurable field mapping.
"""

import io
import csv
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document_metadata import DocumentMetadata
from app.models.extraction_result import ExtractionResult, FieldMappingTemplate

logger = logging.getLogger(__name__)


class ExportService:
    """
    Service for exporting extracted data to various formats.
    """
    
    @staticmethod
    async def get_extractable_fields(
        session: AsyncSession,
        document_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get all extractable fields for a document.
        
        Returns list of available fields with their types and sample values.
        """
        doc_uuid = UUID(document_id)
        
        # Get extraction results
        query = select(ExtractionResult).where(
            ExtractionResult.document_id == doc_uuid
        )
        result = await session.execute(query)
        extractions = result.scalars().all()
        
        fields = []
        field_types = {}
        
        for extraction in extractions:
            field_key = f"{extraction.extraction_type}.{extraction.field_name}"
            
            if field_key not in field_types:
                field_types[field_key] = {
                    "field_path": field_key,
                    "extraction_type": extraction.extraction_type,
                    "field_name": extraction.field_name,
                    "sample_value": extraction.field_value,
                    "data_type": type(extraction.field_value).__name__,
                    "count": 1,
                    "avg_confidence": extraction.confidence,
                }
            else:
                field_types[field_key]["count"] += 1
                field_types[field_key]["avg_confidence"] = (
                    field_types[field_key]["avg_confidence"] + extraction.confidence
                ) / 2
        
        return list(field_types.values())
    
    @staticmethod
    async def export_to_excel(
        session: AsyncSession,
        document_ids: List[str],
        mapping_template_id: Optional[str] = None,
        include_confidence: bool = False,
        include_metadata: bool = False
    ) -> bytes:
        """
        Export extracted data to Excel format.
        
        Args:
            session: Database session
            document_ids: List of document IDs to export
            mapping_template_id: Optional field mapping template ID
            include_confidence: Include confidence scores
            include_metadata: Include document metadata
            
        Returns:
            Excel file as bytes
        """
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
            from openpyxl.utils import get_column_letter
        except ImportError:
            raise ImportError("openpyxl is required for Excel export")
        
        # Get mapping template if specified
        mapping = None
        if mapping_template_id:
            result = await session.execute(
                select(FieldMappingTemplate).where(
                    FieldMappingTemplate.id == UUID(mapping_template_id)
                )
            )
            mapping = result.scalar_one_or_none()
        
        # Create workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "Extracted Data"
        
        # Styles
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        
        # Collect all data
        all_rows = []
        all_fields = set()
        
        for doc_id in document_ids:
            row_data = await ExportService._get_document_export_data(
                session, doc_id, mapping, include_confidence, include_metadata
            )
            if row_data:
                all_fields.update(row_data.keys())
                all_rows.append(row_data)
        
        if not all_rows:
            # Return empty workbook
            ws.append(["No data to export"])
            output = io.BytesIO()
            wb.save(output)
            return output.getvalue()
        
        # Determine column order
        if mapping and mapping.mappings:
            # Use mapping order
            columns = [m.get("target_column", m.get("source_field")) for m in mapping.mappings]
            # Add any extra fields not in mapping
            for field in sorted(all_fields):
                if field not in columns:
                    columns.append(field)
        else:
            # Default order
            priority_fields = ["filename", "document_type", "status"]
            columns = [f for f in priority_fields if f in all_fields]
            columns.extend(sorted(f for f in all_fields if f not in priority_fields))
        
        # Write headers
        for col_idx, column in enumerate(columns, 1):
            cell = ws.cell(row=1, column=col_idx, value=column)
            cell.font = header_font
            cell.fill = header_fill
            cell.border = thin_border
            cell.alignment = Alignment(horizontal="center")
        
        # Write data rows
        for row_idx, row_data in enumerate(all_rows, 2):
            for col_idx, column in enumerate(columns, 1):
                value = row_data.get(column, "")
                if isinstance(value, (dict, list)):
                    value = json.dumps(value)
                cell = ws.cell(row=row_idx, column=col_idx, value=value)
                cell.border = thin_border
        
        # Auto-adjust column widths
        for col_idx, column in enumerate(columns, 1):
            max_length = len(str(column))
            for row in ws.iter_rows(min_row=2, min_col=col_idx, max_col=col_idx):
                for cell in row:
                    if cell.value:
                        max_length = max(max_length, len(str(cell.value)))
            adjusted_width = min(50, max_length + 2)
            ws.column_dimensions[get_column_letter(col_idx)].width = adjusted_width
        
        # Save to bytes
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return output.getvalue()
    
    @staticmethod
    async def export_to_csv(
        session: AsyncSession,
        document_ids: List[str],
        mapping_template_id: Optional[str] = None,
        include_confidence: bool = False,
        include_metadata: bool = False
    ) -> bytes:
        """
        Export extracted data to CSV format.
        
        Returns:
            CSV file as bytes
        """
        # Get mapping template if specified
        mapping = None
        if mapping_template_id:
            result = await session.execute(
                select(FieldMappingTemplate).where(
                    FieldMappingTemplate.id == UUID(mapping_template_id)
                )
            )
            mapping = result.scalar_one_or_none()
        
        # Collect all data
        all_rows = []
        all_fields = set()
        
        for doc_id in document_ids:
            row_data = await ExportService._get_document_export_data(
                session, doc_id, mapping, include_confidence, include_metadata
            )
            if row_data:
                all_fields.update(row_data.keys())
                all_rows.append(row_data)
        
        if not all_rows:
            return b"No data to export"
        
        # Determine column order
        if mapping and mapping.mappings:
            columns = [m.get("target_column", m.get("source_field")) for m in mapping.mappings]
            for field in sorted(all_fields):
                if field not in columns:
                    columns.append(field)
        else:
            priority_fields = ["filename", "document_type", "status"]
            columns = [f for f in priority_fields if f in all_fields]
            columns.extend(sorted(f for f in all_fields if f not in priority_fields))
        
        # Write CSV
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        
        for row_data in all_rows:
            # Convert complex types to strings
            clean_row = {}
            for key, value in row_data.items():
                if isinstance(value, (dict, list)):
                    clean_row[key] = json.dumps(value)
                else:
                    clean_row[key] = value
            writer.writerow(clean_row)
        
        return output.getvalue().encode("utf-8")
    
    @staticmethod
    async def _get_document_export_data(
        session: AsyncSession,
        document_id: str,
        mapping: Optional[FieldMappingTemplate],
        include_confidence: bool,
        include_metadata: bool
    ) -> Dict[str, Any]:
        """Get export data for a single document."""
        doc_uuid = UUID(document_id)
        
        # Get document metadata
        doc_result = await session.execute(
            select(DocumentMetadata).where(DocumentMetadata.id == doc_uuid)
        )
        doc = doc_result.scalar_one_or_none()
        
        if not doc:
            return {}
        
        # Start with base info
        row_data = {
            "document_id": str(doc.id),
            "filename": doc.filename,
            "file_type": doc.file_type,
            "status": doc.ingestion_status,
        }
        
        if include_metadata:
            row_data.update({
                "size": doc.size,
                "created_at": doc.created_at.isoformat() if doc.created_at else "",
                "customer_id": doc.customer_id or "",
                "source": doc.source or "",
            })
        
        # Get extraction results
        ext_result = await session.execute(
            select(ExtractionResult).where(
                ExtractionResult.document_id == doc_uuid
            )
        )
        extractions = ext_result.scalars().all()
        
        # Group extractions by field
        field_values = {}
        field_confidences = {}
        
        for extraction in extractions:
            field_key = f"{extraction.extraction_type}.{extraction.field_name}"
            
            # Use final value (corrected if available)
            value = extraction.final_value
            
            if field_key not in field_values:
                field_values[field_key] = value
                field_confidences[field_key] = extraction.confidence
            else:
                # Multiple values for same field - create list
                existing = field_values[field_key]
                if not isinstance(existing, list):
                    field_values[field_key] = [existing, value]
                else:
                    field_values[field_key].append(value)
        
        # Apply mapping if provided
        if mapping and mapping.mappings:
            for field_mapping in mapping.mappings:
                source_field = field_mapping.get("source_field")
                target_column = field_mapping.get("target_column", source_field)
                transform = field_mapping.get("transform", "none")
                default_value = field_mapping.get("default_value", "")
                
                value = field_values.get(source_field, default_value)
                value = ExportService._apply_transform(value, transform)
                
                row_data[target_column] = value
                
                if include_confidence:
                    conf = field_confidences.get(source_field, 0)
                    row_data[f"{target_column}_confidence"] = f"{conf:.2%}"
        else:
            # No mapping - include all fields
            row_data.update(field_values)
            
            if include_confidence:
                for field_key, conf in field_confidences.items():
                    row_data[f"{field_key}_confidence"] = f"{conf:.2%}"
        
        return row_data
    
    @staticmethod
    def _apply_transform(value: Any, transform: str) -> Any:
        """Apply a transformation to a value."""
        if value is None:
            return ""
        
        if transform == "none":
            return value
        
        elif transform == "uppercase":
            return str(value).upper()
        
        elif transform == "lowercase":
            return str(value).lower()
        
        elif transform == "currency_number":
            # Extract number from currency string like "$724.00"
            try:
                cleaned = str(value).replace("$", "").replace(",", "").strip()
                return float(cleaned)
            except:
                return value
        
        elif transform == "date_iso":
            # Try to parse and format as ISO date
            try:
                if isinstance(value, datetime):
                    return value.strftime("%Y-%m-%d")
                # Try common formats
                for fmt in ["%B %d, %Y", "%m/%d/%Y", "%Y-%m-%d"]:
                    try:
                        dt = datetime.strptime(str(value), fmt)
                        return dt.strftime("%Y-%m-%d")
                    except:
                        continue
            except:
                pass
            return value
        
        elif transform == "first_item":
            # Get first item if list
            if isinstance(value, list) and value:
                return value[0]
            return value
        
        elif transform == "join_comma":
            # Join list with commas
            if isinstance(value, list):
                return ", ".join(str(v) for v in value)
            return value
        
        return value
    
    @staticmethod
    async def create_mapping_template(
        session: AsyncSession,
        name: str,
        mappings: List[Dict],
        customer_id: Optional[str] = None,
        document_type: Optional[str] = None,
        description: Optional[str] = None,
        is_default: bool = False
    ) -> FieldMappingTemplate:
        """Create a new field mapping template."""
        template = FieldMappingTemplate(
            name=name,
            description=description,
            customer_id=customer_id,
            document_type=document_type,
            mappings=mappings,
            is_default=is_default,
        )
        
        session.add(template)
        await session.commit()
        await session.refresh(template)
        
        return template
    
    @staticmethod
    async def get_mapping_templates(
        session: AsyncSession,
        customer_id: Optional[str] = None,
        document_type: Optional[str] = None
    ) -> List[FieldMappingTemplate]:
        """Get available mapping templates."""
        query = select(FieldMappingTemplate).where(
            FieldMappingTemplate.is_active == True
        )
        
        if customer_id:
            query = query.where(
                (FieldMappingTemplate.customer_id == customer_id) |
                (FieldMappingTemplate.customer_id.is_(None))
            )
        
        if document_type:
            query = query.where(
                (FieldMappingTemplate.document_type == document_type) |
                (FieldMappingTemplate.document_type.is_(None))
            )
        
        query = query.order_by(FieldMappingTemplate.is_default.desc())
        
        result = await session.execute(query)
        return result.scalars().all()

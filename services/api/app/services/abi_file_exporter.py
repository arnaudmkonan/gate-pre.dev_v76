"""
ABI File Exporter Service.

Generates downloadable ABI files for ACE/CBP submission.
Wraps the existing ABIMessageGenerator to provide file export functionality.

Usage:
    exporter = ABIFileExporter(db)
    content, filename = await exporter.export_entry(entry_id)
"""

import logging
import zipfile
import io
from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.abi_generator import (
    ABIMessageGenerator,
    ABIMessage,
    ABIMessageType,
    generate_abi_message,
)

logger = logging.getLogger(__name__)


class ABIFileExporter:
    """
    Exports entries to ABI file format for ACE submission.
    
    Supports:
    - Single entry export
    - Bulk export (ZIP archive)
    - Different message types (SE, AD, RM)
    """
    
    def __init__(self, db: AsyncSession):
        """
        Initialize exporter with database session.
        
        Args:
            db: Async database session
        """
        self.db = db
        self.generator = ABIMessageGenerator()
    
    async def export_entry(
        self,
        entry_id: str,
        message_type: str = ABIMessageType.ENTRY_SUMMARY,
        include_metadata: bool = True,
    ) -> Tuple[str, str]:
        """
        Export a single entry to ABI format.
        
        Args:
            entry_id: UUID of the entry
            message_type: SE (Entry Summary), AD (Add), RM (Replace)
            include_metadata: Include file header with metadata
            
        Returns:
            Tuple of (file_content, filename)
        """
        # Generate ABI message
        message = await generate_abi_message(self.db, entry_id, message_type)
        
        if message.validation_errors:
            logger.warning(f"ABI message has validation errors: {message.validation_errors}")
        
        # Build file content
        content_parts = []
        
        if include_metadata:
            content_parts.append(self._generate_file_header(message, entry_id))
        
        content_parts.append(message.to_abi_string())
        
        content = "\n".join(content_parts)
        
        # Generate filename
        entry_num = self._extract_entry_number(message)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"ABI_{message_type}_{entry_num or entry_id[:8]}_{timestamp}.abi"
        
        logger.info(f"Exported entry {entry_id} to ABI file: {filename}")
        
        return content, filename
    
    async def export_bulk(
        self,
        entry_ids: List[str],
        message_type: str = ABIMessageType.ENTRY_SUMMARY,
    ) -> Tuple[bytes, str]:
        """
        Export multiple entries to a ZIP archive.
        
        Args:
            entry_ids: List of entry UUIDs
            message_type: Message type for all entries
            
        Returns:
            Tuple of (zip_bytes, filename)
        """
        zip_buffer = io.BytesIO()
        
        errors = []
        successful = 0
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for entry_id in entry_ids:
                try:
                    content, filename = await self.export_entry(
                        entry_id,
                        message_type,
                        include_metadata=True
                    )
                    zf.writestr(filename, content)
                    successful += 1
                except Exception as e:
                    logger.error(f"Failed to export entry {entry_id}: {e}")
                    errors.append(f"{entry_id}: {str(e)}")
            
            # Add manifest file
            manifest = self._generate_manifest(entry_ids, successful, errors)
            zf.writestr("_MANIFEST.txt", manifest)
        
        zip_buffer.seek(0)
        zip_bytes = zip_buffer.getvalue()
        
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        archive_filename = f"ABI_BULK_{successful}_entries_{timestamp}.zip"
        
        logger.info(f"Exported {successful}/{len(entry_ids)} entries to {archive_filename}")
        
        return zip_bytes, archive_filename
    
    async def get_abi_preview(
        self,
        entry_id: str,
        message_type: str = ABIMessageType.ENTRY_SUMMARY,
    ) -> Dict[str, Any]:
        """
        Get ABI message preview without generating file.
        
        Args:
            entry_id: Entry UUID
            message_type: Message type
            
        Returns:
            Dict with message details and validation status
        """
        message = await generate_abi_message(self.db, entry_id, message_type)
        
        return {
            "entry_id": entry_id,
            "message_type": message_type,
            "record_count": len(message.records),
            "is_valid": len(message.validation_errors) == 0,
            "validation_errors": message.validation_errors,
            "validation_warnings": message.validation_warnings,
            "preview": message.to_abi_string()[:500] + "..." if len(message.to_abi_string()) > 500 else message.to_abi_string(),
            "full_content": message.to_abi_string(),
        }
    
    def _generate_file_header(self, message: ABIMessage, entry_id: str) -> str:
        """Generate metadata header for ABI file."""
        lines = [
            "*" * 80,
            f"* ABI FILE EXPORT",
            f"* Generated: {datetime.utcnow().isoformat()}Z",
            f"* Entry ID: {entry_id}",
            f"* Message Type: {message.message_type}",
            f"* Records: {len(message.records)}",
            "*" * 80,
            f"* Validation: {'PASSED' if len(message.validation_errors) == 0 else 'WARNINGS/ERRORS'}",
        ]
        
        if message.validation_errors:
            lines.append(f"* ERRORS: {', '.join(message.validation_errors)}")
        if message.validation_warnings:
            lines.append(f"* WARNINGS: {', '.join(message.validation_warnings)}")
        
        lines.append("*" * 80)
        lines.append("")  # Blank line before data
        
        return "\n".join(lines)
    
    def _generate_manifest(
        self,
        entry_ids: List[str],
        successful: int,
        errors: List[str]
    ) -> str:
        """Generate manifest file for bulk export."""
        lines = [
            "=" * 60,
            "ABI BULK EXPORT MANIFEST",
            f"Generated: {datetime.utcnow().isoformat()}Z",
            "=" * 60,
            "",
            f"Total Entries Requested: {len(entry_ids)}",
            f"Successfully Exported: {successful}",
            f"Failed: {len(errors)}",
            "",
        ]
        
        if errors:
            lines.append("ERRORS:")
            lines.extend([f"  - {e}" for e in errors])
            lines.append("")
        
        lines.append("ENTRY IDS:")
        lines.extend([f"  - {eid}" for eid in entry_ids])
        
        return "\n".join(lines)
    
    def _extract_entry_number(self, message: ABIMessage) -> Optional[str]:
        """Extract entry number from ABI message header."""
        from app.services.abi_generator import ABIHeaderRecord, ABIRecordType
        
        for record in message.records:
            if record.record_type == ABIRecordType.HEADER:
                if isinstance(record, ABIHeaderRecord):
                    if record.entry_number:
                        return record.entry_number.strip()
        return None


# Convenience function
async def export_entry_to_abi(
    db: AsyncSession,
    entry_id: str,
    message_type: str = "SE"
) -> Tuple[str, str]:
    """
    Quick export function.
    
    Returns:
        Tuple of (content, filename)
    """
    exporter = ABIFileExporter(db)
    return await exporter.export_entry(entry_id, message_type)

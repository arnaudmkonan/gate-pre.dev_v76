"""
File routing service for routing uploaded files to appropriate extractors.
Implements MIME type, extension, and content-based detection.
"""

import logging
import time
from typing import Optional, Dict, List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert

from app.models.routing_decision import RoutingDecision, RoutingStatus, RoutingMethod
from app.models.raw_file import RawFile
from app.utils.content_sniffer import sniff_file_type, get_canonical_type

logger = logging.getLogger(__name__)

# File type to extractor mapping
FILE_TYPE_TO_EXTRACTOR = {
    "txt": "text_extractor",
    "docx": "docx_extractor",
    "doc": "docx_extractor",
    "xlsx": "spreadsheet_extractor",
    "xls": "spreadsheet_extractor",
    "csv": "spreadsheet_extractor",
    "pptx": "presentation_extractor",
    "ppt": "presentation_extractor",
    "html": "markup_extractor",
    "md": "markup_extractor",
    "json": "markup_extractor",
    "xml": "markup_extractor",
    "yml": "markup_extractor",
    "yaml": "markup_extractor",
    "pdf": "pdf_extractor",
}

# MIME type to file type mapping
MIME_TYPE_TO_FILE_TYPE = {
    "text/plain": "txt",
    "text/markdown": "md",
    "text/csv": "csv",
    "application/json": "json",
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "application/vnd.ms-excel": "xls",
    "application/msword": "doc",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
    "application/vnd.ms-powerpoint": "ppt",
    "text/html": "html",
    "application/xml": "xml",
    "text/xml": "xml",
    "application/x-yaml": "yml",
    "text/x-yaml": "yml",
}


class FileRoutingService:
    """Service for routing files to appropriate extractors."""

    @staticmethod
    async def route_file(
        session: AsyncSession,
        file_id: UUID,
        filename: str,
        file_content: bytes,
        mime_type: Optional[str] = None,
    ) -> Optional[RoutingDecision]:
        """
        Route a file to the appropriate extractor.

        Precedence order:
        1. File extension (highest, confidence 0.95)
        2. MIME type (medium, confidence 0.85)
        3. Content sniffer/magic bytes (confidence varies)
        4. Fallback text extractor (confidence 0.30)

        Args:
            session: Database session
            file_id: ID of the raw file
            filename: Original filename with extension
            file_content: Raw file bytes
            mime_type: Optional MIME type from request

        Returns:
            RoutingDecision object or None if routing fails
        """
        start_time = time.time()

        try:
            # Extract file extension
            extension = None
            if "." in filename:
                extension = filename.rsplit(".", 1)[-1].lower()

            routing_candidates = []

            # Method 1: Extension-based routing (highest priority)
            if extension:
                extractor = FILE_TYPE_TO_EXTRACTOR.get(extension)
                if extractor:
                    routing_candidates.append({
                        "method": RoutingMethod.EXTENSION,
                        "extractor": extractor,
                        "file_type": extension,
                        "confidence": 0.95,
                        "reason": f"Matched by file extension: .{extension}",
                    })

            # Method 2: MIME type-based routing (medium priority)
            if mime_type and mime_type not in routing_candidates:
                mime_lower = mime_type.lower().strip()
                detected_file_type = MIME_TYPE_TO_FILE_TYPE.get(mime_lower)
                if detected_file_type:
                    extractor = FILE_TYPE_TO_EXTRACTOR.get(detected_file_type)
                    if extractor:
                        routing_candidates.append({
                            "method": RoutingMethod.MIME_TYPE,
                            "extractor": extractor,
                            "file_type": detected_file_type,
                            "confidence": 0.85,
                            "reason": f"Matched by MIME type: {mime_type}",
                        })

            # Method 3: Content-based detection using magic bytes
            detected_type, sniff_confidence = sniff_file_type(
                file_content, filename, mime_type
            )
            if detected_type and sniff_confidence > 0.5:
                canonical_type = get_canonical_type(detected_type)
                extractor = FILE_TYPE_TO_EXTRACTOR.get(canonical_type)
                if extractor:
                    routing_candidates.append({
                        "method": RoutingMethod.CONTENT_SNIFFER,
                        "extractor": extractor,
                        "file_type": canonical_type,
                        "confidence": sniff_confidence,
                        "reason": f"Detected by magic bytes/content analysis: {detected_type}",
                    })

            # Select best candidate (highest confidence)
            if not routing_candidates:
                # Fallback: unknown file type
                logger.warning(f"No suitable extractor found for {filename}")
                decision = await FileRoutingService._create_routing_decision(
                    session,
                    file_id,
                    "unknown",
                    "text_extractor",  # fallback to text extractor
                    RoutingMethod.FALLBACK,
                    0.30,
                    "No matching extractor found; using fallback text extractor",
                    RoutingStatus.UNSUPPORTED,
                    error_message="Unsupported file type",
                )
                return decision

            best_candidate = max(routing_candidates, key=lambda x: x["confidence"])
            decision = await FileRoutingService._create_routing_decision(
                session,
                file_id,
                best_candidate["file_type"],
                best_candidate["extractor"],
                best_candidate["method"],
                best_candidate["confidence"],
                best_candidate["reason"],
                RoutingStatus.ROUTED,
            )

            elapsed = time.time() - start_time
            logger.info(
                f"Routed file {filename} (ID: {file_id}) to {best_candidate['extractor']} "
                f"in {elapsed:.2f}s (confidence: {best_candidate['confidence']:.2f})"
            )

            return decision

        except Exception as e:
            logger.error(f"Error routing file {file_id}: {e}")
            decision = await FileRoutingService._create_routing_decision(
                session,
                file_id,
                "unknown",
                "unknown",
                RoutingMethod.FALLBACK,
                0.0,
                f"Routing error: {str(e)}",
                RoutingStatus.FAILED,
                error_message=str(e),
            )
            return decision

    @staticmethod
    async def _create_routing_decision(
        session: AsyncSession,
        file_id: UUID,
        detected_type: str,
        chosen_agent: str,
        routing_method: RoutingMethod,
        confidence: float,
        reason: str,
        status: RoutingStatus = RoutingStatus.ROUTED,
        error_message: Optional[str] = None,
    ) -> RoutingDecision:
        """
        Create and persist a routing decision.

        Args:
            session: Database session
            file_id: ID of raw file
            detected_type: Detected file type
            chosen_agent: Selected extractor/agent
            routing_method: How the decision was made
            confidence: Confidence score (0.0-1.0)
            reason: Explanation of routing decision
            status: Routing status
            error_message: Optional error message

        Returns:
            Persisted RoutingDecision object
        """
        stmt = insert(RoutingDecision).values(
            file_id=file_id,
            detected_type=detected_type,
            chosen_agent=chosen_agent,
            routing_method=routing_method.value,
            confidence=confidence,
            reason=reason,
            status=status.value,
            error_message=error_message,
        ).returning(RoutingDecision)

        result = await session.execute(stmt)
        decision = result.scalar_one()
        await session.commit()

        return decision

    @staticmethod
    async def batch_route_files(
        session: AsyncSession,
        files: List[Dict],
    ) -> List[RoutingDecision]:
        """
        Route multiple files in batch.

        Args:
            session: Database session
            files: List of {file_id, filename, file_content, mime_type} dicts

        Returns:
            List of RoutingDecision objects
        """
        decisions = []
        for file_data in files:
            decision = await FileRoutingService.route_file(
                session,
                file_data["file_id"],
                file_data["filename"],
                file_data["file_content"],
                file_data.get("mime_type"),
            )
            if decision:
                decisions.append(decision)

        return decisions

    @staticmethod
    async def get_supported_types() -> List[str]:
        """Get list of supported file types."""
        return list(FILE_TYPE_TO_EXTRACTOR.keys())

    @staticmethod
    def is_supported_type(file_type: str) -> bool:
        """Check if file type is supported."""
        return file_type.lower() in FILE_TYPE_TO_EXTRACTOR

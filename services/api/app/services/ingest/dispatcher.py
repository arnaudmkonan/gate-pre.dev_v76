import logging
from uuid import UUID
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import IngestFile

logger = logging.getLogger(__name__)

# MIME type to agent mapping
MIME_TO_AGENT_MAP = {
    "text/plain": "text_agent",
    "text/markdown": "text_agent",
    "application/pdf": "pdf_agent",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx_agent",
    "application/msword": "docx_agent",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx_agent",
    "application/vnd.ms-excel": "xlsx_agent",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx_agent",
    "application/vnd.ms-powerpoint": "pptx_agent",
    "text/html": "html_agent",
    "application/json": "json_agent",
    "text/csv": "csv_agent",
    "application/x-yaml": "yaml_agent",
    "text/xml": "xml_agent",
    "application/xml": "xml_agent",
}

# File extension fallback mapping
EXTENSION_TO_AGENT_MAP = {
    "txt": "text_agent",
    "md": "text_agent",
    "markdown": "text_agent",
    "pdf": "pdf_agent",
    "docx": "docx_agent",
    "doc": "docx_agent",
    "xlsx": "xlsx_agent",
    "xls": "xlsx_agent",
    "csv": "csv_agent",
    "pptx": "pptx_agent",
    "ppt": "pptx_agent",
    "html": "html_agent",
    "htm": "html_agent",
    "json": "json_agent",
    "yaml": "yaml_agent",
    "yml": "yaml_agent",
    "xml": "xml_agent",
}


class Dispatcher:
    """Routes files to appropriate ingestion agents based on MIME type or extension."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.fallback_agent = "generic_agent"

    def validate_mime_type(self, mime_type: str) -> bool:
        """Validate if a MIME type is supported."""
        return mime_type.lower() in MIME_TO_AGENT_MAP

    def validate_file_type(self, file_type: str) -> bool:
        """Validate if a file type/extension is supported."""
        return file_type.lower() in EXTENSION_TO_AGENT_MAP

    def route_file(self, file_type: str, mime_type: Optional[str] = None) -> str:
        """
        Route a file to the appropriate agent.

        Args:
            file_type: File extension (e.g., 'pdf', 'docx')
            mime_type: Optional MIME type (e.g., 'application/pdf')

        Returns:
            Agent name for processing
        """
        # Try MIME type first if provided
        if mime_type:
            mime_lower = mime_type.lower()
            if mime_lower in MIME_TO_AGENT_MAP:
                agent = MIME_TO_AGENT_MAP[mime_lower]
                logger.info(f"Routed file to {agent} based on MIME type {mime_type}")
                return agent

        # Try file extension
        file_type_lower = file_type.lower().strip(".")
        if file_type_lower in EXTENSION_TO_AGENT_MAP:
            agent = EXTENSION_TO_AGENT_MAP[file_type_lower]
            logger.info(f"Routed file to {agent} based on file type {file_type}")
            return agent

        # Fallback to generic agent for unknown types
        logger.warning(
            f"Unknown file type {file_type} (MIME: {mime_type}), using fallback agent"
        )
        return self.fallback_agent

    async def record_routing_decision(
        self,
        ingest_file_id: UUID,
        agent_type: str,
        file_type: str,
        mime_type: Optional[str] = None,
    ) -> None:
        """Record routing decision in the database."""
        try:
            # Fetch and update the ingest file
            stmt = select(IngestFile).where(IngestFile.id == ingest_file_id)
            result = await self.session.execute(stmt)
            ingest_file = result.scalar_one_or_none()

            if ingest_file:
                ingest_file.routing_decision = agent_type
                await self.session.commit()
                logger.info(
                    f"Recorded routing decision for file {ingest_file_id}: {agent_type}"
                )
            else:
                logger.warning(f"IngestFile {ingest_file_id} not found for routing decision")
        except Exception as e:
            logger.error(f"Failed to record routing decision: {e}")
            await self.session.rollback()
            raise

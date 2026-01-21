"""
Error router service for classifying and routing errors.
Handles transient vs permanent errors and notifications.
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.errors_raw import ErrorsRaw, ErrorType
from app.repositories.error_repo import ErrorRepository

logger = logging.getLogger(__name__)


class ErrorRouter:
    """Service for routing and managing errors."""

    # Transient error patterns
    TRANSIENT_PATTERNS = [
        "timeout",
        "connection",
        "network",
        "temporarily",
        "unavailable",
        "try again",
        "rate limit",
        "503",
        "502",
        "504",
    ]

    # Permanent error patterns
    PERMANENT_PATTERNS = [
        "invalid",
        "unsupported",
        "corrupt",
        "malformed",
        "unauthorized",
        "forbidden",
        "400",
        "401",
        "403",
        "404",
        "unsupported file type",
    ]

    @staticmethod
    def classify_error(error_message: str, stack_trace: Optional[str] = None) -> str:
        """
        Classify error as transient or permanent.

        Args:
            error_message: Error message
            stack_trace: Optional stack trace

        Returns:
            ErrorType.TRANSIENT or ErrorType.PERMANENT
        """
        combined = (error_message + " " + (stack_trace or "")).lower()

        # Check permanent patterns first (they're more critical)
        for pattern in ErrorRouter.PERMANENT_PATTERNS:
            if pattern in combined:
                return ErrorType.PERMANENT

        # Check transient patterns
        for pattern in ErrorRouter.TRANSIENT_PATTERNS:
            if pattern in combined:
                return ErrorType.TRANSIENT

        # Default to transient (can retry safely)
        return ErrorType.TRANSIENT

    @staticmethod
    async def handle_error(
        session: AsyncSession,
        file_id: UUID,
        agent_id: str,
        error_type: str,
        stack_trace: Optional[str] = None,
        processing_step: str = "unknown",
        max_retries: int = 3,
    ) -> ErrorsRaw:
        """
        Handle and classify error, create error record.

        Args:
            session: Database session
            file_id: File ID
            agent_id: Agent ID
            error_type: Error type/name
            stack_trace: Optional stack trace
            processing_step: Step where error occurred
            max_retries: Max retry attempts

        Returns:
            Created ErrorsRaw record
        """
        try:
            # Classify error
            classification = ErrorRouter.classify_error(error_type, stack_trace)

            # Create error record
            error = await ErrorRepository.create_error(
                session,
                file_id=file_id,
                agent_id=agent_id,
                error_type=error_type,
                stack_trace=stack_trace,
                processing_step=processing_step,
                error_classification=classification,
                max_retries=max_retries,
            )

            logger.info(
                f"Recorded error: file {file_id}, agent {agent_id}, "
                f"type {error_type}, classification {classification}"
            )

            return error

        except Exception as e:
            logger.error(f"Failed to handle error: {e}")
            raise

    @staticmethod
    async def should_retry(error: ErrorsRaw) -> bool:
        """
        Determine if error should be retried.

        Args:
            error: ErrorsRaw record

        Returns:
            True if should retry, False if should move to error queue
        """
        # Check if classification is transient
        if error.error_classification != ErrorType.TRANSIENT:
            return False

        # Check if retry limit reached
        if error.retry_count >= error.max_retries:
            return False

        return True

    @staticmethod
    async def move_to_error_queue(
        session: AsyncSession,
        error_id: UUID,
    ) -> Optional[ErrorsRaw]:
        """
        Move error to permanent error queue (no more retries).

        Args:
            session: Database session
            error_id: Error ID

        Returns:
            Updated ErrorsRaw record
        """
        try:
            error = await ErrorRepository.get_error_by_id(session, error_id)
            if not error:
                return None

            # Mark as permanent
            error.error_classification = ErrorType.PERMANENT
            await session.commit()

            logger.info(f"Moved error {error_id} to error queue")
            return error

        except Exception as e:
            await session.rollback()
            logger.error(f"Failed to move error to queue: {e}")
            raise

    @staticmethod
    async def notify_error(
        error: ErrorsRaw,
        channel: str = "email",
    ) -> bool:
        """
        Send notification for permanent error.

        Args:
            error: ErrorsRaw record
            channel: Notification channel (email, webhook, etc.)

        Returns:
            True if notification sent successfully
        """
        try:
            # TODO: Integrate with notification service
            # For now, just log
            logger.warning(
                f"Error notification (via {channel}): "
                f"File {error.file_id}, Agent {error.agent_id}, "
                f"Type {error.error_type}, Step {error.processing_step}"
            )

            return True

        except Exception as e:
            logger.error(f"Failed to notify error: {e}")
            return False

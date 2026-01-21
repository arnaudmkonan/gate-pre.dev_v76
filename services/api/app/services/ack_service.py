"""
Service for managing agent acknowledgements.
Tracks agent processing status and maintains audit trail.
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_ack import AgentAck, AgentAckStatus

logger = logging.getLogger(__name__)


class AckService:
    """Service for managing agent acknowledgements."""

    @staticmethod
    async def create_ack(
        session: AsyncSession,
        file_id: UUID,
        agent_id: str,
    ) -> AgentAck:
        """
        Create initial acknowledgement record when file is dispatched to agent.

        Args:
            session: Database session
            file_id: File/job ID
            agent_id: Agent ID being dispatched to

        Returns:
            Created AgentAck record
        """
        try:
            ack = AgentAck(
                file_id=file_id,
                agent_id=agent_id,
                status=AgentAckStatus.PENDING,
                dispatched_at=datetime.now(timezone.utc),
            )
            session.add(ack)
            await session.commit()
            logger.info(f"Created ACK for file {file_id} → agent {agent_id}")
            return ack
        except Exception as e:
            await session.rollback()
            logger.error(
                f"Failed to create ACK for file {file_id}, agent {agent_id}: {e}"
            )
            raise

    @staticmethod
    async def get_ack(
        session: AsyncSession,
        file_id: UUID,
        agent_id: str,
    ) -> Optional[AgentAck]:
        """
        Get acknowledgement record for a file-agent pair.

        Args:
            session: Database session
            file_id: File/job ID
            agent_id: Agent ID

        Returns:
            AgentAck record or None if not found
        """
        try:
            query = select(AgentAck).where(
                (AgentAck.file_id == file_id) & (AgentAck.agent_id == agent_id)
            )
            result = await session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to get ACK for file {file_id}, agent {agent_id}: {e}")
            raise

    @staticmethod
    async def get_ack_by_file(
        session: AsyncSession,
        file_id: UUID,
    ) -> Optional[AgentAck]:
        """
        Get latest acknowledgement for a file (most recent dispatch).

        Args:
            session: Database session
            file_id: File/job ID

        Returns:
            AgentAck record or None
        """
        try:
            query = (
                select(AgentAck)
                .where(AgentAck.file_id == file_id)
                .order_by(AgentAck.created_at.desc())
                .limit(1)
            )
            result = await session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to get latest ACK for file {file_id}: {e}")
            raise

    @staticmethod
    async def acknowledge(
        session: AsyncSession,
        file_id: UUID,
        agent_id: str,
        metadata: Optional[dict] = None,
    ) -> Optional[AgentAck]:
        """
        Record agent acknowledgement of file dispatch.

        Args:
            session: Database session
            file_id: File/job ID
            agent_id: Agent ID
            metadata: Optional metadata from agent

        Returns:
            Updated AgentAck record
        """
        try:
            ack = await AckService.get_ack(session, file_id, agent_id)
            if not ack:
                logger.warning(
                    f"No pending ACK found for file {file_id}, agent {agent_id}"
                )
                return None

            ack.status = AgentAckStatus.ACKNOWLEDGED
            ack.ack_timestamp = datetime.now(timezone.utc)
            ack.agent_metadata = metadata or {}

            await session.commit()
            logger.info(f"Acknowledged file {file_id} by agent {agent_id}")
            return ack
        except Exception as e:
            await session.rollback()
            logger.error(
                f"Failed to acknowledge file {file_id}, agent {agent_id}: {e}"
            )
            raise

    @staticmethod
    async def mark_completed(
        session: AsyncSession,
        file_id: UUID,
        agent_id: str,
        metadata: Optional[dict] = None,
    ) -> Optional[AgentAck]:
        """
        Mark acknowledgement as completed when agent finishes processing.

        Args:
            session: Database session
            file_id: File/job ID
            agent_id: Agent ID
            metadata: Optional completion metadata from agent

        Returns:
            Updated AgentAck record
        """
        try:
            ack = await AckService.get_ack(session, file_id, agent_id)
            if not ack:
                logger.warning(
                    f"No ACK found for file {file_id}, agent {agent_id}"
                )
                return None

            ack.status = AgentAckStatus.COMPLETED
            ack.completed_at = datetime.now(timezone.utc)
            ack.agent_metadata = metadata or ack.agent_metadata

            await session.commit()
            logger.info(f"Marked file {file_id} as completed by agent {agent_id}")
            return ack
        except Exception as e:
            await session.rollback()
            logger.error(
                f"Failed to mark file {file_id} completed for agent {agent_id}: {e}"
            )
            raise

    @staticmethod
    async def mark_failed(
        session: AsyncSession,
        file_id: UUID,
        agent_id: str,
        error_details: Optional[dict] = None,
    ) -> Optional[AgentAck]:
        """
        Mark acknowledgement as failed if agent encounters error.

        Args:
            session: Database session
            file_id: File/job ID
            agent_id: Agent ID
            error_details: Optional error information from agent

        Returns:
            Updated AgentAck record
        """
        try:
            ack = await AckService.get_ack(session, file_id, agent_id)
            if not ack:
                logger.warning(
                    f"No ACK found for file {file_id}, agent {agent_id}"
                )
                return None

            ack.status = AgentAckStatus.FAILED
            ack.completed_at = datetime.now(timezone.utc)
            ack.error_details = error_details or {}

            await session.commit()
            logger.error(f"Marked file {file_id} as failed for agent {agent_id}")
            return ack
        except Exception as e:
            await session.rollback()
            logger.error(
                f"Failed to mark file {file_id} failed for agent {agent_id}: {e}"
            )
            raise

    @staticmethod
    async def get_pending_acks(
        session: AsyncSession,
        agent_id: Optional[str] = None,
    ) -> list:
        """
        Get all pending acknowledgements, optionally filtered by agent.

        Args:
            session: Database session
            agent_id: Optional agent ID filter

        Returns:
            List of pending AgentAck records
        """
        try:
            query = select(AgentAck).where(AgentAck.status == AgentAckStatus.PENDING)
            if agent_id:
                query = query.where(AgentAck.agent_id == agent_id)
            result = await session.execute(query)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Failed to get pending ACKs: {e}")
            raise

    @staticmethod
    async def get_ack_history(
        session: AsyncSession,
        file_id: UUID,
    ) -> list:
        """
        Get complete ACK history for a file (all agent dispatches).

        Args:
            session: Database session
            file_id: File/job ID

        Returns:
            List of AgentAck records ordered by dispatch time
        """
        try:
            query = (
                select(AgentAck)
                .where(AgentAck.file_id == file_id)
                .order_by(AgentAck.dispatched_at)
            )
            result = await session.execute(query)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Failed to get ACK history for file {file_id}: {e}")
            raise

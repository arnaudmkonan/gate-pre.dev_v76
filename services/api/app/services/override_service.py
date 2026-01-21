"""
Service for managing admin overrides and file reprocessing.
Handles permission checks, audit logging, and requeue operations.
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.overrides_audit import OverridesAudit
from app.services.ack_service import AckService
from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)


class OverrideService:
    """Service for managing admin overrides."""

    @staticmethod
    async def can_override(session: AsyncSession, admin_id: str) -> bool:
        """
        Validate admin permissions to override file routing.

        Args:
            session: Database session
            admin_id: Admin user ID

        Returns:
            True if admin has override permissions
        """
        # TODO: Integrate with AuthService for role-based access control
        # For now, assume any non-empty admin_id has permission
        if not admin_id or not admin_id.strip():
            return False
        return True

    @staticmethod
    async def record_override_audit(
        session: AsyncSession,
        admin_id: str,
        file_id: UUID,
        prev_agent_id: Optional[str],
        new_agent_id: str,
        reason: Optional[str] = None,
        prev_routing_decision: Optional[str] = None,
        decision_confidence: Optional[float] = None,
    ) -> OverridesAudit:
        """
        Record admin override in audit table.

        Args:
            session: Database session
            admin_id: Admin user ID
            file_id: File being overridden
            prev_agent_id: Previous agent ID (if any)
            new_agent_id: New agent ID
            reason: Optional reason for override
            prev_routing_decision: Previous routing method
            decision_confidence: Confidence of previous decision

        Returns:
            Created OverridesAudit record
        """
        from sqlalchemy import select
        from app.models.agent_registry import AgentRegistry

        try:
            # Validate new_agent_id exists in agent_registry
            query = select(AgentRegistry).where(
                AgentRegistry.agent_id == new_agent_id
            )
            result = await session.execute(query)
            agent = result.scalar_one_or_none()

            if not agent:
                raise ValueError(f"Agent not found: {new_agent_id}")

            # Validate prev_agent_id if provided
            if prev_agent_id:
                query = select(AgentRegistry).where(
                    AgentRegistry.agent_id == prev_agent_id
                )
                result = await session.execute(query)
                prev_agent = result.scalar_one_or_none()
                if not prev_agent:
                    logger.warning(f"Previous agent not found: {prev_agent_id}")

            audit = OverridesAudit(
                admin_id=admin_id,
                file_id=file_id,
                prev_agent_id=prev_agent_id,
                new_agent_id=new_agent_id,
                reason=reason,
                prev_routing_decision=prev_routing_decision,
                decision_confidence=decision_confidence,
            )
            session.add(audit)
            await session.commit()
            logger.info(
                f"Recorded override: file {file_id} from agent {prev_agent_id} "
                f"to {new_agent_id} by admin {admin_id}"
            )
            return audit
        except Exception as e:
            await session.rollback()
            logger.error(f"Failed to record override audit: {e}")
            raise

    @staticmethod
    async def requeue_file(
        session: AsyncSession,
        file_id: UUID,
        new_agent_id: str,
        storage_path: str,
    ) -> dict:
        """
        Requeue file for processing by new agent.

        Args:
            session: Database session
            file_id: File to requeue
            new_agent_id: Target agent ID
            storage_path: Path to file in storage

        Returns:
            Dict with requeue result
        """
        try:
            # Create new ACK record for new agent
            ack = await AckService.create_ack(
                session,
                file_id=file_id,
                agent_id=new_agent_id,
            )

            # Dispatch to Celery
            task_result = celery_app.send_task(
                "app.workers.dispatch.dispatch_to_agent",
                args=(str(file_id), new_agent_id, storage_path),
                countdown=0,
            )

            logger.info(
                f"Requeued file {file_id} to agent {new_agent_id}, "
                f"task_id: {task_result.id}"
            )

            return {
                "status": "success",
                "file_id": str(file_id),
                "agent_id": new_agent_id,
                "ack_id": str(ack.id),
                "task_id": task_result.id,
            }
        except Exception as e:
            logger.error(f"Failed to requeue file {file_id}: {e}")
            raise

    @staticmethod
    async def override_and_requeue(
        session: AsyncSession,
        admin_id: str,
        file_id: UUID,
        new_agent_id: str,
        storage_path: str,
        prev_agent_id: Optional[str] = None,
        reason: Optional[str] = None,
        prev_routing_decision: Optional[str] = None,
        decision_confidence: Optional[float] = None,
    ) -> dict:
        """
        Complete override operation: record audit and requeue file.

        Args:
            session: Database session
            admin_id: Admin user ID
            file_id: File to override
            new_agent_id: Target agent ID
            storage_path: Path to file in storage
            prev_agent_id: Previous agent ID
            reason: Override reason
            prev_routing_decision: Previous routing method
            decision_confidence: Previous decision confidence

        Returns:
            Dict with override and requeue results
        """
        try:
            # Check permissions
            can_override = await OverrideService.can_override(session, admin_id)
            if not can_override:
                raise PermissionError(f"Admin {admin_id} not authorized to override")

            # Record audit
            audit = await OverrideService.record_override_audit(
                session,
                admin_id=admin_id,
                file_id=file_id,
                prev_agent_id=prev_agent_id,
                new_agent_id=new_agent_id,
                reason=reason,
                prev_routing_decision=prev_routing_decision,
                decision_confidence=decision_confidence,
            )

            # Requeue file
            requeue_result = await OverrideService.requeue_file(
                session,
                file_id=file_id,
                new_agent_id=new_agent_id,
                storage_path=storage_path,
            )

            result = {
                "status": "success",
                "audit_id": str(audit.id),
                **requeue_result,
            }

            logger.info(f"Override completed for file {file_id}: {result}")
            return result

        except PermissionError as e:
            logger.warning(f"Permission denied for override by {admin_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to perform override for file {file_id}: {e}")
            raise

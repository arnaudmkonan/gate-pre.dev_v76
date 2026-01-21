"""
Celery task for dispatching files to ingestion agents.
Handles agent selection, task dispatching, and acknowledgement tracking.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from celery import Task
from sqlalchemy import select

from app.core.celery_app import celery_app
from app.core.database import AsyncSessionLocal
from app.models.agent_registry import AgentRegistry
from app.services.ack_service import AckService

logger = logging.getLogger(__name__)


class CallbackTask(Task):
    """Task class with callback support for logging."""

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure."""
        logger.error(f"Task {task_id} failed: {exc}")

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Handle task retry."""
        logger.warning(f"Task {task_id} retrying: {exc}")

    def on_success(self, result, task_id, args, kwargs):
        """Handle task success."""
        logger.info(f"Task {task_id} completed successfully")


@celery_app.task(
    bind=True,
    base=CallbackTask,
    autoretry_for=(Exception,),
    max_retries=3,
    default_retry_delay=10,
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    name="app.workers.dispatch.dispatch_to_agent",
)
async def dispatch_to_agent(
    self,
    file_id: str,
    agent_id: str,
    storage_path: str,
) -> dict:
    """
    Dispatch file to ingestion agent.

    Steps:
    1. Lookup agent from registry
    2. Call agent's handler function
    3. Update ACK status to ACKNOWLEDGED
    4. Log dispatch result

    Args:
        self: Celery task self
        file_id: File/job ID (UUID string)
        agent_id: Target agent ID
        storage_path: Path to file in storage

    Returns:
        Dict with dispatch status and result
    """
    from uuid import UUID

    try:
        async with AsyncSessionLocal() as session:
            # Lookup agent
            query = select(AgentRegistry).where(
                AgentRegistry.agent_id == agent_id
            )
            result = await session.execute(query)
            agent = result.scalar_one_or_none()

            if not agent:
                logger.error(f"Agent not found: {agent_id}")
                raise ValueError(f"Agent not found: {agent_id}")

            logger.info(
                f"Dispatching file {file_id} to agent {agent_id} "
                f"(handler: {agent.handler_name})"
            )

            # Call agent's handler
            # The handler should be a task or callable in the same Celery app
            handler_task_name = f"app.workers.{agent.handler_name}"

            try:
                # Dispatch to agent handler asynchronously
                handler_result = celery_app.send_task(
                    handler_task_name,
                    args=(file_id, storage_path),
                    countdown=0,
                )

                logger.info(f"Dispatched to handler: {handler_task_name}, task_id: {handler_result.id}")

                # Update ACK to ACKNOWLEDGED
                await AckService.acknowledge(
                    session,
                    file_id=UUID(file_id),
                    agent_id=agent_id,
                    metadata={
                        "dispatched_at": datetime.now(timezone.utc).isoformat(),
                        "handler_task_id": handler_result.id,
                    },
                )

                return {
                    "status": "success",
                    "file_id": file_id,
                    "agent_id": agent_id,
                    "handler_task_id": handler_result.id,
                }

            except Exception as e:
                logger.error(f"Failed to dispatch to handler {handler_task_name}: {e}")

                # Update ACK to FAILED
                await AckService.mark_failed(
                    session,
                    file_id=UUID(file_id),
                    agent_id=agent_id,
                    error_details={
                        "error": str(e),
                        "step": "handler_dispatch",
                    },
                )

                raise

    except Exception as e:
        logger.error(f"Failed to dispatch file {file_id} to agent {agent_id}: {e}")
        raise self.retry(exc=e, countdown=10)


@celery_app.task(
    bind=True,
    base=CallbackTask,
    name="app.workers.dispatch.bulk_dispatch",
)
def bulk_dispatch(
    self,
    file_ids: list[str],
    agent_id: str,
) -> dict:
    """
    Dispatch multiple files to same agent.
    Useful for batch processing or manual admin operations.

    Args:
        self: Celery task self
        file_ids: List of file IDs
        agent_id: Target agent ID

    Returns:
        Dict with bulk dispatch results
    """
    results = {
        "total": len(file_ids),
        "successful": 0,
        "failed": 0,
        "file_results": [],
    }

    for file_id in file_ids:
        try:
            # Dispatch each file individually
            dispatch_to_agent.apply_async(
                args=(file_id, agent_id, f"uploads/{file_id}"),
                countdown=0,
            )
            results["successful"] += 1
            results["file_results"].append({"file_id": file_id, "status": "dispatched"})
        except Exception as e:
            logger.error(f"Failed to dispatch file {file_id}: {e}")
            results["failed"] += 1
            results["file_results"].append(
                {"file_id": file_id, "status": "failed", "error": str(e)}
            )

    logger.info(f"Bulk dispatch: {results['successful']}/{results['total']} successful")
    return results

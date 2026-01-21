"""Retry policy service for per-pipeline configuration."""

import logging
import random
from datetime import datetime, timezone, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.retry_policy import RetryPolicy
from app.schemas.retry_policy import (
    RetryPolicyCreate,
    RetryPolicyResponse,
    RetryPolicyUpdate,
    RetryCalculation,
)

logger = logging.getLogger(__name__)


class RetryPolicyService:
    """Service for managing retry policies."""

    @staticmethod
    async def create_policy(
        session: AsyncSession,
        policy: RetryPolicyCreate,
    ) -> RetryPolicyResponse:
        """
        Create a new retry policy for a pipeline.

        Args:
            session: Database session
            policy: RetryPolicyCreate schema

        Returns:
            Created RetryPolicyResponse
        """
        try:
            retry_policy = RetryPolicy(
                pipeline_id=policy.pipeline_id,
                policy_type=policy.policy_type,
                max_attempts=policy.max_attempts,
                base_delay_ms=policy.base_delay_ms,
                max_delay_ms=policy.max_delay_ms,
                jitter=policy.jitter,
            )

            session.add(retry_policy)
            await session.commit()
            await session.refresh(retry_policy)

            logger.info(f"Created retry policy for pipeline {policy.pipeline_id}")
            return RetryPolicyService._to_response(retry_policy)

        except Exception as e:
            await session.rollback()
            logger.error(f"Error creating retry policy: {e}")
            raise

    @staticmethod
    async def get_policy(
        session: AsyncSession,
        pipeline_id: UUID,
    ) -> Optional[RetryPolicyResponse]:
        """Get retry policy for a pipeline."""
        try:
            result = await session.execute(
                select(RetryPolicy).where(RetryPolicy.pipeline_id == pipeline_id)
            )
            policy = result.scalar_one_or_none()
            return RetryPolicyService._to_response(policy) if policy else None

        except Exception as e:
            logger.error(f"Error getting retry policy: {e}")
            raise

    @staticmethod
    async def update_policy(
        session: AsyncSession,
        pipeline_id: UUID,
        update: RetryPolicyUpdate,
    ) -> RetryPolicyResponse:
        """Update a retry policy."""
        try:
            result = await session.execute(
                select(RetryPolicy).where(RetryPolicy.pipeline_id == pipeline_id)
            )
            policy = result.scalar_one_or_none()

            if not policy:
                raise ValueError(f"Retry policy not found for pipeline {pipeline_id}")

            # Update fields
            if update.policy_type is not None:
                policy.policy_type = update.policy_type
            if update.max_attempts is not None:
                policy.max_attempts = update.max_attempts
            if update.base_delay_ms is not None:
                policy.base_delay_ms = update.base_delay_ms
            if update.max_delay_ms is not None:
                policy.max_delay_ms = update.max_delay_ms
            if update.jitter is not None:
                policy.jitter = update.jitter

            policy.updated_at = datetime.now(timezone.utc)

            await session.commit()
            await session.refresh(policy)

            logger.info(f"Updated retry policy for pipeline {pipeline_id}")
            return RetryPolicyService._to_response(policy)

        except Exception as e:
            await session.rollback()
            logger.error(f"Error updating retry policy: {e}")
            raise

    @staticmethod
    async def delete_policy(
        session: AsyncSession,
        pipeline_id: UUID,
    ) -> None:
        """Delete a retry policy."""
        try:
            result = await session.execute(
                select(RetryPolicy).where(RetryPolicy.pipeline_id == pipeline_id)
            )
            policy = result.scalar_one_or_none()

            if not policy:
                raise ValueError(f"Retry policy not found for pipeline {pipeline_id}")

            await session.delete(policy)
            await session.commit()

            logger.info(f"Deleted retry policy for pipeline {pipeline_id}")

        except Exception as e:
            await session.rollback()
            logger.error(f"Error deleting retry policy: {e}")
            raise

    @staticmethod
    def calculate_retry_delay(
        policy: RetryPolicyResponse,
        attempt_number: int,
    ) -> RetryCalculation:
        """
        Calculate the retry delay based on policy and attempt number.

        Args:
            policy: RetryPolicyResponse
            attempt_number: Current attempt number (1-based)

        Returns:
            RetryCalculation with delay_ms and next_retry_at
        """
        if policy.policy_type == "exponential":
            # Exponential backoff: base_delay * (2 ^ (attempt - 1))
            delay_ms = policy.base_delay_ms * (2 ** (attempt_number - 1))
        elif policy.policy_type == "linear":
            # Linear backoff: base_delay * attempt
            delay_ms = policy.base_delay_ms * attempt_number
        elif policy.policy_type == "fixed":
            # Fixed delay
            delay_ms = policy.base_delay_ms
        else:
            # No retry
            delay_ms = 0

        # Cap at max_delay_ms
        delay_ms = min(delay_ms, policy.max_delay_ms)

        # Apply jitter if enabled
        if policy.jitter and delay_ms > 0:
            jitter = random.randint(0, int(delay_ms * 0.1))  # Up to 10% jitter
            delay_ms = delay_ms + jitter

        now = datetime.now(timezone.utc)
        next_retry_at = now + timedelta(milliseconds=delay_ms)

        return RetryCalculation(
            attempt_number=attempt_number,
            delay_ms=delay_ms,
            next_retry_at=next_retry_at,
            policy_type=policy.policy_type,
        )

    @staticmethod
    def _to_response(policy: RetryPolicy) -> RetryPolicyResponse:
        """Convert RetryPolicy to RetryPolicyResponse."""
        return RetryPolicyResponse(
            id=policy.id,
            pipeline_id=policy.pipeline_id,
            policy_type=policy.policy_type,
            max_attempts=policy.max_attempts,
            base_delay_ms=policy.base_delay_ms,
            max_delay_ms=policy.max_delay_ms,
            jitter=policy.jitter,
            created_at=policy.created_at,
            updated_at=policy.updated_at,
        )

"""Pydantic schemas for retry policy endpoints."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class RetryPolicyCreate(BaseModel):
    """Create a retry policy."""

    pipeline_id: UUID
    policy_type: str = "exponential"  # exponential, fixed, linear, none
    max_attempts: int = 3
    base_delay_ms: int = 1000
    max_delay_ms: int = 60000
    jitter: bool = True


class RetryPolicyResponse(BaseModel):
    """Response for a retry policy."""

    id: UUID
    pipeline_id: UUID
    policy_type: str
    max_attempts: int
    base_delay_ms: int
    max_delay_ms: int
    jitter: bool
    created_at: datetime
    updated_at: datetime


class RetryPolicyUpdate(BaseModel):
    """Update a retry policy."""

    policy_type: Optional[str] = None
    max_attempts: Optional[int] = None
    base_delay_ms: Optional[int] = None
    max_delay_ms: Optional[int] = None
    jitter: Optional[bool] = None


class RetryCalculation(BaseModel):
    """Calculation of retry delay."""

    attempt_number: int
    delay_ms: int
    next_retry_at: datetime
    policy_type: str

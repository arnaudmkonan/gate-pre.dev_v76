"""Pydantic schemas for audit log responses."""

from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID

from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    """Response model for an audit log entry."""

    audit_id: str
    resource_type: str
    resource_id: str
    action: str
    actor_id: Optional[str] = None
    timestamp: datetime
    changes: Optional[Dict[str, Any]] = None


class AuditExportRequest(BaseModel):
    """Request model for audit export."""

    resource_id: Optional[str] = None
    action: Optional[str] = None
    resource_type: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    limit: int = 100
    offset: int = 0


class AuditExportResponse(BaseModel):
    """Response model for audit export."""

    logs: List[AuditLogResponse]
    total_count: int
    limit: int
    offset: int

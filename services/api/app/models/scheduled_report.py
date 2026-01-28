"""
Scheduled Reports Models and Service.

Models for automated report scheduling and generation.

Task 7.4 from ROADMAP_FULL_WORKFLOW.md
"""
from datetime import datetime, date, timezone, timedelta
from enum import Enum
from typing import Optional, List
from uuid import UUID

from sqlalchemy import Column, String, DateTime, Date, ForeignKey, Integer, Text, Boolean, Index
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB, ARRAY

from app.models.base import BaseModel


class ReportFrequency(str, Enum):
    """Report schedule frequency."""
    DAILY = "daily"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


class ReportType(str, Enum):
    """Type of scheduled report."""
    ENTRY_SUMMARY = "entry_summary"
    DUTY_SUMMARY = "duty_summary"
    COMPLIANCE_SCORE = "compliance_score"
    CLIENT_ACTIVITY = "client_activity"
    ISF_COMPLIANCE = "isf_compliance"
    ANNUAL_SUMMARY = "annual_summary"
    CUSTOM = "custom"


class ReportStatus(str, Enum):
    """Report generation status."""
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class ScheduledReport(BaseModel):
    """
    Scheduled report configuration.
    """
    __tablename__ = "scheduled_reports"
    
    # Report configuration
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    report_type = Column(String(50), nullable=False)
    
    # Schedule
    frequency = Column(String(20), nullable=False)
    day_of_week = Column(Integer, nullable=True)  # 0=Monday for weekly
    day_of_month = Column(Integer, nullable=True)  # For monthly
    time_of_day = Column(String(5), nullable=True, default="08:00")  # HH:MM
    timezone = Column(String(50), default="America/New_York")
    
    # Scope
    client_id = Column(PGUUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=True)
    filters = Column(JSONB, nullable=True, default={})  # Additional filters
    
    # Recipients
    recipients = Column(ARRAY(String), nullable=False, default=[])  # Email addresses
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    next_run_at = Column(DateTime(timezone=True), nullable=True)
    
    # Metadata
    created_by = Column(String(100), nullable=True)
    
    __table_args__ = (
        Index("ix_scheduled_reports_type", "report_type"),
        Index("ix_scheduled_reports_next_run", "next_run_at"),
        Index("ix_scheduled_reports_active", "is_active"),
    )
    
    def calculate_next_run(self):
        """Calculate next run time based on frequency."""
        now = datetime.now(tz=timezone.utc)
        
        if self.frequency == ReportFrequency.DAILY.value:
            next_run = now + timedelta(days=1)
        elif self.frequency == ReportFrequency.WEEKLY.value:
            days_ahead = (self.day_of_week or 0) - now.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            next_run = now + timedelta(days=days_ahead)
        elif self.frequency == ReportFrequency.BIWEEKLY.value:
            next_run = now + timedelta(days=14)
        elif self.frequency == ReportFrequency.MONTHLY.value:
            # Next month, same day
            if now.month == 12:
                next_run = now.replace(year=now.year + 1, month=1, day=self.day_of_month or 1)
            else:
                next_run = now.replace(month=now.month + 1, day=self.day_of_month or 1)
        elif self.frequency == ReportFrequency.QUARTERLY.value:
            next_run = now + timedelta(days=90)
        elif self.frequency == ReportFrequency.ANNUAL.value:
            next_run = now.replace(year=now.year + 1)
        else:
            next_run = now + timedelta(days=1)
        
        self.next_run_at = next_run
    
    def to_dict(self):
        return {
            "id": str(self.id),
            "name": self.name,
            "description": self.description,
            "report_type": self.report_type,
            "frequency": self.frequency,
            "day_of_week": self.day_of_week,
            "day_of_month": self.day_of_month,
            "time_of_day": self.time_of_day,
            "timezone": self.timezone,
            "client_id": str(self.client_id) if self.client_id else None,
            "recipients": self.recipients,
            "is_active": self.is_active,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "next_run_at": self.next_run_at.isoformat() if self.next_run_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class GeneratedReport(BaseModel):
    """
    History of generated reports.
    """
    __tablename__ = "generated_reports"
    
    schedule_id = Column(PGUUID(as_uuid=True), ForeignKey("scheduled_reports.id", ondelete="CASCADE"), nullable=True)
    
    # Report info
    name = Column(String(200), nullable=False)
    report_type = Column(String(50), nullable=False)
    
    # Status
    status = Column(String(20), default=ReportStatus.PENDING.value, nullable=False)
    
    # Timing
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Result
    file_path = Column(String(500), nullable=True)  # Path to stored report
    file_size = Column(Integer, nullable=True)
    row_count = Column(Integer, nullable=True)
    
    # Error tracking
    error_message = Column(Text, nullable=True)
    
    # Recipients
    recipients = Column(ARRAY(String), nullable=True, default=[])
    sent_at = Column(DateTime(timezone=True), nullable=True)
    
    # Parameters used
    parameters = Column(JSONB, nullable=True, default={})
    
    __table_args__ = (
        Index("ix_generated_reports_schedule", "schedule_id"),
        Index("ix_generated_reports_status", "status"),
        Index("ix_generated_reports_type", "report_type"),
    )
    
    def to_dict(self):
        return {
            "id": str(self.id),
            "schedule_id": str(self.schedule_id) if self.schedule_id else None,
            "name": self.name,
            "report_type": self.report_type,
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "file_path": self.file_path,
            "file_size": self.file_size,
            "row_count": self.row_count,
            "error_message": self.error_message,
            "recipients": self.recipients,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

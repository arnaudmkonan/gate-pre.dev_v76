"""
Scheduled Reports Service.

Manages scheduled report configuration and execution.

Task 7.4 from ROADMAP_FULL_WORKFLOW.md
"""
from datetime import datetime, date, timezone, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scheduled_report import (
    ScheduledReport, GeneratedReport,
    ReportFrequency, ReportType, ReportStatus
)


class ScheduledReportService:
    """Service for managing scheduled reports."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_schedule(
        self,
        name: str,
        report_type: str,
        frequency: str,
        recipients: List[str],
        client_id: Optional[UUID] = None,
        day_of_week: Optional[int] = None,
        day_of_month: Optional[int] = None,
        time_of_day: str = "08:00",
        timezone: str = "America/New_York",
        filters: Optional[Dict] = None,
        description: Optional[str] = None,
        created_by: Optional[str] = None,
    ) -> ScheduledReport:
        """Create a new report schedule."""
        schedule = ScheduledReport(
            name=name,
            description=description,
            report_type=report_type,
            frequency=frequency,
            day_of_week=day_of_week,
            day_of_month=day_of_month,
            time_of_day=time_of_day,
            timezone=timezone,
            client_id=client_id,
            filters=filters or {},
            recipients=recipients,
            is_active=True,
            created_by=created_by,
        )
        
        # Calculate first run
        schedule.calculate_next_run()
        
        self.db.add(schedule)
        await self.db.commit()
        await self.db.refresh(schedule)
        
        return schedule
    
    async def get_schedule(self, schedule_id: UUID) -> Optional[ScheduledReport]:
        """Get schedule by ID."""
        query = select(ScheduledReport).where(ScheduledReport.id == schedule_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def list_schedules(
        self,
        client_id: Optional[UUID] = None,
        is_active: Optional[bool] = None,
        report_type: Optional[str] = None,
    ) -> List[ScheduledReport]:
        """List report schedules."""
        query = select(ScheduledReport)
        
        conditions = []
        if client_id:
            conditions.append(ScheduledReport.client_id == client_id)
        if is_active is not None:
            conditions.append(ScheduledReport.is_active == is_active)
        if report_type:
            conditions.append(ScheduledReport.report_type == report_type)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        query = query.order_by(ScheduledReport.name)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def update_schedule(
        self,
        schedule_id: UUID,
        updates: Dict[str, Any],
    ) -> ScheduledReport:
        """Update a schedule."""
        schedule = await self.get_schedule(schedule_id)
        if not schedule:
            raise ValueError(f"Schedule {schedule_id} not found")
        
        for key, value in updates.items():
            if hasattr(schedule, key):
                setattr(schedule, key, value)
        
        # Recalculate next run if frequency changed
        if "frequency" in updates or "day_of_week" in updates or "day_of_month" in updates:
            schedule.calculate_next_run()
        
        await self.db.commit()
        await self.db.refresh(schedule)
        
        return schedule
    
    async def pause_schedule(self, schedule_id: UUID) -> ScheduledReport:
        """Pause a schedule."""
        return await self.update_schedule(schedule_id, {"is_active": False})
    
    async def resume_schedule(self, schedule_id: UUID) -> ScheduledReport:
        """Resume a paused schedule."""
        schedule = await self.update_schedule(schedule_id, {"is_active": True})
        schedule.calculate_next_run()
        await self.db.commit()
        await self.db.refresh(schedule)
        return schedule
    
    async def delete_schedule(self, schedule_id: UUID) -> None:
        """Delete a schedule."""
        schedule = await self.get_schedule(schedule_id)
        if schedule:
            await self.db.delete(schedule)
            await self.db.commit()
    
    async def get_due_schedules(self) -> List[ScheduledReport]:
        """Get schedules that are due to run."""
        now = datetime.now(tz=timezone.utc)
        
        query = select(ScheduledReport).where(
            and_(
                ScheduledReport.is_active == True,
                ScheduledReport.next_run_at <= now,
            )
        )
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def run_schedule(
        self,
        schedule_id: UUID,
    ) -> GeneratedReport:
        """Run a scheduled report."""
        schedule = await self.get_schedule(schedule_id)
        if not schedule:
            raise ValueError(f"Schedule {schedule_id} not found")
        
        # Create generated report record
        generated = GeneratedReport(
            schedule_id=schedule_id,
            name=schedule.name,
            report_type=schedule.report_type,
            status=ReportStatus.GENERATING.value,
            started_at=datetime.now(tz=timezone.utc),
            recipients=schedule.recipients,
            parameters={
                "client_id": str(schedule.client_id) if schedule.client_id else None,
                "filters": schedule.filters,
            },
        )
        
        self.db.add(generated)
        await self.db.commit()
        
        try:
            # Generate the report based on type
            result = await self._generate_report(schedule, generated)
            
            generated.status = ReportStatus.COMPLETED.value
            generated.completed_at = datetime.now(tz=timezone.utc)
            generated.row_count = result.get("row_count", 0)
            generated.file_path = result.get("file_path")
            generated.file_size = result.get("file_size")
            
            # Update schedule
            schedule.last_run_at = datetime.now(tz=timezone.utc)
            schedule.calculate_next_run()
            
        except Exception as e:
            generated.status = ReportStatus.FAILED.value
            generated.completed_at = datetime.now(tz=timezone.utc)
            generated.error_message = str(e)
        
        await self.db.commit()
        await self.db.refresh(generated)
        
        return generated
    
    async def _generate_report(
        self,
        schedule: ScheduledReport,
        generated: GeneratedReport,
    ) -> Dict[str, Any]:
        """Generate report based on type."""
        # Import services
        from app.services.analytics_service import (
            AnalyticsService, ComplianceScoreService, CBPReportService, ExportService
        )
        
        result = {"row_count": 0}
        
        if schedule.report_type == ReportType.ENTRY_SUMMARY.value:
            service = AnalyticsService(self.db)
            data = await service.get_dashboard_summary(
                client_id=schedule.client_id,
            )
            result["row_count"] = data.get("total_entries", 0)
            
        elif schedule.report_type == ReportType.COMPLIANCE_SCORE.value:
            if schedule.client_id:
                service = ComplianceScoreService(self.db)
                data = await service.calculate_client_score(schedule.client_id)
                result["row_count"] = 1
        
        elif schedule.report_type == ReportType.CLIENT_ACTIVITY.value:
            service = AnalyticsService(self.db)
            data = await service.get_top_clients()
            result["row_count"] = len(data)
        
        elif schedule.report_type == ReportType.ANNUAL_SUMMARY.value:
            if schedule.client_id:
                service = CBPReportService(self.db)
                year = datetime.now().year
                data = await service.generate_annual_summary(schedule.client_id, year)
                result["row_count"] = data.get("summary", {}).get("total_entries", 0)
        
        return result
    
    async def get_report_history(
        self,
        schedule_id: Optional[UUID] = None,
        report_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[GeneratedReport]:
        """Get generated report history."""
        query = select(GeneratedReport)
        
        conditions = []
        if schedule_id:
            conditions.append(GeneratedReport.schedule_id == schedule_id)
        if report_type:
            conditions.append(GeneratedReport.report_type == report_type)
        if status:
            conditions.append(GeneratedReport.status == status)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        query = query.order_by(GeneratedReport.created_at.desc()).limit(limit)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def get_generated_report(self, report_id: UUID) -> Optional[GeneratedReport]:
        """Get generated report by ID."""
        query = select(GeneratedReport).where(GeneratedReport.id == report_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

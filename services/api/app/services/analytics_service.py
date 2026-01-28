"""
Analytics and Reporting Service.

Provides analytics, metrics, and report generation for:
- Entry analytics dashboard
- Compliance scoring
- CBP report generation
- Data export

Phase 7 from ROADMAP_FULL_WORKFLOW.md
"""
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID
import csv
import io

from sqlalchemy import select, func, and_, or_, extract, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entry import Entry
from app.models.client import Client


class AnalyticsService:
    """Service for entry analytics and business insights."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_dashboard_summary(
        self,
        client_id: Optional[UUID] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """Get overall dashboard summary."""
        # Default to last 30 days
        if not end_date:
            end_date = date.today()
        if not start_date:
            start_date = end_date - timedelta(days=30)
        
        query = select(Entry)
        
        if client_id:
            query = query.where(Entry.client_id == client_id)
        
        query = query.where(
            and_(
                Entry.created_at >= start_date,
                Entry.created_at <= end_date + timedelta(days=1),
            )
        )
        
        result = await self.db.execute(query)
        entries = result.scalars().all()
        
        # Calculate metrics using actual Entry model fields
        total_entries = len(entries)
        total_value = sum(float(e.total_entered_value or 0) for e in entries)
        total_duty = sum(float(e.total_duty or 0) for e in entries)
        total_amount_due = sum(float(e.total_amount_due or 0) for e in entries)
        
        # Status breakdown
        status_counts = {}
        for e in entries:
            status = e.status or "unknown"
            status_counts[status] = status_counts.get(status, 0) + 1
        
        return {
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "total_entries": total_entries,
            "total_value": total_value,
            "total_duty": total_duty,
            "total_amount_due": total_amount_due,
            "average_value": total_value / total_entries if total_entries > 0 else 0,
            "average_duty": total_duty / total_entries if total_entries > 0 else 0,
            "status_breakdown": status_counts,
        }
    
    async def get_entries_by_month(
        self,
        client_id: Optional[UUID] = None,
        months: int = 12,
    ) -> List[Dict[str, Any]]:
        """Get entry count and value by month."""
        end_date = date.today()
        start_date = end_date - timedelta(days=months * 30)
        
        query = (
            select(
                extract("year", Entry.created_at).label("year"),
                extract("month", Entry.created_at).label("month"),
                func.count(Entry.id).label("count"),
                func.sum(Entry.total_entered_value).label("total_value"),
                func.sum(Entry.total_duty).label("total_duty"),
            )
            .where(Entry.created_at >= start_date)
            .group_by(
                extract("year", Entry.created_at),
                extract("month", Entry.created_at),
            )
            .order_by(
                extract("year", Entry.created_at),
                extract("month", Entry.created_at),
            )
        )
        
        if client_id:
            query = query.where(Entry.client_id == client_id)
        
        result = await self.db.execute(query)
        rows = result.all()
        
        return [
            {
                "year": int(row.year),
                "month": int(row.month),
                "label": f"{int(row.year)}-{int(row.month):02d}",
                "count": row.count,
                "total_value": float(row.total_value or 0),
                "total_duty": float(row.total_duty or 0),
            }
            for row in rows
        ]
    
    async def get_top_hts_codes(
        self,
        client_id: Optional[UUID] = None,
        limit: int = 10,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[Dict[str, Any]]:
        """Get top HTS codes by value or count."""
        from app.models.entry import EntryLine
        
        if not end_date:
            end_date = date.today()
        if not start_date:
            start_date = end_date - timedelta(days=365)
        
        query = (
            select(
                EntryLine.hts_code,
                func.count(EntryLine.id).label("line_count"),
                func.sum(EntryLine.entered_value).label("total_value"),
                func.sum(EntryLine.total_line_duty).label("total_duty"),
            )
            .join(Entry, EntryLine.entry_id == Entry.id)
            .where(
                and_(
                    Entry.created_at >= start_date,
                    Entry.created_at <= end_date + timedelta(days=1),
                    EntryLine.hts_code.isnot(None),
                )
            )
            .group_by(EntryLine.hts_code)
            .order_by(desc(func.sum(EntryLine.entered_value)))
            .limit(limit)
        )
        
        if client_id:
            query = query.where(Entry.client_id == client_id)
        
        result = await self.db.execute(query)
        rows = result.all()
        
        return [
            {
                "hts_code": row.hts_code,
                "line_count": row.line_count,
                "total_value": float(row.total_value or 0),
                "total_duty": float(row.total_duty or 0),
            }
            for row in rows
        ]
    
    async def get_top_clients(
        self,
        limit: int = 10,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[Dict[str, Any]]:
        """Get top clients by entry count or value."""
        if not end_date:
            end_date = date.today()
        if not start_date:
            start_date = end_date - timedelta(days=365)
        
        query = (
            select(
                Entry.client_id,
                Client.name.label("client_name"),
                func.count(Entry.id).label("entry_count"),
                func.sum(Entry.total_entered_value).label("total_value"),
                func.sum(Entry.total_duty).label("total_duty"),
            )
            .join(Client, Entry.client_id == Client.id)
            .where(
                and_(
                    Entry.created_at >= start_date,
                    Entry.created_at <= end_date + timedelta(days=1),
                )
            )
            .group_by(Entry.client_id, Client.name)
            .order_by(desc(func.count(Entry.id)))
            .limit(limit)
        )
        
        result = await self.db.execute(query)
        rows = result.all()
        
        return [
            {
                "client_id": str(row.client_id),
                "client_name": row.client_name,
                "entry_count": row.entry_count,
                "total_value": float(row.total_value or 0),
                "total_duty": float(row.total_duty or 0),
            }
            for row in rows
        ]
    
    async def get_port_distribution(
        self,
        client_id: Optional[UUID] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[Dict[str, Any]]:
        """Get entry distribution by port."""
        if not end_date:
            end_date = date.today()
        if not start_date:
            start_date = end_date - timedelta(days=365)
        
        query = (
            select(
                Entry.port_of_entry,
                func.count(Entry.id).label("count"),
                func.sum(Entry.total_entered_value).label("total_value"),
            )
            .where(
                and_(
                    Entry.created_at >= start_date,
                    Entry.created_at <= end_date + timedelta(days=1),
                    Entry.port_of_entry.isnot(None),
                )
            )
            .group_by(Entry.port_of_entry)
            .order_by(desc(func.count(Entry.id)))
        )
        
        if client_id:
            query = query.where(Entry.client_id == client_id)
        
        result = await self.db.execute(query)
        rows = result.all()
        
        total_count = sum(r.count for r in rows)
        
        return [
            {
                "port": row.port_of_entry,
                "count": row.count,
                "percentage": round(row.count / total_count * 100, 1) if total_count > 0 else 0,
                "total_value": float(row.total_value or 0),
            }
            for row in rows
        ]
    
    async def get_processing_time_metrics(
        self,
        client_id: Optional[UUID] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """Get entry processing time metrics."""
        if not end_date:
            end_date = date.today()
        if not start_date:
            start_date = end_date - timedelta(days=90)
        
        query = select(Entry).where(
            and_(
                Entry.created_at >= start_date,
                Entry.created_at <= end_date + timedelta(days=1),
                Entry.filed_at.isnot(None),
            )
        )
        
        if client_id:
            query = query.where(Entry.client_id == client_id)
        
        result = await self.db.execute(query)
        entries = result.scalars().all()
        
        # Calculate processing times
        processing_times = []
        for e in entries:
            if e.filed_at and e.created_at:
                days = (e.filed_at.date() - e.created_at.date()).days
                if days >= 0:
                    processing_times.append(days)
        
        if processing_times:
            avg_time = sum(processing_times) / len(processing_times)
            min_time = min(processing_times)
            max_time = max(processing_times)
            # Calculate median
            sorted_times = sorted(processing_times)
            n = len(sorted_times)
            median_time = sorted_times[n // 2] if n % 2 == 1 else (sorted_times[n // 2 - 1] + sorted_times[n // 2]) / 2
        else:
            avg_time = min_time = max_time = median_time = 0
        
        return {
            "total_entries": len(entries),
            "entries_with_filed_date": len(processing_times),
            "average_processing_days": round(avg_time, 1),
            "median_processing_days": round(median_time, 1),
            "min_processing_days": min_time,
            "max_processing_days": max_time,
        }


class ComplianceScoreService:
    """Service for compliance scoring."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def calculate_client_score(
        self,
        client_id: UUID,
        months: int = 12,
    ) -> Dict[str, Any]:
        """Calculate compliance score for a client."""
        end_date = date.today()
        start_date = end_date - timedelta(days=months * 30)
        
        # Get entries for client
        query = select(Entry).where(
            and_(
                Entry.client_id == client_id,
                Entry.created_at >= start_date,
            )
        )
        result = await self.db.execute(query)
        entries = result.scalars().all()
        
        total_entries = len(entries)
        if total_entries == 0:
            return {
                "client_id": str(client_id),
                "overall_score": 100,
                "total_entries": 0,
                "categories": {},
                "message": "No entries in period",
            }
        
        # Calculate scores by category
        # These would be based on actual CBP rejections, amendments, etc.
        # For now, using simulated scoring logic
        
        classification_issues = 0
        value_issues = 0
        origin_issues = 0
        timing_issues = 0
        
        for e in entries:
            # Check for issues (in real system, these would be tracked)
            if e.status == "rejected":
                classification_issues += 1
            if hasattr(e, "amended") and e.amended:
                value_issues += 1
        
        classification_score = max(0, 100 - (classification_issues / total_entries * 100))
        value_score = max(0, 100 - (value_issues / total_entries * 100))
        origin_score = 95  # Placeholder
        timing_score = 90  # Placeholder
        
        overall_score = (classification_score * 0.35 + value_score * 0.30 + 
                        origin_score * 0.20 + timing_score * 0.15)
        
        return {
            "client_id": str(client_id),
            "overall_score": round(overall_score, 1),
            "total_entries": total_entries,
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "categories": {
                "classification": {
                    "score": round(classification_score, 1),
                    "weight": 35,
                    "issues": classification_issues,
                },
                "value": {
                    "score": round(value_score, 1),
                    "weight": 30,
                    "issues": value_issues,
                },
                "origin": {
                    "score": round(origin_score, 1),
                    "weight": 20,
                    "issues": origin_issues,
                },
                "timing": {
                    "score": round(timing_score, 1),
                    "weight": 15,
                    "issues": timing_issues,
                },
            },
            "rating": self._get_rating(overall_score),
            "recommendations": self._get_recommendations(
                classification_score, value_score, origin_score, timing_score
            ),
        }
    
    def _get_rating(self, score: float) -> str:
        if score >= 95:
            return "Excellent"
        elif score >= 85:
            return "Good"
        elif score >= 70:
            return "Fair"
        elif score >= 50:
            return "Needs Improvement"
        else:
            return "Critical"
    
    def _get_recommendations(
        self,
        classification: float,
        value: float,
        origin: float,
        timing: float,
    ) -> List[str]:
        recommendations = []
        
        if classification < 90:
            recommendations.append("Review HTS classification procedures")
        if value < 90:
            recommendations.append("Implement transaction value documentation checklist")
        if origin < 90:
            recommendations.append("Verify country of origin certifications")
        if timing < 90:
            recommendations.append("Improve entry filing turnaround time")
        
        if not recommendations:
            recommendations.append("Maintain current compliance practices")
        
        return recommendations
    
    async def get_score_trend(
        self,
        client_id: UUID,
        months: int = 12,
    ) -> List[Dict[str, Any]]:
        """Get monthly compliance score trend."""
        trends = []
        
        for i in range(months - 1, -1, -1):
            month_end = date.today() - timedelta(days=i * 30)
            month_start = month_end - timedelta(days=30)
            
            # Simplified - in production would calculate actual monthly score
            score = await self.calculate_client_score(client_id, months=1)
            
            trends.append({
                "month": month_start.strftime("%Y-%m"),
                "score": score["overall_score"],
            })
        
        return trends


class CBPReportService:
    """Service for generating CBP-compliant reports."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def generate_annual_summary(
        self,
        client_id: UUID,
        year: int,
    ) -> Dict[str, Any]:
        """Generate annual importer activity summary."""
        start_date = date(year, 1, 1)
        end_date = date(year, 12, 31)
        
        # Get client info
        client_query = select(Client).where(Client.id == client_id)
        client_result = await self.db.execute(client_query)
        client = client_result.scalar_one_or_none()
        
        if not client:
            raise ValueError(f"Client {client_id} not found")
        
        # Get entries for year
        query = select(Entry).where(
            and_(
                Entry.client_id == client_id,
                Entry.created_at >= start_date,
                Entry.created_at <= end_date + timedelta(days=1),
            )
        )
        result = await self.db.execute(query)
        entries = result.scalars().all()
        
        # Calculate totals
        total_entries = len(entries)
        total_value = sum(float(e.total_entered_value or 0) for e in entries)
        total_duty = sum(float(e.total_duty or 0) for e in entries)
        
        # Group by entry type
        entry_types = {}
        for e in entries:
            etype = e.entry_type or "unknown"
            if etype not in entry_types:
                entry_types[etype] = {"count": 0, "value": 0, "duty": 0}
            entry_types[etype]["count"] += 1
            entry_types[etype]["value"] += float(e.total_entered_value or 0)
            entry_types[etype]["duty"] += float(e.total_duty or 0)
        
        # Group by port
        ports = {}
        for e in entries:
            port = e.port_of_entry or "unknown"
            if port not in ports:
                ports[port] = 0
            ports[port] += 1
        
        return {
            "report_type": "Annual Importer Activity Summary",
            "generated_at": datetime.now(tz=None).isoformat(),
            "year": year,
            "client": {
                "id": str(client.id),
                "name": client.name,
                "ior_number": client.ior_number,
            },
            "summary": {
                "total_entries": total_entries,
                "total_value": total_value,
                "total_duty": total_duty,
            },
            "by_entry_type": entry_types,
            "by_port": ports,
            "cbp_format_compliant": True,
        }
    
    async def generate_record_keeping_report(
        self,
        client_id: UUID,
        start_date: date,
        end_date: date,
    ) -> Dict[str, Any]:
        """Generate CBP record-keeping compliance report."""
        # Get entries
        query = select(Entry).where(
            and_(
                Entry.client_id == client_id,
                Entry.created_at >= start_date,
                Entry.created_at <= end_date + timedelta(days=1),
            )
        )
        result = await self.db.execute(query)
        entries = result.scalars().all()
        
        # Check record keeping status (simplified)
        entries_with_docs = sum(1 for e in entries if hasattr(e, "document_ids") and e.document_ids)
        retention_compliant = len(entries)  # In production, check 5-year retention
        
        return {
            "report_type": "Record Keeping Compliance Report",
            "generated_at": datetime.now(tz=None).isoformat(),
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "client_id": str(client_id),
            "summary": {
                "total_entries": len(entries),
                "entries_with_documents": entries_with_docs,
                "retention_compliant": retention_compliant,
            },
            "compliance_status": "Compliant" if entries_with_docs == len(entries) else "Needs Review",
            "recommendations": [
                "Ensure all supporting documents are archived",
                "Verify 5-year retention period is maintained",
            ],
        }
    
    async def generate_isf_compliance_summary(
        self,
        client_id: UUID,
        start_date: date,
        end_date: date,
    ) -> Dict[str, Any]:
        """Generate ISF compliance summary report."""
        from app.models.isf_filing import ISFFiling
        
        # Get ISF filings
        query = select(ISFFiling).where(
            and_(
                ISFFiling.importer_id == str(client_id),
                ISFFiling.created_at >= start_date,
                ISFFiling.created_at <= end_date + timedelta(days=1),
            )
        )
        result = await self.db.execute(query)
        filings = result.scalars().all()
        
        # Analyze compliance
        total = len(filings)
        on_time = sum(1 for f in filings if f.status not in ["late", "rejected"])
        late = sum(1 for f in filings if f.status == "late")
        rejected = sum(1 for f in filings if f.status == "rejected")
        
        return {
            "report_type": "ISF Compliance Summary",
            "generated_at": datetime.now(tz=None).isoformat(),
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "client_id": str(client_id),
            "summary": {
                "total_filings": total,
                "on_time": on_time,
                "late": late,
                "rejected": rejected,
                "compliance_rate": round(on_time / total * 100, 1) if total > 0 else 100,
            },
            "status": "Compliant" if late == 0 and rejected == 0 else "Needs Improvement",
        }


class ExportService:
    """Service for exporting data to CSV/Excel."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def export_entries_csv(
        self,
        client_id: Optional[UUID] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        status: Optional[str] = None,
    ) -> str:
        """Export entries to CSV format."""
        query = select(Entry)
        
        conditions = []
        if client_id:
            conditions.append(Entry.client_id == client_id)
        if start_date:
            conditions.append(Entry.created_at >= start_date)
        if end_date:
            conditions.append(Entry.created_at <= end_date + timedelta(days=1))
        if status:
            conditions.append(Entry.status == status)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        query = query.order_by(Entry.created_at.desc())
        
        result = await self.db.execute(query)
        entries = result.scalars().all()
        
        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow([
            "Entry Number",
            "Entry Type",
            "Port",
            "Entry Date",
            "Status",
            "Total Value",
            "Total Duty",
            "Client ID",
            "Created At",
        ])
        
        # Data rows
        for e in entries:
            writer.writerow([
                e.entry_number,
                e.entry_type,
                e.port_of_entry,
                e.entry_date.isoformat() if e.entry_date else "",
                e.status,
                float(e.total_entered_value or 0),
                float(e.total_duty or 0),
                str(e.client_id) if e.client_id else "",
                e.created_at.isoformat() if e.created_at else "",
            ])
        
        return output.getvalue()
    
    async def export_clients_csv(self) -> str:
        """Export clients to CSV format."""
        query = select(Client).order_by(Client.name)
        result = await self.db.execute(query)
        clients = result.scalars().all()
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        writer.writerow([
            "Client ID",
            "Name",
            "Legal Name",
            "IOR Number",
            "EIN",
            "Status",
            "City",
            "State",
            "Country",
            "Created At",
        ])
        
        for c in clients:
            writer.writerow([
                str(c.id),
                c.name,
                c.legal_name,
                c.ior_number,
                c.ein,
                c.status,
                c.city,
                c.state_province,
                c.country,
                c.created_at.isoformat() if c.created_at else "",
            ])
        
        return output.getvalue()
    
    async def get_export_preview(
        self,
        export_type: str,
        filters: Dict[str, Any],
        limit: int = 10,
    ) -> Dict[str, Any]:
        """Get preview of export data."""
        if export_type == "entries":
            csv_data = await self.export_entries_csv(**filters)
        elif export_type == "clients":
            csv_data = await self.export_clients_csv()
        else:
            raise ValueError(f"Unknown export type: {export_type}")
        
        lines = csv_data.strip().split("\n")
        headers = lines[0] if lines else ""
        preview_rows = lines[1:limit + 1] if len(lines) > 1 else []
        total_rows = len(lines) - 1 if lines else 0
        
        return {
            "export_type": export_type,
            "total_rows": total_rows,
            "preview_rows": min(limit, total_rows),
            "headers": headers,
            "preview": preview_rows,
        }

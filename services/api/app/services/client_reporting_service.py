"""
Client Reporting Service.

Generates reports per client:
- Entry summary by date range
- Duty paid reports
- Import history by HTS chapter
- Year-to-date statistics
- Export to JSON (for PDF/Excel generation by frontend)

Task 4.5 from ROADMAP_FULL_WORKFLOW.md
"""
from datetime import datetime, date, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID
from decimal import Decimal
from collections import defaultdict
import calendar

from sqlalchemy import select, func, and_, or_, extract
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.client import Client
from app.models.entry import Entry, EntryLine, EntryStatus


class ClientReportService:
    """Service for generating client reports."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_entry_summary(
        self,
        client_id: UUID,
        start_date: date,
        end_date: date,
    ) -> Dict[str, Any]:
        """
        Generate entry summary report for a date range.
        
        Includes:
        - Total entries
        - Entries by status
        - Total value
        - Total duty
        """
        # Get entries for the client in date range
        query = select(Entry).where(
            and_(
                Entry.client_id == client_id,
                Entry.entry_date >= start_date,
                Entry.entry_date <= end_date,
            )
        ).options(selectinload(Entry.lines))
        
        result = await self.db.execute(query)
        entries = result.scalars().all()
        
        # Calculate statistics
        by_status = defaultdict(int)
        by_entry_type = defaultdict(int)
        by_port = defaultdict(int)
        
        total_value = Decimal("0")
        total_duty = Decimal("0")
        total_mpf = Decimal("0")
        total_hmf = Decimal("0")
        total_add_cvd = Decimal("0")
        
        entry_list = []
        
        for entry in entries:
            by_status[entry.status or "unknown"] += 1
            by_entry_type[entry.entry_type or "01"] += 1
            by_port[entry.port_of_entry or "unknown"] += 1
            
            # Sum values
            if entry.total_value:
                total_value += Decimal(str(entry.total_value))
            if entry.total_duty:
                total_duty += Decimal(str(entry.total_duty))
            if entry.mpf_amount:
                total_mpf += Decimal(str(entry.mpf_amount))
            if entry.hmf_amount:
                total_hmf += Decimal(str(entry.hmf_amount))
            if entry.add_cvd_amount:
                total_add_cvd += Decimal(str(entry.add_cvd_amount))
            
            entry_list.append({
                "id": str(entry.id),
                "entry_number": entry.entry_number,
                "entry_date": entry.entry_date.isoformat() if entry.entry_date else None,
                "entry_type": entry.entry_type,
                "port_of_entry": entry.port_of_entry,
                "status": entry.status,
                "total_value": float(entry.total_value or 0),
                "total_duty": float(entry.total_duty or 0),
                "line_count": len(entry.lines) if entry.lines else 0,
            })
        
        # Get client info
        client_query = select(Client).where(Client.id == client_id)
        client_result = await self.db.execute(client_query)
        client = client_result.scalar_one_or_none()
        
        return {
            "report_type": "entry_summary",
            "client": {
                "id": str(client_id),
                "name": client.name if client else "Unknown",
            },
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            "summary": {
                "total_entries": len(entries),
                "by_status": dict(by_status),
                "by_entry_type": dict(by_entry_type),
                "by_port": dict(by_port),
            },
            "financials": {
                "total_value": float(total_value),
                "total_duty": float(total_duty),
                "total_mpf": float(total_mpf),
                "total_hmf": float(total_hmf),
                "total_add_cvd": float(total_add_cvd),
                "total_fees": float(total_duty + total_mpf + total_hmf + total_add_cvd),
            },
            "entries": entry_list,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
    
    async def get_duty_paid_report(
        self,
        client_id: UUID,
        start_date: date,
        end_date: date,
    ) -> Dict[str, Any]:
        """
        Generate duty paid report.
        
        Detailed breakdown of all duties, fees, and taxes paid.
        """
        # Get entries with duty information
        query = select(Entry).where(
            and_(
                Entry.client_id == client_id,
                Entry.entry_date >= start_date,
                Entry.entry_date <= end_date,
                Entry.status.in_([EntryStatus.FILED.value, EntryStatus.ACCEPTED.value, EntryStatus.RELEASED.value]),
            )
        ).options(selectinload(Entry.lines))
        
        result = await self.db.execute(query)
        entries = result.scalars().all()
        
        # Calculate by entry
        duty_details = []
        totals = {
            "duty": Decimal("0"),
            "mpf": Decimal("0"),
            "hmf": Decimal("0"),
            "add_duty": Decimal("0"),
            "cvd": Decimal("0"),
            "other_fees": Decimal("0"),
        }
        
        for entry in entries:
            entry_duty = Decimal(str(entry.total_duty or 0))
            entry_mpf = Decimal(str(entry.mpf_amount or 0))
            entry_hmf = Decimal(str(entry.hmf_amount or 0))
            entry_add = Decimal("0")
            entry_cvd = Decimal("0")
            
            # Sum line-level ADD/CVD
            for line in (entry.lines or []):
                if line.add_rate:
                    entry_add += Decimal(str(line.add_rate or 0)) * Decimal(str(line.entered_value or 0)) / 100
                if line.cvd_rate:
                    entry_cvd += Decimal(str(line.cvd_rate or 0)) * Decimal(str(line.entered_value or 0)) / 100
            
            entry_total = entry_duty + entry_mpf + entry_hmf + entry_add + entry_cvd
            
            totals["duty"] += entry_duty
            totals["mpf"] += entry_mpf
            totals["hmf"] += entry_hmf
            totals["add_duty"] += entry_add
            totals["cvd"] += entry_cvd
            
            duty_details.append({
                "entry_number": entry.entry_number,
                "entry_date": entry.entry_date.isoformat() if entry.entry_date else None,
                "entry_value": float(entry.total_value or 0),
                "duty": float(entry_duty),
                "mpf": float(entry_mpf),
                "hmf": float(entry_hmf),
                "add_duty": float(entry_add),
                "cvd": float(entry_cvd),
                "total": float(entry_total),
            })
        
        grand_total = sum(totals.values())
        
        # Get client info
        client_query = select(Client).where(Client.id == client_id)
        client_result = await self.db.execute(client_query)
        client = client_result.scalar_one_or_none()
        
        return {
            "report_type": "duty_paid",
            "client": {
                "id": str(client_id),
                "name": client.name if client else "Unknown",
                "ior_number": client.ior_number if client else None,
            },
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            "totals": {
                "duty": float(totals["duty"]),
                "mpf": float(totals["mpf"]),
                "hmf": float(totals["hmf"]),
                "add_duty": float(totals["add_duty"]),
                "cvd": float(totals["cvd"]),
                "other_fees": float(totals["other_fees"]),
                "grand_total": float(grand_total),
            },
            "entry_count": len(duty_details),
            "entries": duty_details,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
    
    async def get_hts_chapter_report(
        self,
        client_id: UUID,
        start_date: date,
        end_date: date,
    ) -> Dict[str, Any]:
        """
        Generate import history by HTS chapter.
        
        Groups entries by HTS chapter (first 2 digits).
        """
        # Get entries with lines
        query = select(Entry).where(
            and_(
                Entry.client_id == client_id,
                Entry.entry_date >= start_date,
                Entry.entry_date <= end_date,
            )
        ).options(selectinload(Entry.lines))
        
        result = await self.db.execute(query)
        entries = result.scalars().all()
        
        # Group by HTS chapter
        by_chapter = defaultdict(lambda: {
            "count": 0,
            "entries": 0,
            "value": Decimal("0"),
            "duty": Decimal("0"),
            "quantity": Decimal("0"),
            "hts_codes": set(),
        })
        
        entry_ids_by_chapter = defaultdict(set)
        
        for entry in entries:
            for line in (entry.lines or []):
                if line.hts_code:
                    chapter = line.hts_code[:2]
                    by_chapter[chapter]["count"] += 1
                    by_chapter[chapter]["value"] += Decimal(str(line.entered_value or 0))
                    by_chapter[chapter]["duty"] += Decimal(str(line.duty_amount or 0))
                    by_chapter[chapter]["quantity"] += Decimal(str(line.quantity or 0))
                    by_chapter[chapter]["hts_codes"].add(line.hts_code[:6])
                    entry_ids_by_chapter[chapter].add(str(entry.id))
        
        # Calculate entry count per chapter
        for chapter in by_chapter:
            by_chapter[chapter]["entries"] = len(entry_ids_by_chapter[chapter])
        
        # Sort chapters
        chapter_data = []
        for chapter, data in sorted(by_chapter.items()):
            chapter_data.append({
                "chapter": chapter,
                "chapter_description": self._get_chapter_description(chapter),
                "line_count": data["count"],
                "entry_count": data["entries"],
                "total_value": float(data["value"]),
                "total_duty": float(data["duty"]),
                "total_quantity": float(data["quantity"]),
                "unique_hts_codes": len(data["hts_codes"]),
            })
        
        # Get client info
        client_query = select(Client).where(Client.id == client_id)
        client_result = await self.db.execute(client_query)
        client = client_result.scalar_one_or_none()
        
        return {
            "report_type": "hts_chapter",
            "client": {
                "id": str(client_id),
                "name": client.name if client else "Unknown",
            },
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            "summary": {
                "total_chapters": len(chapter_data),
                "total_value": float(sum(c["total_value"] for c in chapter_data)),
                "total_duty": float(sum(c["total_duty"] for c in chapter_data)),
            },
            "chapters": chapter_data,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
    
    def _get_chapter_description(self, chapter: str) -> str:
        """Get description for HTS chapter."""
        # Common HTS chapters
        chapters = {
            "01": "Live Animals",
            "02": "Meat and Edible Meat Offal",
            "03": "Fish and Crustaceans",
            "04": "Dairy Produce; Birds' Eggs; Natural Honey",
            "05": "Products of Animal Origin",
            "06": "Live Trees and Other Plants",
            "07": "Edible Vegetables and Certain Roots",
            "08": "Edible Fruit and Nuts",
            "09": "Coffee, Tea, Mate and Spices",
            "10": "Cereals",
            "11": "Products of Milling Industry",
            "12": "Oil Seeds and Oleaginous Fruits",
            "15": "Animal or Vegetable Fats and Oils",
            "16": "Preparations of Meat, Fish or Crustaceans",
            "17": "Sugars and Sugar Confectionery",
            "18": "Cocoa and Cocoa Preparations",
            "19": "Preparations of Cereals, Flour, Starch",
            "20": "Preparations of Vegetables, Fruit, Nuts",
            "21": "Miscellaneous Edible Preparations",
            "22": "Beverages, Spirits and Vinegar",
            "27": "Mineral Fuels, Mineral Oils",
            "28": "Inorganic Chemicals",
            "29": "Organic Chemicals",
            "30": "Pharmaceutical Products",
            "32": "Tanning or Dyeing Extracts",
            "33": "Essential Oils and Resinoids",
            "34": "Soap, Organic Surface-Active Agents",
            "39": "Plastics and Articles Thereof",
            "40": "Rubber and Articles Thereof",
            "42": "Articles of Leather",
            "44": "Wood and Articles of Wood",
            "48": "Paper and Paperboard",
            "61": "Articles of Apparel, Knitted or Crocheted",
            "62": "Articles of Apparel, Not Knitted",
            "63": "Other Made Up Textile Articles",
            "64": "Footwear, Gaiters and the Like",
            "65": "Headgear and Parts Thereof",
            "69": "Ceramic Products",
            "70": "Glass and Glassware",
            "71": "Natural or Cultured Pearls, Precious Stones",
            "72": "Iron and Steel",
            "73": "Articles of Iron or Steel",
            "74": "Copper and Articles Thereof",
            "75": "Nickel and Articles Thereof",
            "76": "Aluminum and Articles Thereof",
            "82": "Tools, Implements, Cutlery",
            "83": "Miscellaneous Articles of Base Metal",
            "84": "Nuclear Reactors, Boilers, Machinery",
            "85": "Electrical Machinery and Equipment",
            "87": "Vehicles Other Than Railway",
            "90": "Optical, Photographic, Medical Instruments",
            "94": "Furniture; Bedding, Mattresses",
            "95": "Toys, Games and Sports Equipment",
            "96": "Miscellaneous Manufactured Articles",
        }
        return chapters.get(chapter, f"Chapter {chapter}")
    
    async def get_ytd_statistics(
        self,
        client_id: UUID,
        year: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Generate year-to-date statistics.
        
        Monthly breakdown of entries and duties.
        """
        if year is None:
            year = date.today().year
        
        start_date = date(year, 1, 1)
        end_date = min(date(year, 12, 31), date.today())
        
        # Get entries for the year
        query = select(Entry).where(
            and_(
                Entry.client_id == client_id,
                Entry.entry_date >= start_date,
                Entry.entry_date <= end_date,
            )
        )
        
        result = await self.db.execute(query)
        entries = result.scalars().all()
        
        # Group by month
        monthly = defaultdict(lambda: {
            "entries": 0,
            "value": Decimal("0"),
            "duty": Decimal("0"),
        })
        
        for entry in entries:
            if entry.entry_date:
                month_key = entry.entry_date.strftime("%Y-%m")
                monthly[month_key]["entries"] += 1
                monthly[month_key]["value"] += Decimal(str(entry.total_value or 0))
                monthly[month_key]["duty"] += Decimal(str(entry.total_duty or 0))
        
        # Build monthly data
        monthly_data = []
        for month in range(1, 13):
            month_key = f"{year}-{month:02d}"
            month_name = calendar.month_name[month]
            data = monthly.get(month_key, {"entries": 0, "value": Decimal("0"), "duty": Decimal("0")})
            
            monthly_data.append({
                "month": month,
                "month_name": month_name,
                "month_key": month_key,
                "entry_count": data["entries"],
                "total_value": float(data["value"]),
                "total_duty": float(data["duty"]),
            })
        
        # YTD totals
        ytd_entries = sum(m["entry_count"] for m in monthly_data)
        ytd_value = sum(m["total_value"] for m in monthly_data)
        ytd_duty = sum(m["total_duty"] for m in monthly_data)
        
        # Calculate averages
        current_month = date.today().month if year == date.today().year else 12
        avg_entries = ytd_entries / current_month if current_month > 0 else 0
        avg_value = ytd_value / current_month if current_month > 0 else 0
        avg_duty = ytd_duty / current_month if current_month > 0 else 0
        
        # Get client info
        client_query = select(Client).where(Client.id == client_id)
        client_result = await self.db.execute(client_query)
        client = client_result.scalar_one_or_none()
        
        return {
            "report_type": "ytd_statistics",
            "client": {
                "id": str(client_id),
                "name": client.name if client else "Unknown",
            },
            "year": year,
            "ytd_totals": {
                "entries": ytd_entries,
                "value": ytd_value,
                "duty": ytd_duty,
            },
            "averages": {
                "entries_per_month": round(avg_entries, 1),
                "value_per_month": round(avg_value, 2),
                "duty_per_month": round(avg_duty, 2),
            },
            "monthly": monthly_data,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
    
    async def get_country_of_origin_report(
        self,
        client_id: UUID,
        start_date: date,
        end_date: date,
    ) -> Dict[str, Any]:
        """
        Generate import breakdown by country of origin.
        """
        # Get entries with lines
        query = select(Entry).where(
            and_(
                Entry.client_id == client_id,
                Entry.entry_date >= start_date,
                Entry.entry_date <= end_date,
            )
        ).options(selectinload(Entry.lines))
        
        result = await self.db.execute(query)
        entries = result.scalars().all()
        
        # Group by country
        by_country = defaultdict(lambda: {
            "lines": 0,
            "entries": set(),
            "value": Decimal("0"),
            "duty": Decimal("0"),
        })
        
        for entry in entries:
            for line in (entry.lines or []):
                country = line.country_of_origin or "Unknown"
                by_country[country]["lines"] += 1
                by_country[country]["entries"].add(str(entry.id))
                by_country[country]["value"] += Decimal(str(line.entered_value or 0))
                by_country[country]["duty"] += Decimal(str(line.duty_amount or 0))
        
        # Build country data
        country_data = []
        for country, data in sorted(by_country.items(), key=lambda x: float(x[1]["value"]), reverse=True):
            country_data.append({
                "country_code": country,
                "country_name": self._get_country_name(country),
                "line_count": data["lines"],
                "entry_count": len(data["entries"]),
                "total_value": float(data["value"]),
                "total_duty": float(data["duty"]),
            })
        
        client_query = select(Client).where(Client.id == client_id)
        client_result = await self.db.execute(client_query)
        client = client_result.scalar_one_or_none()
        
        return {
            "report_type": "country_of_origin",
            "client": {
                "id": str(client_id),
                "name": client.name if client else "Unknown",
            },
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            "summary": {
                "total_countries": len(country_data),
                "total_value": float(sum(c["total_value"] for c in country_data)),
                "total_duty": float(sum(c["total_duty"] for c in country_data)),
            },
            "countries": country_data,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
    
    def _get_country_name(self, code: str) -> str:
        """Get country name from ISO code."""
        countries = {
            "CN": "China",
            "MX": "Mexico",
            "CA": "Canada",
            "DE": "Germany",
            "JP": "Japan",
            "KR": "South Korea",
            "TW": "Taiwan",
            "VN": "Vietnam",
            "IN": "India",
            "GB": "United Kingdom",
            "FR": "France",
            "IT": "Italy",
            "TH": "Thailand",
            "MY": "Malaysia",
            "ID": "Indonesia",
            "PH": "Philippines",
            "BR": "Brazil",
            "AU": "Australia",
            # Add more as needed
        }
        return countries.get(code, code)
    
    async def generate_report(
        self,
        client_id: UUID,
        report_type: str,
        start_date: date,
        end_date: date,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Generate a report by type.
        
        Report types:
        - entry_summary
        - duty_paid
        - hts_chapter
        - ytd_statistics
        - country_of_origin
        """
        if report_type == "entry_summary":
            return await self.get_entry_summary(client_id, start_date, end_date)
        elif report_type == "duty_paid":
            return await self.get_duty_paid_report(client_id, start_date, end_date)
        elif report_type == "hts_chapter":
            return await self.get_hts_chapter_report(client_id, start_date, end_date)
        elif report_type == "ytd_statistics":
            year = kwargs.get("year", date.today().year)
            return await self.get_ytd_statistics(client_id, year)
        elif report_type == "country_of_origin":
            return await self.get_country_of_origin_report(client_id, start_date, end_date)
        else:
            raise ValueError(f"Unknown report type: {report_type}")
    
    async def list_available_reports(self) -> List[Dict[str, str]]:
        """List all available report types."""
        return [
            {
                "type": "entry_summary",
                "name": "Entry Summary Report",
                "description": "Summary of all entries in a date range",
            },
            {
                "type": "duty_paid",
                "name": "Duty Paid Report",
                "description": "Detailed breakdown of duties, fees, and taxes paid",
            },
            {
                "type": "hts_chapter",
                "name": "HTS Chapter Report",
                "description": "Import history grouped by HTS chapter",
            },
            {
                "type": "ytd_statistics",
                "name": "Year-to-Date Statistics",
                "description": "Monthly breakdown of entries and duties",
            },
            {
                "type": "country_of_origin",
                "name": "Country of Origin Report",
                "description": "Import breakdown by country of origin",
            },
        ]

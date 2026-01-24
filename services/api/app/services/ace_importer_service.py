"""
ACE Entry Data Importer Service
Parse and import CBP entry data from CSV, Excel, and structured formats.
"""
import csv
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from decimal import Decimal
from io import StringIO
from uuid import uuid4

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# Standard ACE/7501 field mappings - supports various broker export formats
FIELD_MAPPINGS = {
    # Entry header
    "entry_number": ["entry_number", "entry_no", "entrynumber", "entry #", "entry"],
    "entry_type": ["entry_type", "type", "entry_type_code"],
    "entry_date": ["entry_date", "entry date", "date_of_entry", "import_date"],
    
    # Importer
    "importer_name": ["importer", "importer_of_record", "ior", "importer_name", "consignee"],
    "importer_number": ["importer_number", "ior_number", "importer_id", "ein"],
    
    # Port
    "port_code": ["port_code", "port", "port_of_entry", "entry_port"],
    "port_name": ["port_name", "port_description"],
    
    # Line items
    "hts_code": ["hts", "hts_code", "tariff", "tariff_number", "htsus"],
    "description": ["description", "goods_description", "merchandise", "commodity"],
    "country_of_origin": ["origin", "country_of_origin", "coo", "made_in", "country"],
    "quantity": ["quantity", "qty", "units", "pieces"],
    "unit": ["unit", "uom", "unit_of_measure"],
    "entered_value": ["value", "entered_value", "line_value", "declared_value", "total_value"],
    "duty_rate": ["duty_rate", "rate", "tariff_rate", "ad_valorem"],
    "duty_amount": ["duty", "duty_amount", "duty_owed", "duties"],
    "mpf_amount": ["mpf", "merchandise_processing_fee"],
    "hmf_amount": ["hmf", "harbor_maintenance_fee"],
}


def normalize_field_name(field: str) -> Optional[str]:
    """Normalize a field name to standard name."""
    field_lower = field.lower().strip().replace("-", "_").replace(" ", "_")
    
    for standard_name, variations in FIELD_MAPPINGS.items():
        if field_lower in [v.lower() for v in variations]:
            return standard_name
    
    return None


def parse_date(date_str: str) -> Optional[datetime]:
    """Parse various date formats to datetime."""
    if not date_str:
        return None
    
    formats = [
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%m-%d-%Y",
        "%d/%m/%Y",
        "%Y%m%d",
        "%m/%d/%y",
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(str(date_str).strip(), fmt)
        except ValueError:
            continue
    
    return None


def parse_number(value: str) -> float:
    """Parse various number formats to float."""
    if not value:
        return 0.0
    
    # Remove currency symbols and commas
    cleaned = str(value).replace("$", "").replace(",", "").replace(" ", "").strip()
    
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


class ACEImporterService:
    """Service for importing ACE entry data from various file formats."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def import_csv(
        self,
        csv_content: str,
        batch_id: str = None
    ) -> Dict[str, Any]:
        """
        Import ACE entry data from CSV content.
        
        Each row becomes one ace_entries record.
        
        Args:
            csv_content: CSV string content
            batch_id: Optional batch identifier for grouping imports
        
        Returns:
            Import results with entries and statistics
        """
        if batch_id is None:
            batch_id = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        results = {
            "success": True,
            "batch_id": batch_id,
            "entries_parsed": 0,
            "entries_saved": 0,
            "total_value": 0.0,
            "total_duty": 0.0,
            "errors": [],
            "warnings": [],
        }
        
        try:
            reader = csv.DictReader(StringIO(csv_content))
            
            if not reader.fieldnames:
                results["success"] = False
                results["errors"].append("CSV file has no headers")
                return results
            
            # Normalize header fields
            field_map = {}
            unmapped_fields = []
            for field in reader.fieldnames:
                normalized = normalize_field_name(field)
                if normalized:
                    field_map[field] = normalized
                else:
                    unmapped_fields.append(field)
            
            if unmapped_fields:
                results["warnings"].append(f"Unmapped columns: {', '.join(unmapped_fields)}")
            
            logger.info(f"Field mappings: {field_map}")
            
            # Import model here to avoid circular imports
            from app.models.ace_entry import ACEEntry
            
            entries_to_save = []
            
            # Process each row
            for row_num, row in enumerate(reader, start=2):
                try:
                    # Normalize row keys
                    normalized_row = {}
                    for key, value in row.items():
                        norm_key = field_map.get(key, key.lower().replace(" ", "_"))
                        normalized_row[norm_key] = value
                    
                    # Extract entry number (required)
                    entry_number = str(normalized_row.get("entry_number", "")).strip()
                    if not entry_number:
                        results["warnings"].append(f"Row {row_num}: Missing entry number, skipped")
                        continue
                    
                    # Parse values
                    entered_value = parse_number(normalized_row.get("entered_value", "0"))
                    duty_rate = parse_number(normalized_row.get("duty_rate", "0"))
                    duty_amount = parse_number(normalized_row.get("duty_amount", "0"))
                    
                    # Calculate duty if not provided
                    if duty_amount == 0 and duty_rate > 0 and entered_value > 0:
                        rate = duty_rate if duty_rate <= 1 else duty_rate / 100
                        duty_amount = entered_value * rate
                    
                    # Create entry record
                    entry = ACEEntry(
                        entry_number=entry_number,
                        entry_date=parse_date(normalized_row.get("entry_date", "")),
                        entry_type=normalized_row.get("entry_type", "01"),
                        importer_name=normalized_row.get("importer_name", ""),
                        importer_number=normalized_row.get("importer_number"),
                        port_code=normalized_row.get("port_code", ""),
                        port_name=normalized_row.get("port_name", ""),
                        hts_code=normalized_row.get("hts_code", ""),
                        description=normalized_row.get("description", ""),
                        country_of_origin=normalized_row.get("country_of_origin", ""),
                        quantity=Decimal(str(parse_number(normalized_row.get("quantity", "0")))),
                        unit=normalized_row.get("unit", ""),
                        entered_value=Decimal(str(entered_value)),
                        duty_rate=Decimal(str(duty_rate)) if duty_rate > 0 else None,
                        duty_amount=Decimal(str(duty_amount)),
                        mpf_amount=Decimal(str(parse_number(normalized_row.get("mpf_amount", "0")))) or None,
                        hmf_amount=Decimal(str(parse_number(normalized_row.get("hmf_amount", "0")))) or None,
                        batch_id=batch_id,
                        raw_data={
                            "row_number": row_num,
                            "original_row": dict(row)
                        }
                    )
                    
                    entries_to_save.append(entry)
                    results["entries_parsed"] += 1
                    results["total_value"] += entered_value
                    results["total_duty"] += duty_amount
                    
                except Exception as e:
                    results["errors"].append(f"Row {row_num}: {str(e)}")
                    logger.error(f"Error parsing row {row_num}: {e}")
            
            # Save entries to database
            if entries_to_save:
                self.db.add_all(entries_to_save)
                await self.db.commit()
                results["entries_saved"] = len(entries_to_save)
            
            results["total_value"] = round(results["total_value"], 2)
            results["total_duty"] = round(results["total_duty"], 2)
            
        except Exception as e:
            logger.error(f"CSV import error: {e}")
            results["success"] = False
            results["errors"].append(str(e))
            await self.db.rollback()
        
        return results
    
    async def get_entries(
        self,
        batch_id: str = None,
        importer: str = None,
        hts_code: str = None,
        country: str = None,
        date_from: str = None,
        date_to: str = None,
        limit: int = 100,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Query ACE entries with filters."""
        from app.models.ace_entry import ACEEntry
        
        query = select(ACEEntry)
        
        filters = []
        if batch_id:
            filters.append(ACEEntry.batch_id == batch_id)
        if importer:
            filters.append(ACEEntry.importer_name.ilike(f"%{importer}%"))
        if hts_code:
            filters.append(ACEEntry.hts_code.like(f"{hts_code}%"))
        if country:
            filters.append(ACEEntry.country_of_origin.ilike(f"%{country}%"))
        if date_from:
            filters.append(ACEEntry.entry_date >= parse_date(date_from))
        if date_to:
            filters.append(ACEEntry.entry_date <= parse_date(date_to))
        
        if filters:
            query = query.where(and_(*filters))
        
        # Get total count
        count_query = select(func.count()).select_from(ACEEntry)
        if filters:
            count_query = count_query.where(and_(*filters))
        total = await self.db.scalar(count_query)
        
        # Apply pagination
        query = query.order_by(ACEEntry.entry_date.desc()).offset(offset).limit(limit)
        
        result = await self.db.execute(query)
        entries = result.scalars().all()
        
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "entries": [self._entry_to_dict(e) for e in entries]
        }
    
    async def get_statistics(self, batch_id: str = None) -> Dict[str, Any]:
        """Get statistics for ACE entries."""
        from app.models.ace_entry import ACEEntry
        
        query = select(ACEEntry)
        if batch_id:
            query = query.where(ACEEntry.batch_id == batch_id)
        
        result = await self.db.execute(query)
        entries = result.scalars().all()
        
        if not entries:
            return {
                "total_entries": 0,
                "unique_entry_numbers": 0,
                "total_value": 0,
                "total_duty": 0,
                "avg_duty_rate": 0,
                "importers": [],
                "ports": [],
                "hts_codes": [],
                "countries": [],
                "date_range": {}
            }
        
        # Calculate statistics
        entry_numbers = set()
        importers = set()
        ports = set()
        hts_codes = set()
        countries = set()
        total_value = 0
        total_duty = 0
        dates = []
        
        for e in entries:
            entry_numbers.add(e.entry_number)
            if e.importer_name:
                importers.add(e.importer_name)
            if e.port_name:
                ports.add(e.port_name)
            if e.hts_code:
                hts_codes.add(e.hts_code)
            if e.country_of_origin:
                countries.add(e.country_of_origin)
            if e.entry_date:
                dates.append(e.entry_date)
            
            total_value += float(e.entered_value or 0)
            total_duty += float(e.duty_amount or 0)
        
        return {
            "total_entries": len(entries),
            "unique_entry_numbers": len(entry_numbers),
            "total_value": round(total_value, 2),
            "total_duty": round(total_duty, 2),
            "avg_duty_rate": round((total_duty / total_value * 100) if total_value > 0 else 0, 2),
            "importers": sorted(list(importers))[:20],
            "ports": sorted(list(ports))[:20],
            "hts_codes": sorted(list(hts_codes))[:50],
            "countries": sorted(list(countries)),
            "date_range": {
                "earliest": min(dates).isoformat() if dates else None,
                "latest": max(dates).isoformat() if dates else None
            }
        }
    
    def _entry_to_dict(self, entry) -> Dict[str, Any]:
        """Convert ACEEntry model to dictionary."""
        return {
            "id": str(entry.id),
            "entry_number": entry.entry_number,
            "entry_date": entry.entry_date.isoformat() if entry.entry_date else None,
            "entry_type": entry.entry_type,
            "importer_name": entry.importer_name,
            "importer_number": entry.importer_number,
            "port_code": entry.port_code,
            "port_name": entry.port_name,
            "hts_code": entry.hts_code,
            "description": entry.description,
            "country_of_origin": entry.country_of_origin,
            "quantity": float(entry.quantity) if entry.quantity else None,
            "unit": entry.unit,
            "entered_value": float(entry.entered_value) if entry.entered_value else None,
            "duty_rate": float(entry.duty_rate) if entry.duty_rate else None,
            "duty_amount": float(entry.duty_amount) if entry.duty_amount else None,
            "mpf_amount": float(entry.mpf_amount) if entry.mpf_amount else None,
            "hmf_amount": float(entry.hmf_amount) if entry.hmf_amount else None,
            "liquidation_date": entry.liquidation_date.isoformat() if entry.liquidation_date else None,
            "liquidation_status": entry.liquidation_status,
            "batch_id": entry.batch_id,
            "created_at": entry.created_at.isoformat() if entry.created_at else None,
        }


# Sample ACE data for demonstration/testing
SAMPLE_ACE_DATA = """entry_number,entry_date,entry_type,importer_name,port_name,hts_code,description,country_of_origin,quantity,unit,entered_value,duty_rate,duty_amount
ABC-1234567-8,2024-01-15,01,Acme Import Corp,Los Angeles,8471.30.0100,Laptop computers,CN,100,PCS,150000,0,0
ABC-1234567-8,2024-01-15,01,Acme Import Corp,Los Angeles,8471.60.9000,Computer monitors,CN,200,PCS,80000,0,0
ABC-1234568-9,2024-02-20,01,Acme Import Corp,Long Beach,6110.20.2075,Cotton sweaters,VN,500,PCS,25000,16.5,4125
ABC-1234568-9,2024-02-20,01,Acme Import Corp,Long Beach,6203.42.4015,Cotton trousers,VN,300,PCS,18000,16.6,2988
DEF-9876543-2,2024-03-10,01,Global Trading LLC,New York,8517.12.0050,Smartphones,KR,1000,PCS,500000,0,0
DEF-9876543-2,2024-03-10,01,Global Trading LLC,New York,8518.30.2000,Headphones,KR,2000,PCS,100000,4.9,4900
GHI-5555555-5,2024-04-05,01,Tech Imports Inc,Seattle,9403.20.0018,Metal office desks,MX,50,PCS,35000,0,0
GHI-5555555-5,2024-04-05,01,Tech Imports Inc,Seattle,9401.30.8000,Office chairs,MX,100,PCS,20000,0,0
JKL-7777777-7,2024-05-15,01,Pacific Trade Imports,Los Angeles,8471.30.0100,Desktop computers,CN,200,PCS,300000,0,0
JKL-7777777-7,2024-05-15,01,Pacific Trade Imports,Los Angeles,8544.42.9000,USB cables,CN,5000,PCS,15000,0,0
JKL-7777777-7,2024-05-15,01,Pacific Trade Imports,Los Angeles,8504.40.9500,Power adapters,CN,200,PCS,10000,1.5,150
MNO-8888888-8,2024-06-20,01,Fashion Imports LLC,New York,6204.62.4020,Women's cotton dresses,BD,1000,PCS,50000,11.5,5750
MNO-8888888-8,2024-06-20,01,Fashion Imports LLC,New York,6205.20.2060,Men's cotton shirts,BD,800,PCS,32000,19.7,6304
"""


async def load_sample_ace_data(db: AsyncSession) -> Dict[str, Any]:
    """Load sample ACE data for demonstration."""
    service = ACEImporterService(db)
    return await service.import_csv(SAMPLE_ACE_DATA, batch_id="sample_data")

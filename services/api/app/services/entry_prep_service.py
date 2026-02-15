"""
Entry Prep Service

Aggregates shipment data into CBP 7501 entry format.
Supports pre-filling from extracted trade documents.

Phase 5 Task 5.1 from trade automation implementation plan.
"""
from typing import Any, Optional
from uuid import UUID
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.gold_records import Shipment
from app.models.document_metadata import DocumentMetadata
from app.models.extraction_result import ExtractionResult


class EntryPrepData:
    """CBP 7501 Entry Summary Data Structure"""
    
    def __init__(self):
        # Header Fields
        self.entry_number: Optional[str] = None
        self.entry_type: str = "01"  # Consumption Entry (most common)
        self.entry_date: Optional[datetime] = None
        self.filer_code: Optional[str] = None
        self.port_code: Optional[str] = None
        
        # Importer Information  
        self.importer_of_record_number: Optional[str] = None
        self.importer_name: Optional[str] = None
        self.importer_address: Optional[str] = None
        self.importer_city: Optional[str] = None
        self.importer_state: Optional[str] = None
        self.importer_zip: Optional[str] = None
        
        # Consignee Information
        self.consignee_name: Optional[str] = None
        self.consignee_address: Optional[str] = None
        
        # Transport Information
        self.carrier_code: Optional[str] = None
        self.vessel_name: Optional[str] = None
        self.voyage_number: Optional[str] = None
        self.port_of_unlading: Optional[str] = None
        self.port_of_entry: Optional[str] = None
        self.importing_carrier: Optional[str] = None
        self.foreign_port: Optional[str] = None
        self.export_date: Optional[datetime] = None
        self.import_date: Optional[datetime] = None
        
        # Bill of Lading / Transport
        self.master_bill: Optional[str] = None
        self.house_bill: Optional[str] = None
        self.scac_code: Optional[str] = None
        
        # Bond Information
        self.bond_type: str = "9"  # Continuous bond
        self.surety_code: Optional[str] = None
        
        # Country Information
        self.country_of_origin: Optional[str] = None
        self.exporting_country: Optional[str] = None
        
        # Value/Duty Summary
        self.total_entered_value: Decimal = Decimal("0.00")
        self.total_duty: Decimal = Decimal("0.00")
        self.total_mpf: Decimal = Decimal("0.00")  # Merchandise Processing Fee
        self.total_hmf: Decimal = Decimal("0.00")  # Harbor Maintenance Fee
        self.total_taxes: Decimal = Decimal("0.00")
        self.total_other: Decimal = Decimal("0.00")
        self.grand_total: Decimal = Decimal("0.00")
        
        # Line Items
        self.line_items: list[dict] = []
        
        # Metadata
        self.source_shipment_id: Optional[str] = None
        self.source_documents: list[str] = []
        self.validation_warnings: list[str] = []
        self.completeness_score: float = 0.0
        
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "entry_number": self.entry_number,
            "entry_type": self.entry_type,
            "entry_date": self.entry_date.isoformat() if self.entry_date else None,
            "filer_code": self.filer_code,
            "port_code": self.port_code,
            
            "importer": {
                "ior_number": self.importer_of_record_number,
                "name": self.importer_name,
                "address": self.importer_address,
                "city": self.importer_city,
                "state": self.importer_state,
                "zip": self.importer_zip,
            },
            
            "consignee": {
                "name": self.consignee_name,
                "address": self.consignee_address,
            },
            
            "transport": {
                "carrier_code": self.carrier_code,
                "vessel_name": self.vessel_name,
                "voyage_number": self.voyage_number,
                "port_of_unlading": self.port_of_unlading,
                "port_of_entry": self.port_of_entry,
                "importing_carrier": self.importing_carrier,
                "foreign_port": self.foreign_port,
                "export_date": self.export_date.isoformat() if self.export_date else None,
                "import_date": self.import_date.isoformat() if self.import_date else None,
                "master_bill": self.master_bill,
                "house_bill": self.house_bill,
                "scac_code": self.scac_code,
            },
            
            "bond": {
                "type": self.bond_type,
                "surety_code": self.surety_code,
            },
            
            "origin": {
                "country_of_origin": self.country_of_origin,
                "exporting_country": self.exporting_country,
            },
            
            "totals": {
                "entered_value": float(self.total_entered_value),
                "duty": float(self.total_duty),
                "mpf": float(self.total_mpf),
                "hmf": float(self.total_hmf),
                "taxes": float(self.total_taxes),
                "other": float(self.total_other),
                "grand_total": float(self.grand_total),
            },
            
            "line_items": self.line_items,
            
            "metadata": {
                "source_shipment_id": self.source_shipment_id,
                "source_documents": self.source_documents,
                "validation_warnings": self.validation_warnings,
                "completeness_score": self.completeness_score,
            }
        }


class EntryPrepService:
    """Service for preparing customs entry data from shipments"""
    
    # Standard duty rates by HTS chapter (simplified)
    DEFAULT_DUTY_RATES = {
        "61": 0.12,  # Apparel, knitted
        "62": 0.12,  # Apparel, not knitted
        "64": 0.08,  # Footwear
        "85": 0.0,   # Electronics (often duty-free)
        "94": 0.0,   # Furniture
        "84": 0.0,   # Machinery
    }
    
    MPF_RATE = 0.003464  # 0.3464% of value
    MPF_MIN = Decimal("27.75")
    MPF_MAX = Decimal("538.40")
    
    HMF_RATE = 0.00125  # 0.125% of value (ocean shipments only)
    
    @classmethod
    async def prepare_from_shipment(
        cls,
        session: AsyncSession,
        shipment_id: UUID
    ) -> EntryPrepData:
        """
        Prepare entry data from a shipment and its linked documents.
        
        Args:
            session: Database session
            shipment_id: UUID of the shipment to prepare from
            
        Returns:
            EntryPrepData with pre-filled fields
        """
        entry = EntryPrepData()
        entry.source_shipment_id = str(shipment_id)
        
        # Fetch shipment
        result = await session.execute(
            select(Shipment).where(Shipment.id == shipment_id)
        )
        shipment = result.scalar_one_or_none()
        
        if not shipment:
            entry.validation_warnings.append(f"Shipment {shipment_id} not found")
            return entry
        
        # Populate from shipment
        entry.entry_number = shipment.entry_number
        entry.port_code = shipment.port_of_entry
        entry.master_bill = shipment.bol_number
        entry.importer_name = shipment.importer_name
        entry.consignee_name = shipment.importer_name  # Often same
        entry.foreign_port = shipment.origin
        entry.port_of_entry = shipment.destination or shipment.port_of_entry
        entry.import_date = shipment.arrival_date
        entry.export_date = shipment.ship_date
        entry.total_entered_value = shipment.total_declared_value or Decimal("0.00")
        
        if shipment.documents:
            entry.source_documents = [str(d) for d in shipment.documents]
        
        # Fetch extraction results for linked documents
        if entry.source_documents:
            extractions = await cls._get_document_extractions(session, entry.source_documents)
            cls._merge_extraction_data(entry, extractions)
        
        # Calculate duties
        cls._calculate_duties(entry)
        
        # Calculate completeness
        entry.completeness_score = cls._calculate_completeness(entry)
        
        # Validate and generate warnings
        cls._validate_entry(entry)
        
        return entry
    
    @classmethod
    async def _get_document_extractions(
        cls,
        session: AsyncSession,
        document_ids: list[str]
    ) -> list[dict]:
        """Fetch extraction results for documents"""
        extractions = []
        
        try:
            uuids = [UUID(d) for d in document_ids]
            result = await session.execute(
                select(ExtractionResult).where(
                    ExtractionResult.document_id.in_(uuids),
                    ExtractionResult.extraction_type == "trade_document"
                )
            )
            
            for extraction in result.scalars().all():
                if extraction.extracted_data:
                    extractions.append(extraction.extracted_data)
        except Exception as e:
            print(f"Error fetching extractions: {e}")
        
        return extractions
    
    @classmethod
    def _merge_extraction_data(cls, entry: EntryPrepData, extractions: list[dict]) -> None:
        """Merge data from multiple extractions into entry"""
        line_items = []
        
        for extraction in extractions:
            # Document-level fields (take first non-null)
            if not entry.master_bill and extraction.get("master_bol"):
                entry.master_bill = extraction["master_bol"]
            if not entry.house_bill and extraction.get("house_bol"):
                entry.house_bill = extraction["house_bol"]
            if not entry.consignee_name and extraction.get("consignee"):
                entry.consignee_name = extraction["consignee"]
            if not entry.importer_name and extraction.get("consignee"):
                entry.importer_name = extraction["consignee"]
            if not entry.vessel_name and extraction.get("vessel_name"):
                entry.vessel_name = extraction["vessel_name"]
            if not entry.voyage_number and extraction.get("voyage_number"):
                entry.voyage_number = extraction["voyage_number"]
            if not entry.foreign_port and extraction.get("port_of_loading"):
                entry.foreign_port = extraction["port_of_loading"]
            if not entry.port_of_entry and extraction.get("port_of_discharge"):
                entry.port_of_entry = extraction["port_of_discharge"]
            if not entry.country_of_origin and extraction.get("country_of_origin"):
                entry.country_of_origin = extraction["country_of_origin"]
            
            # Extract line items from commercial invoices
            items = extraction.get("line_items", [])
            for item in items:
                line_item = {
                    "line_number": len(line_items) + 1,
                    "hts_number": item.get("hts_code", ""),
                    "description": item.get("description", ""),
                    "quantity": item.get("quantity", 0),
                    "unit": item.get("unit", "PCS"),
                    "gross_weight": item.get("weight", 0),
                    "country_of_origin": item.get("country_of_origin", entry.country_of_origin),
                    "entered_value": Decimal(str(item.get("value", 0))),
                    "duty_rate": cls._get_duty_rate(item.get("hts_code", "")),
                    "duty_amount": Decimal("0.00"),
                }
                # Calculate duty
                line_item["duty_amount"] = line_item["entered_value"] * Decimal(str(line_item["duty_rate"]))
                line_items.append(line_item)
        
        entry.line_items = line_items
        
        # Sum up line item values
        if line_items:
            entry.total_entered_value = sum(
                item.get("entered_value", Decimal("0.00")) 
                for item in line_items
            )
            entry.total_duty = sum(
                item.get("duty_amount", Decimal("0.00"))
                for item in line_items
            )
    
    @classmethod
    def _get_duty_rate(cls, hts_code: str) -> float:
        """Get duty rate for HTS code (simplified)"""
        if not hts_code:
            return 0.0
        
        # Get chapter (first 2 digits)
        chapter = hts_code[:2] if len(hts_code) >= 2 else ""
        return cls.DEFAULT_DUTY_RATES.get(chapter, 0.05)  # Default 5%
    
    @classmethod
    def _calculate_duties(cls, entry: EntryPrepData) -> None:
        """Calculate MPF, HMF, and total duties"""
        value = float(entry.total_entered_value)
        
        # Merchandise Processing Fee
        mpf = Decimal(str(value * cls.MPF_RATE))
        entry.total_mpf = max(cls.MPF_MIN, min(cls.MPF_MAX, mpf))
        
        # Harbor Maintenance Fee (ocean shipments)
        entry.total_hmf = Decimal(str(value * cls.HMF_RATE))
        
        # Grand total
        entry.grand_total = (
            entry.total_duty +
            entry.total_mpf +
            entry.total_hmf +
            entry.total_taxes +
            entry.total_other
        )
    
    @classmethod
    def _calculate_completeness(cls, entry: EntryPrepData) -> float:
        """Calculate how complete the entry data is (0-1)"""
        required_fields = [
            entry.importer_name,
            entry.port_of_entry or entry.port_code,
            entry.master_bill,
            entry.country_of_origin or entry.foreign_port,
            entry.total_entered_value > 0,
        ]
        
        important_fields = [
            entry.consignee_name,
            entry.vessel_name,
            entry.import_date,
            entry.foreign_port,
            len(entry.line_items) > 0,
        ]
        
        optional_fields = [
            entry.filer_code,
            entry.surety_code,
            entry.export_date,
            entry.voyage_number,
        ]
        
        required_score = sum(1 for f in required_fields if f) / len(required_fields) * 0.6
        important_score = sum(1 for f in important_fields if f) / len(important_fields) * 0.3
        optional_score = sum(1 for f in optional_fields if f) / len(optional_fields) * 0.1
        
        return round(required_score + important_score + optional_score, 2)
    
    @classmethod
    def _validate_entry(cls, entry: EntryPrepData) -> None:
        """Add validation warnings"""
        if not entry.importer_name:
            entry.validation_warnings.append("Missing importer name")
        if not entry.master_bill:
            entry.validation_warnings.append("Missing bill of lading")
        if not entry.port_of_entry and not entry.port_code:
            entry.validation_warnings.append("Missing port of entry")
        if not entry.country_of_origin and not entry.foreign_port:
            entry.validation_warnings.append("Missing country of origin")
        if entry.total_entered_value <= 0:
            entry.validation_warnings.append("No declared value - duty calculation may be incorrect")
        if len(entry.line_items) == 0:
            entry.validation_warnings.append("No line items - add commercial invoice details")
        
        # Check line items
        for item in entry.line_items:
            if not item.get("hts_number"):
                entry.validation_warnings.append(
                    f"Line {item.get('line_number', '?')}: Missing HTS code"
                )
    
    @classmethod
    def export_to_ace_format(cls, entry: EntryPrepData) -> dict:
        """
        Export entry data in ACE-compatible format.
        Note: This is simplified - actual ACE format is more complex.
        """
        return {
            "header": {
                "entry_summary_type": entry.entry_type,
                "entry_number": entry.entry_number,
                "port_code": entry.port_code,
                "entry_date": entry.entry_date.isoformat() if entry.entry_date else None,
                "filer_code": entry.filer_code,
            },
            "importer": {
                "ior": entry.importer_of_record_number,
                "name": entry.importer_name,
            },
            "transport": {
                "mot": "11",  # Ocean
                "carrier": entry.carrier_code,
                "vessel": entry.vessel_name,
                "voyage": entry.voyage_number,
                "bill_number": entry.master_bill,
            },
            "invoice_headers": [{
                "consignee": entry.consignee_name,
                "origin": entry.country_of_origin,
                "value": float(entry.total_entered_value),
            }],
            "line_items": [
                {
                    "line": item["line_number"],
                    "hts": item["hts_number"],
                    "description": item["description"][:50] if item.get("description") else "",
                    "value": float(item.get("entered_value", 0)),
                    "qty": item.get("quantity", 1),
                    "origin": item.get("country_of_origin", entry.country_of_origin),
                }
                for item in entry.line_items
            ],
            "totals": {
                "value": float(entry.total_entered_value),
                "duty": float(entry.total_duty),
                "mpf": float(entry.total_mpf),
                "hmf": float(entry.total_hmf),
                "total": float(entry.grand_total),
            }
        }

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
    
    # Advisory fallback duty rates by HTS chapter ONLY when tariff table has no match;
    # lines without a verified DB rate are explicitly flagged in validation_warnings.
    ADVISORY_CHAPTER_RATES = {
        "61": 0.12,  # Apparel, knitted
        "62": 0.12,  # Apparel, not knitted
        "64": 0.08,  # Footwear
        "84": 0.0,   # Machinery
        "85": 0.0,   # Electronics
        "94": 0.0,   # Furniture
    }
    
    # FY2026 CBP Merchandise Processing Fee (19 CFR 24.23)
    MPF_RATE = 0.003464  # 0.3464% ad valorem
    MPF_MIN = Decimal("33.58")
    MPF_MAX = Decimal("651.50")
    
    HMF_RATE = 0.00125  # 0.125% of value (ocean shipments only)
    
    @classmethod
    async def prepare_from_shipment(
        cls,
        session: AsyncSession,
        shipment_id: UUID
    ) -> EntryPrepData:
        """
        Prepare entry data from a shipment and its linked documents.
        Never fabricates synthetic IOR EINs, HTS codes, origins, or customs values.
        """
        from sqlalchemy.orm import selectinload
        from app.core.config import settings
        from app.models.client import Client

        entry = EntryPrepData()
        entry.source_shipment_id = str(shipment_id)
        configured_filer = (settings.broker_filer_code or "").strip().upper()[:3] or None
        configured_port = (settings.broker_default_port or "").strip()[:4] or None
        entry.filer_code = configured_filer
        entry.entry_date = datetime.now(timezone.utc)
        
        # Fetch shipment with linked_documents
        result = await session.execute(
            select(Shipment)
            .options(selectinload(Shipment.linked_documents))
            .where(Shipment.id == shipment_id)
        )
        shipment = result.scalar_one_or_none()
        
        if not shipment:
            entry.validation_warnings.append(f"Shipment {shipment_id} not found")
            return entry
        
        # Populate from shipment without inventing unverified filer/port codes
        id_digits = str(shipment.id.int)
        if shipment.entry_number:
            entry.entry_number = shipment.entry_number
            if not entry.filer_code and "-" in shipment.entry_number:
                prefix = shipment.entry_number.split("-", 1)[0].strip().upper()
                if len(prefix) == 3:
                    entry.filer_code = prefix
        elif configured_filer:
            entry.entry_number = f"{configured_filer}-{id_digits[:7]}-{id_digits[7]}"
        else:
            entry.entry_number = None

        raw_dest_port = (
            shipment.port_of_entry
            if shipment.port_of_entry and shipment.port_of_entry.isdigit() and len(shipment.port_of_entry) == 4
            else None
        )
        entry.port_code = raw_dest_port or configured_port
        entry.master_bill = shipment.bol_number or (
            shipment.primary_key_value if shipment.primary_key_type == "BOL_NUM" else None
        )
        entry.importer_name = shipment.importer_name
        entry.consignee_name = shipment.importer_name
        entry.foreign_port = shipment.origin
        entry.port_of_entry = raw_dest_port or configured_port
        entry.import_date = shipment.arrival_date or datetime.now(timezone.utc)
        entry.export_date = shipment.ship_date
        entry.total_entered_value = shipment.total_declared_value or Decimal("0.00")
        
        linked_doc_ids = [str(link.document_id) for link in (shipment.linked_documents or [])]
        if shipment.documents:
            for d in shipment.documents:
                if str(d) not in linked_doc_ids:
                    linked_doc_ids.append(str(d))
        entry.source_documents = linked_doc_ids
        
        # Fetch extraction results for linked documents
        if entry.source_documents:
            extractions = await cls._get_document_extractions(session, entry.source_documents)
            hts_rates = await cls._lookup_hts_rates(session, extractions)
            cls._merge_extraction_data(entry, extractions, hts_rates=hts_rates)

        # Resolve Importer of Record EIN/IOR from Client master record if missing from PDF
        if entry.importer_name and not entry.importer_of_record_number:
            client_res = await session.execute(
                select(Client).where(Client.name.ilike(entry.importer_name.strip())).limit(1)
            )
            matched_client = client_res.scalar_one_or_none()
            if matched_client:
                entry.importer_of_record_number = matched_client.ior_number or matched_client.ein
                if not entry.importer_address and matched_client.address_line1:
                    entry.importer_address = matched_client.address_line1
                if not entry.importer_city and matched_client.city:
                    entry.importer_city = matched_client.city
                if not entry.importer_state and matched_client.state_province:
                    entry.importer_state = matched_client.state_province
                if not entry.importer_zip and matched_client.postal_code:
                    entry.importer_zip = matched_client.postal_code
                if not entry.port_code and matched_client.primary_port:
                    entry.port_code = matched_client.primary_port[:4]
                    entry.port_of_entry = entry.port_code
        
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
    ) -> list[ExtractionResult]:
        """Fetch ExtractionResult ORM records for linked documents (supporting both DocumentMetadata.id and RawFile.id)"""
        try:
            from app.models.raw_file import RawFile

            uuids = [UUID(d) for d in document_ids]
            resolved_doc_ids = set(uuids)

            # Also resolve RawFile IDs -> DocumentMetadata IDs via storage_path or filename
            raw_res = await session.execute(select(RawFile).where(RawFile.id.in_(uuids)))
            raw_files = raw_res.scalars().all()
            if raw_files:
                filenames = [rf.filename for rf in raw_files if rf.filename]
                if filenames:
                    dm_res = await session.execute(
                        select(DocumentMetadata.id).where(DocumentMetadata.filename.in_(filenames))
                    )
                    resolved_doc_ids.update(dm_res.scalars().all())

            result = await session.execute(
                select(ExtractionResult).where(
                    ExtractionResult.document_id.in_(list(resolved_doc_ids))
                )
            )
            return list(result.scalars().all())
        except Exception as e:
            print(f"Error fetching extractions: {e}")
            return []
    
    @classmethod
    async def _lookup_hts_rates(
        cls,
        session: AsyncSession,
        extractions: list[ExtractionResult],
    ) -> dict[str, float]:
        """Look up authoritative base duty rates (as decimal fraction, e.g. 0.065) from hts_codes."""
        from app.models.reference_data import HTSCode

        candidate_codes: set[str] = set()
        for ext in extractions:
            if not (ext.field_name or "").lower().strip().startswith("cargo_item"):
                continue
            meta = ext.extraction_metadata or {}
            raw = ""
            if isinstance(meta, dict):
                raw = str(meta.get("hts_code") or meta.get("hs_code") or "").strip()
            val_str = str(ext.final_value or "").strip()
            if not raw and "HTS" in val_str:
                parts = val_str.split("HTS")[-1].strip().split()
                if parts:
                    raw = parts[0].strip()
            if raw:
                candidate_codes.add(raw)
                digits = "".join(c for c in raw if c.isdigit())
                if len(digits) >= 6:
                    candidate_codes.add(digits)
                    if len(digits) == 10:
                        candidate_codes.add(f"{digits[:4]}.{digits[4:6]}.{digits[6:]}")
                    elif len(digits) == 8:
                        candidate_codes.add(f"{digits[:4]}.{digits[4:6]}.{digits[6:]}")

        if not candidate_codes:
            return {}

        try:
            res = await session.execute(
                select(HTSCode).where(HTSCode.hts_code.in_(list(candidate_codes)))
            )
            rates: dict[str, float] = {}
            for row in res.scalars().all():
                if row.duty_rate_percent is not None:
                    frac = float(row.duty_rate_percent) / 100.0
                    rates[row.hts_code] = frac
                    rates["".join(c for c in row.hts_code if c.isdigit())] = frac
            return rates
        except Exception:
            return {}

    @classmethod
    def _merge_extraction_data(
        cls,
        entry: EntryPrepData,
        extractions: list[ExtractionResult],
        hts_rates: Optional[dict[str, float]] = None,
    ) -> None:
        """Merge individual field ExtractionResult records into EntryPrepData without synthetic fallbacks."""
        hts_rates = hts_rates or {}
        line_items = []
        invoice_values: list[Decimal] = []
        seen_cargo = set()
        
        for ext in extractions:
            fname = (ext.field_name or "").lower().strip()
            val = ext.final_value
            if val is None:
                continue
            val_str = str(val).strip().strip('"')
            meta = ext.extraction_metadata or {}

            if fname in ("master_bl_number", "master_bol", "bol_number", "bill_of_lading") and not entry.master_bill:
                entry.master_bill = val_str
                if len(val_str) >= 4 and not entry.scac_code:
                    entry.scac_code = val_str[:4].upper()
                    entry.carrier_code = val_str[:4].upper()
            elif fname in ("house_bl_number", "house_bol", "house_bill") and not entry.house_bill:
                entry.house_bill = val_str
            elif fname in ("importer_of_record", "importer", "buyer", "consignee"):
                clean_name = val_str.split(" Description")[0].split(" Address")[0].strip()
                if not entry.importer_name:
                    entry.importer_name = clean_name
                if not entry.consignee_name:
                    entry.consignee_name = clean_name
                if isinstance(meta, dict):
                    if meta.get("tax_id") and not entry.importer_of_record_number:
                        entry.importer_of_record_number = str(meta["tax_id"])
                    if meta.get("address") and not entry.importer_address:
                        entry.importer_address = str(meta["address"])
                    if meta.get("city") and not entry.importer_city:
                        entry.importer_city = str(meta["city"])
                    if meta.get("state") and not entry.importer_state:
                        entry.importer_state = str(meta["state"])
                    if meta.get("postal_code") and not entry.importer_zip:
                        entry.importer_zip = str(meta["postal_code"])
            elif fname in ("shipper", "seller", "exporter", "manufacturer"):
                if isinstance(meta, dict) and meta.get("country") and not entry.country_of_origin:
                    entry.country_of_origin = str(meta["country"])[:2].upper()
                    entry.exporting_country = entry.country_of_origin
            elif fname in ("vessel_name", "vessel") and not entry.vessel_name:
                entry.vessel_name = val_str
            elif fname in ("voyage_number", "voyage") and not entry.voyage_number:
                entry.voyage_number = val_str
            elif fname == "port_of_loading" and not entry.foreign_port:
                entry.foreign_port = val_str
            elif fname in ("port_of_discharge", "port_of_unlading", "port_of_entry"):
                entry.port_of_unlading = val_str
                if val_str.isdigit() and len(val_str) == 4:
                    entry.port_code = val_str
                    entry.port_of_entry = val_str
            elif fname == "country_of_origin" and not entry.country_of_origin:
                entry.country_of_origin = val_str[:2].upper()
            elif fname == "total_invoice_value":
                try:
                    cleaned_num = "".join(c for c in val_str if c.isdigit() or c == ".")
                    if cleaned_num:
                        invoice_values.append(Decimal(cleaned_num))
                except Exception:
                    pass
            elif fname.startswith("cargo_item"):
                hts_code = ""
                if isinstance(meta, dict):
                    hts_code = str(meta.get("hts_code") or meta.get("hs_code") or "").strip()
                if not hts_code and "HTS" in val_str:
                    parts = val_str.split("HTS")[-1].strip().split()
                    if parts:
                        hts_code = parts[0].strip()
                dedup_key = (hts_code, val_str)
                if dedup_key in seen_cargo:
                    continue
                seen_cargo.add(dedup_key)

                qty = float(meta["quantity"]) if isinstance(meta, dict) and meta.get("quantity") is not None else 0.0
                unit = str(meta.get("unit") or "PCS") if isinstance(meta, dict) else "PCS"
                raw_wt = (meta.get("gross_weight_kg") or meta.get("weight")) if isinstance(meta, dict) else None
                weight = float(raw_wt) if raw_wt is not None else 0.0
                origin = (
                    (str(meta.get("country_of_origin"))[:2].upper() if isinstance(meta, dict) and meta.get("country_of_origin") else None)
                    or entry.country_of_origin
                )
                item_val = Decimal("0.00")
                if isinstance(meta, dict) and meta.get("total_value"):
                    try:
                        item_val = Decimal(str(meta["total_value"]))
                    except Exception:
                        item_val = Decimal("0.00")

                digits = "".join(c for c in hts_code if c.isdigit())
                verified_rate = hts_rates.get(hts_code) if hts_code in hts_rates else hts_rates.get(digits)
                rate_verified = verified_rate is not None
                rate = verified_rate if verified_rate is not None else cls._get_duty_rate(hts_code)

                line_items.append({
                    "line_number": len(line_items) + 1,
                    "hts_number": hts_code or None,
                    "description": val_str,
                    "quantity": qty,
                    "unit": unit,
                    "gross_weight": weight,
                    "country_of_origin": origin,
                    "entered_value": item_val,
                    "duty_rate": rate,
                    "rate_verified": rate_verified,
                    "duty_amount": (item_val * Decimal(str(rate))).quantize(Decimal("0.01")),
                })

        # Only distribute extracted invoice total across lines when a real positive invoice value was extracted
        total_inv = max(invoice_values) if invoice_values else entry.total_entered_value

        if line_items:
            current_sum = sum(item["entered_value"] for item in line_items)
            if current_sum <= Decimal("0.00") and total_inv > Decimal("0.00"):
                per_line = (total_inv / Decimal(len(line_items))).quantize(Decimal("0.01"))
                for item in line_items:
                    item["entered_value"] = per_line
                    item["duty_amount"] = (per_line * Decimal(str(item["duty_rate"]))).quantize(Decimal("0.01"))
                entry.validation_warnings.append(
                    "Line-item values were apportioned evenly from total invoice value — verify individual line values"
                )

            entry.line_items = line_items
            entry.total_entered_value = sum(item["entered_value"] for item in line_items)
            entry.total_duty = sum(item["duty_amount"] for item in line_items)
        else:
            entry.total_entered_value = total_inv
    
    @classmethod
    def _get_duty_rate(cls, hts_code: str) -> float:
        """Fallback advisory chapter duty rate when HTS code is not in hts_codes DB table."""
        if not hts_code:
            return 0.0
        
        chapter = hts_code[:2] if len(hts_code) >= 2 else ""
        return cls.ADVISORY_CHAPTER_RATES.get(chapter, 0.0)
    
    @classmethod
    def _calculate_duties(cls, entry: EntryPrepData) -> None:
        """Calculate MPF, HMF, and total duties (only when entered value > 0)."""
        if entry.total_entered_value <= Decimal("0.00"):
            entry.total_mpf = Decimal("0.00")
            entry.total_hmf = Decimal("0.00")
            entry.grand_total = Decimal("0.00")
            return

        value = float(entry.total_entered_value)
        
        # Merchandise Processing Fee (FY2026 CBP caps)
        mpf = Decimal(str(value * cls.MPF_RATE)).quantize(Decimal("0.01"))
        entry.total_mpf = max(cls.MPF_MIN, min(cls.MPF_MAX, mpf))
        
        # Harbor Maintenance Fee (ocean shipments)
        entry.total_hmf = Decimal(str(value * cls.HMF_RATE)).quantize(Decimal("0.01"))
        
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
        """Add validation warnings under 19 USC 1641 broker reasonable care."""
        if not entry.filer_code:
            entry.validation_warnings.append("Missing CBP 3-character broker filer code (configure BROKER_FILER_CODE)")
        if not entry.importer_name:
            entry.validation_warnings.append("Missing importer name")
        if not entry.importer_of_record_number:
            entry.validation_warnings.append("Missing Importer of Record EIN / CBP number")
        if not entry.master_bill:
            entry.validation_warnings.append("Missing bill of lading")
        if not entry.port_of_entry and not entry.port_code:
            entry.validation_warnings.append("Missing 4-digit CBP port of entry")
        if not entry.country_of_origin and not entry.foreign_port:
            entry.validation_warnings.append("Missing country of origin")
        if entry.total_entered_value <= 0:
            entry.validation_warnings.append("No declared value extracted — enter verified commercial invoice value")
        if len(entry.line_items) == 0:
            entry.validation_warnings.append("No line items — add commercial invoice lines and HTS classifications")
        
        # Check line items
        for item in entry.line_items:
            ln = item.get("line_number", "?")
            if not item.get("hts_number"):
                entry.validation_warnings.append(
                    f"Line {ln}: Missing 10-digit HTS classification"
                )
            elif not item.get("rate_verified"):
                entry.validation_warnings.append(
                    f"Line {ln}: HTS {item.get('hts_number')} duty rate not verified against USITC tariff table"
                )
            if not item.get("country_of_origin"):
                entry.validation_warnings.append(
                    f"Line {ln}: Missing ISO 2-letter country of origin"
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

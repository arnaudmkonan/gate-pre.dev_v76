"""
Entry Creation Service.

Bridges the gap between Document-Driven workflow and Entry workflow.
Creates Entry records from Shipments and their linked documents.

Key responsibilities:
1. Map Shipment/Document fields to Entry fields
2. Create EntryLine records from InvoiceLine records
3. Calculate duties using DutyCalculatorService
4. Trigger compliance checks after creation
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID
import logging

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entry import Entry, EntryLine, EntryDocument, EntryParty, EntrySource, EntryStatus, PartyRole
from app.models.gold_records import Shipment, ShipmentDocument, CommercialInvoice, InvoiceLine
from app.models.document_metadata import DocumentMetadata
from app.models.silver_records import Party

logger = logging.getLogger(__name__)


# ==================== Field Mappings ====================

# Maps Shipment fields to Entry fields
SHIPMENT_TO_ENTRY_MAPPING = {
    "entry_number": "entry_number",
    "bol_number": "bill_of_lading",
    "awb_number": "bill_of_lading",  # Fallback for air shipments
    "container_numbers": "container_numbers",
    "importer_name": "importer_of_record_name",
    "exporter_name": "ultimate_consignee_name",
    "port_of_entry": "port_of_entry",
    "origin": "foreign_port_of_lading",
    "destination": "port_of_unlading",
    "total_declared_value": "total_entered_value",
    "total_duty": "total_duty",
    "currency": "currency",
    "arrival_date": "import_date",
    "entry_date": "entry_date",
}

# Maps extracted document keys to Entry fields
DOCUMENT_KEY_TO_ENTRY_MAPPING = {
    "ENTRY_NUM": "entry_number",
    "BOL_NUM": "bill_of_lading",
    "MASTER_BOL": "master_bill",
    "HOUSE_BOL": "house_bill",
    "AWB_NUM": "bill_of_lading",
    "CONTAINER_NUM": "container_numbers",  # Append to array
    "VESSEL_NAME": "vessel_name",
    "VOYAGE_NUM": "voyage_flight_number",
    "PORT_LOADING": "foreign_port_of_lading",
    "PORT_DISCHARGE": "port_of_entry",
    "IMPORTER_NAME": "importer_of_record_name",
    "CONSIGNEE_NAME": "ultimate_consignee_name",
    "VENDOR_NAME": "seller_name",  # Custom field in metadata
}


# ==================== Result Classes ====================

@dataclass
class EntryCreationResult:
    """Result of entry creation operation."""
    success: bool
    entry: Optional[Entry] = None
    entry_id: Optional[UUID] = None
    line_count: int = 0
    total_value: Decimal = Decimal("0")
    total_duty: Decimal = Decimal("0")
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    source_documents: List[UUID] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "entry_id": str(self.entry_id) if self.entry_id else None,
            "line_count": self.line_count,
            "total_value": float(self.total_value),
            "total_duty": float(self.total_duty),
            "errors": self.errors,
            "warnings": self.warnings,
            "source_documents": [str(d) for d in self.source_documents],
        }


# ==================== Service Classes ====================

class EntryCreationService:
    """
    Async service for creating Entry records from Shipments.

    Usage:
        async with get_async_db() as session:
            service = EntryCreationService(session)
            result = await service.create_entry_from_shipment(shipment_id)
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_entry_from_shipment(
        self,
        shipment_id: UUID,
        entry_type: str = "01",  # Default: Consumption
        assigned_to: Optional[str] = None,
        auto_calculate_duties: bool = True,
    ) -> EntryCreationResult:
        """
        Create an Entry from a Shipment and its linked documents.

        Args:
            shipment_id: UUID of the Shipment
            entry_type: CBP entry type code (default "01" = Consumption)
            assigned_to: User/broker to assign the entry to
            auto_calculate_duties: Whether to calculate duties automatically

        Returns:
            EntryCreationResult with created entry or errors
        """
        result = EntryCreationResult(success=False)

        try:
            # 1. Load Shipment with relationships
            shipment = await self._load_shipment(shipment_id)
            if not shipment:
                result.errors.append(f"Shipment {shipment_id} not found")
                return result

            # 2. Check if Entry already exists for this Shipment
            existing = await self._check_existing_entry(shipment_id)
            if existing:
                result.errors.append(f"Entry already exists for shipment: {existing.entry_number or existing.id}")
                result.entry_id = existing.id
                return result

            # 3. Load linked documents and extract data
            document_data = await self._load_document_data(shipment)

            # 4. Create Entry record
            entry = await self._create_entry(
                shipment=shipment,
                document_data=document_data,
                entry_type=entry_type,
                assigned_to=assigned_to,
            )

            # 5. Create EntryLine records from invoices
            lines = await self._create_entry_lines(entry, shipment, document_data)
            result.line_count = len(lines)

            # 6. Link source documents
            await self._link_documents(entry, shipment)
            result.source_documents = [doc.document_id for doc in entry.documents]

            # 7. Calculate totals
            entry.calculate_totals()

            # 8. Calculate duties if requested
            if auto_calculate_duties:
                await self._calculate_duties(entry)

            # 9. Create party records
            await self._create_parties(entry, shipment, document_data)

            # 10. Commit
            self.session.add(entry)
            await self.session.commit()
            await self.session.refresh(entry)

            result.success = True
            result.entry = entry
            result.entry_id = entry.id
            result.total_value = entry.total_entered_value or Decimal("0")
            result.total_duty = entry.total_amount_due or Decimal("0")

            logger.info(f"Created Entry {entry.id} from Shipment {shipment_id} with {result.line_count} lines")

        except Exception as e:
            logger.exception(f"Error creating entry from shipment {shipment_id}")
            result.errors.append(str(e))
            await self.session.rollback()

        return result

    async def _load_shipment(self, shipment_id: UUID) -> Optional[Shipment]:
        """Load shipment with all relationships."""
        stmt = (
            select(Shipment)
            .options(
                selectinload(Shipment.linked_documents),
                selectinload(Shipment.invoices).selectinload(CommercialInvoice.lines),
                selectinload(Shipment.shipper),
                selectinload(Shipment.consignee),
            )
            .where(Shipment.id == shipment_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _check_existing_entry(self, shipment_id: UUID) -> Optional[Entry]:
        """Check if an entry already exists for this shipment."""
        stmt = select(Entry).where(Entry.shipment_id == shipment_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _load_document_data(self, shipment: Shipment) -> Dict[str, Any]:
        """
        Load and aggregate data from linked documents.

        Returns dict with extracted fields from all documents.
        """
        data = {
            "keys": {},  # Aggregated document keys
            "invoices": [],
            "line_items": [],
            "parties": {},
        }

        # Load document keys from document_keys table
        from app.models.document_key import DocumentKey

        doc_ids = [link.document_id for link in shipment.linked_documents]
        if doc_ids:
            stmt = select(DocumentKey).where(DocumentKey.document_id.in_(doc_ids))
            result = await self.session.execute(stmt)
            keys = result.scalars().all()

            for key in keys:
                key_type = key.key_type
                if key_type not in data["keys"]:
                    data["keys"][key_type] = []
                data["keys"][key_type].append(key.key_value)

        # Process invoices
        for invoice in shipment.invoices:
            data["invoices"].append({
                "invoice_num": invoice.invoice_num,
                "vendor_id": invoice.vendor_id,
                "buyer_id": invoice.buyer_id,
                "total_amount": invoice.total_amount,
            })
            for line in invoice.lines:
                data["line_items"].append({
                    "invoice_id": invoice.id,
                    "line_num": line.line_num,
                    "description": line.description,
                    "hs_code": line.hs_code,
                    "quantity": line.quantity,
                    "unit_price": line.unit_price,
                    "amount": line.amount,
                })

        return data

    async def _create_entry(
        self,
        shipment: Shipment,
        document_data: Dict[str, Any],
        entry_type: str,
        assigned_to: Optional[str],
    ) -> Entry:
        """Create the Entry record with mapped fields."""
        keys = document_data.get("keys", {})

        # Get first value from each key type
        def first_key(key_type: str) -> Optional[str]:
            values = keys.get(key_type, [])
            return values[0] if values else None

        # Get all values from key type (for arrays)
        def all_keys(key_type: str) -> List[str]:
            return keys.get(key_type, [])

        entry = Entry(
            # Source tracking
            source_type=EntrySource.DOCUMENT_EXTRACTION.value,
            source_reference=str(shipment.id),
            shipment_id=shipment.id,

            # Entry identification
            entry_type=entry_type,
            entry_number=first_key("ENTRY_NUM") or shipment.entry_number,

            # Status
            status=EntryStatus.DRAFT.value,
            assigned_to=assigned_to,

            # Transport information
            bill_of_lading=first_key("BOL_NUM") or shipment.bol_number,
            master_bill=first_key("MASTER_BOL"),
            house_bill=first_key("HOUSE_BOL"),
            container_numbers=all_keys("CONTAINER_NUM") or shipment.container_numbers or [],
            vessel_name=first_key("VESSEL_NAME"),
            voyage_flight_number=first_key("VOYAGE_NUM"),

            # Port information
            foreign_port_of_lading=first_key("PORT_LOADING") or shipment.origin,
            port_of_entry=first_key("PORT_DISCHARGE") or shipment.port_of_entry,
            port_of_unlading=shipment.destination,

            # Party information
            importer_of_record_name=first_key("IMPORTER_NAME") or shipment.importer_name,
            ultimate_consignee_name=first_key("CONSIGNEE_NAME") or shipment.exporter_name,

            # Dates
            import_date=shipment.arrival_date,
            entry_date=shipment.entry_date or datetime.now(timezone.utc),

            # Financial
            total_entered_value=shipment.total_declared_value or Decimal("0"),
            currency=shipment.currency or "USD",
        )

        return entry

    async def _create_entry_lines(
        self,
        entry: Entry,
        shipment: Shipment,
        document_data: Dict[str, Any],
    ) -> List[EntryLine]:
        """Create EntryLine records from invoice line items."""
        lines = []
        line_number = 1

        for item in document_data.get("line_items", []):
            # Normalize HTS code
            hts_code = self._normalize_hts(item.get("hs_code"))

            line = EntryLine(
                entry_id=entry.id,
                line_number=line_number,
                hts_code=hts_code,
                product_description=item.get("description"),
                quantity_1=item.get("quantity"),
                entered_value=item.get("amount") or (
                    (item.get("quantity") or 0) * (item.get("unit_price") or 0)
                ),
                dutiable_value=item.get("amount"),
                source_document_id=item.get("invoice_id"),
                raw_extraction_data=item,
            )

            entry.lines.append(line)
            lines.append(line)
            line_number += 1

        return lines

    def _normalize_hts(self, hts_code: Optional[str]) -> Optional[str]:
        """Normalize HTS code to 10-digit format."""
        if not hts_code:
            return None
        # Remove dots, spaces, dashes
        clean = "".join(c for c in hts_code if c.isdigit())
        # Pad to 10 digits if needed
        if len(clean) < 10:
            clean = clean.ljust(10, "0")
        return clean[:10]  # Truncate if longer

    async def _link_documents(self, entry: Entry, shipment: Shipment) -> None:
        """Link source documents to the entry."""
        for link in shipment.linked_documents:
            # Get document metadata
            stmt = select(DocumentMetadata).where(DocumentMetadata.id == link.document_id)
            result = await self.session.execute(stmt)
            doc_meta = result.scalar_one_or_none()

            entry_doc = EntryDocument(
                entry_id=entry.id,
                document_id=link.document_id,
                document_type=doc_meta.document_type if doc_meta else None,
                is_primary=link.link_method == "auto",
            )
            entry.documents.append(entry_doc)

    async def _calculate_duties(self, entry: Entry) -> None:
        """Calculate duties for all line items."""
        from app.services.duty_calculator_service import DutyCalculatorService

        try:
            calc = DutyCalculatorService(self.session)
            for line in entry.lines:
                if line.hts_code and line.entered_value:
                    breakdown = await calc.calculate_line_duty(
                        hts_code=line.hts_code,
                        entered_value=line.entered_value,
                        quantity=line.quantity_1 or Decimal("0"),
                        country_of_origin=line.country_of_origin or "CN",
                    )
                    line.duty_rate = breakdown.base_duty_rate
                    line.duty_amount = breakdown.base_duty_amount
                    line.section_301_rate = breakdown.section_301_rate
                    line.section_301_duty = breakdown.section_301_amount
                    line.total_line_duty = breakdown.total_duty
        except Exception as e:
            logger.warning(f"Duty calculation failed: {e}")

    async def _create_parties(
        self,
        entry: Entry,
        shipment: Shipment,
        document_data: Dict[str, Any],
    ) -> None:
        """Create EntryParty records from shipment parties."""
        # Importer
        if shipment.importer_name:
            importer = EntryParty(
                entry_id=entry.id,
                role=PartyRole.IMPORTER_OF_RECORD.value,
                name=shipment.importer_name,
                party_id=shipment.consignee_id,
            )
            entry.parties.append(importer)

        # Shipper/Seller
        if shipment.exporter_name:
            shipper = EntryParty(
                entry_id=entry.id,
                role=PartyRole.SHIPPER.value,
                name=shipment.exporter_name,
                party_id=shipment.shipper_id,
            )
            entry.parties.append(shipper)


class EntryCreationServiceSync:
    """
    Synchronous version for use in Celery workers.
    """

    def __init__(self, session):
        self.session = session

    def create_entry_from_shipment(
        self,
        shipment_id: UUID,
        entry_type: str = "01",
        assigned_to: Optional[str] = None,
        auto_calculate_duties: bool = True,
    ) -> EntryCreationResult:
        """Synchronous entry creation."""
        result = EntryCreationResult(success=False)

        try:
            # Load shipment
            shipment = self.session.query(Shipment).options(
                selectinload(Shipment.linked_documents),
                selectinload(Shipment.invoices).selectinload(CommercialInvoice.lines),
            ).filter(Shipment.id == shipment_id).first()

            if not shipment:
                result.errors.append(f"Shipment {shipment_id} not found")
                return result

            # Check existing
            existing = self.session.query(Entry).filter(Entry.shipment_id == shipment_id).first()
            if existing:
                result.errors.append(f"Entry already exists for shipment")
                result.entry_id = existing.id
                return result

            # Load document keys
            from app.models.document_key import DocumentKey
            doc_ids = [link.document_id for link in shipment.linked_documents]
            keys_data = {}
            if doc_ids:
                keys = self.session.query(DocumentKey).filter(DocumentKey.document_id.in_(doc_ids)).all()
                for key in keys:
                    if key.key_type not in keys_data:
                        keys_data[key.key_type] = []
                    keys_data[key.key_type].append(key.key_value)

            # Create entry
            entry = Entry(
                source_type=EntrySource.DOCUMENT_EXTRACTION.value,
                source_reference=str(shipment.id),
                shipment_id=shipment.id,
                entry_type=entry_type,
                status=EntryStatus.DRAFT.value,
                assigned_to=assigned_to,
                bill_of_lading=keys_data.get("BOL_NUM", [None])[0] or shipment.bol_number,
                master_bill=keys_data.get("MASTER_BOL", [None])[0],
                house_bill=keys_data.get("HOUSE_BOL", [None])[0],
                container_numbers=keys_data.get("CONTAINER", []) or shipment.container_numbers or [],
                vessel_name=keys_data.get("VESSEL_NAME", [None])[0],
                importer_of_record_name=keys_data.get("IMPORTER_NAME", [None])[0] or shipment.importer_name,
                port_of_entry=shipment.port_of_entry,
                total_entered_value=shipment.total_declared_value or Decimal("0"),
                currency=shipment.currency or "USD",
                import_date=shipment.arrival_date,
            )

            # Create lines from invoices
            line_number = 1
            for invoice in shipment.invoices:
                for line_item in invoice.lines:
                    hts_code = self._normalize_hts(line_item.hs_code)
                    entry_line = EntryLine(
                        entry=entry,
                        line_number=line_number,
                        hts_code=hts_code,
                        product_description=line_item.description,
                        quantity_1=line_item.quantity,
                        entered_value=line_item.amount,
                        dutiable_value=line_item.amount,
                    )
                    entry.lines.append(entry_line)
                    line_number += 1

            entry.calculate_totals()

            self.session.add(entry)
            self.session.commit()
            self.session.refresh(entry)

            result.success = True
            result.entry = entry
            result.entry_id = entry.id
            result.line_count = len(entry.lines)
            result.total_value = entry.total_entered_value or Decimal("0")

            logger.info(f"Created Entry {entry.id} from Shipment {shipment_id}")

        except Exception as e:
            logger.exception(f"Error creating entry from shipment {shipment_id}")
            result.errors.append(str(e))
            self.session.rollback()

        return result

    def _normalize_hts(self, hts_code: Optional[str]) -> Optional[str]:
        if not hts_code:
            return None
        clean = "".join(c for c in hts_code if c.isdigit())
        if len(clean) < 10:
            clean = clean.ljust(10, "0")
        return clean[:10]

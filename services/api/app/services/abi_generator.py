"""
ABI Message Format Generator.

Generates ABI (Automated Broker Interface) messages for ACE transmission.
Based on CBP CATAIR (Customs and Trade Automated Interface Requirements).

Task 3.2 from ROADMAP_FULL_WORKFLOW.md

ABI Message Types:
- SE: Entry Summary (Primary filing)
- AD: Add Entry (New entry)
- RM: Replace/Amend Entry
- DE: Delete Entry
- RS: Response messages
- 10+2 ISF: Importer Security Filing

Record Types:
- 10: Entry Header
- 20: Port Header
- 30: Bill of Lading
- 40: Container
- 50: Line Item
- 60: Party
- 70: Value
- 90: Entry Summary Totals
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from decimal import Decimal
from dataclasses import dataclass, field
import logging
import re

logger = logging.getLogger(__name__)


# ============================================================================
# ABI Record Constants
# ============================================================================

# Message types
class ABIMessageType:
    ENTRY_SUMMARY = "SE"
    ADD_ENTRY = "AD"
    REPLACE_ENTRY = "RM"
    DELETE_ENTRY = "DE"
    ISF_10_2 = "IS"


# Record types per CATAIR
class ABIRecordType:
    HEADER = "10"
    PORT = "20"
    BOL = "30"
    CONTAINER = "40"
    LINE_ITEM = "50"
    PARTY = "60"
    VALUE = "70"
    FEES = "80"
    TOTALS = "90"


# Entry type codes (same as CBP)
ENTRY_TYPE_CODES = {
    "01": "Consumption",
    "02": "Consumption FTZ",
    "03": "Consumption ADD/CVD",
    "05": "Informal",
    "06": "Warehouse",
    "07": "FTZ Admission",
}

# Transport mode codes
TRANSPORT_MODES = {
    "10": "Vessel",
    "20": "Rail",
    "30": "Truck",
    "40": "Air",
    "50": "Mail",
    "60": "Passenger",
    "70": "Fixed Transport",
}

# Party role codes
PARTY_CODES = {
    "IOR": "Importer of Record",
    "CNE": "Consignee",
    "MFR": "Manufacturer",
    "SEL": "Seller",
    "BUY": "Buyer",
    "SHP": "Shipper",
    "NTF": "Notify Party",
}


# ============================================================================
# ABI Record Classes
# ============================================================================

@dataclass
class ABIRecord:
    """Base class for ABI record."""
    record_type: str = ""
    sequence: int = 0
    
    def to_abi_string(self) -> str:
        """Convert to ABI fixed-width format."""
        raise NotImplementedError
    
    def _pad(self, value: Any, length: int, pad_char: str = " ", align: str = "left") -> str:
        """Pad/truncate value to fixed length."""
        s = str(value or "")[:length]
        if align == "right":
            return s.rjust(length, pad_char)
        return s.ljust(length, pad_char)
    
    def _pad_num(self, value: Any, length: int, decimals: int = 0) -> str:
        """Pad numeric value with zeros."""
        if value is None:
            return "0" * length
        if decimals > 0:
            # Convert to cents (no decimal point in ABI)
            val = int(float(value) * (10 ** decimals))
        else:
            val = int(float(value))
        return str(val).zfill(length)[:length]


@dataclass
class ABIHeaderRecord(ABIRecord):
    """Record Type 10: Entry Header."""
    entry_number: str = ""
    entry_type: str = "01"
    filer_code: str = ""
    entry_date: Optional[date] = None
    import_date: Optional[date] = None
    surety_code: str = ""
    bond_type: str = "8"
    transmission_type: str = "SE"  # SE, AD, RM, DE
    
    def __post_init__(self):
        self.record_type = ABIRecordType.HEADER
    
    def to_abi_string(self) -> str:
        """Generate ABI header record (fixed 80 characters)."""
        entry_dt = self.entry_date.strftime("%Y%m%d") if self.entry_date else "".ljust(8)
        import_dt = self.import_date.strftime("%Y%m%d") if self.import_date else "".ljust(8)
        
        return "".join([
            self._pad(self.record_type, 2),           # 1-2: Record type
            self._pad(self.transmission_type, 2),     # 3-4: Transaction type
            self._pad(self.sequence, 5, align="right", pad_char="0"),  # 5-9: Sequence
            self._pad(self.filer_code, 3),            # 10-12: Filer code
            self._pad(self.entry_number, 15),         # 13-27: Entry number
            self._pad(self.entry_type, 2),            # 28-29: Entry type
            self._pad(entry_dt, 8),                   # 30-37: Entry date
            self._pad(import_dt, 8),                  # 38-45: Import date
            self._pad(self.surety_code, 3),           # 46-48: Surety code
            self._pad(self.bond_type, 1),             # 49: Bond type
            self._pad("", 31),                        # 50-80: Reserved/filler
        ])


@dataclass
class ABIPortRecord(ABIRecord):
    """Record Type 20: Port/Transport Information."""
    port_of_entry: str = ""
    port_of_unlading: str = ""
    foreign_port: str = ""
    mode_of_transport: str = ""
    carrier_code: str = ""
    vessel_name: str = ""
    voyage_number: str = ""
    
    def __post_init__(self):
        self.record_type = ABIRecordType.PORT
    
    def to_abi_string(self) -> str:
        return "".join([
            self._pad(self.record_type, 2),
            self._pad(self.sequence, 5, align="right", pad_char="0"),
            self._pad(self.port_of_entry, 4),
            self._pad(self.port_of_unlading, 4),
            self._pad(self.foreign_port, 5),
            self._pad(self.mode_of_transport, 2),
            self._pad(self.carrier_code, 4),
            self._pad(self.vessel_name, 25),
            self._pad(self.voyage_number, 10),
            self._pad("", 19),  # Filler
        ])


@dataclass
class ABIBillOfLadingRecord(ABIRecord):
    """Record Type 30: Bill of Lading."""
    bol_number: str = ""
    master_bill: str = ""
    house_bill: str = ""
    bol_type: str = "M"  # M=Master, H=House
    
    def __post_init__(self):
        self.record_type = ABIRecordType.BOL
    
    def to_abi_string(self) -> str:
        return "".join([
            self._pad(self.record_type, 2),
            self._pad(self.sequence, 5, align="right", pad_char="0"),
            self._pad(self.bol_type, 1),
            self._pad(self.bol_number, 50),
            self._pad(self.master_bill, 12),
            self._pad("", 10),  # Filler
        ])


@dataclass
class ABIContainerRecord(ABIRecord):
    """Record Type 40: Container."""
    container_number: str = ""
    seal_number: str = ""
    
    def __post_init__(self):
        self.record_type = ABIRecordType.CONTAINER
    
    def to_abi_string(self) -> str:
        return "".join([
            self._pad(self.record_type, 2),
            self._pad(self.sequence, 5, align="right", pad_char="0"),
            self._pad(self.container_number, 15),
            self._pad(self.seal_number, 15),
            self._pad("", 43),  # Filler
        ])


@dataclass
class ABILineItemRecord(ABIRecord):
    """Record Type 50: Line Item."""
    line_number: int = 1
    hts_code: str = ""
    country_of_origin: str = ""
    quantity_1: float = 0
    uom_1: str = ""
    quantity_2: float = 0
    uom_2: str = ""
    entered_value: float = 0
    duty_rate: float = 0
    duty_amount: float = 0
    manufacturer_id: str = ""
    spi_code: str = ""  # Special Program Indicator
    
    def __post_init__(self):
        self.record_type = ABIRecordType.LINE_ITEM
    
    def to_abi_string(self) -> str:
        # Clean HTS code (remove dots)
        hts = self.hts_code.replace(".", "")[:10]
        
        return "".join([
            self._pad(self.record_type, 2),
            self._pad(self.sequence, 5, align="right", pad_char="0"),
            self._pad_num(self.line_number, 3),           # Line number
            self._pad(hts, 10),                            # HTS code
            self._pad(self.country_of_origin, 2),          # Country
            self._pad_num(self.quantity_1, 10),            # Qty 1
            self._pad(self.uom_1, 3),                      # UOM 1
            self._pad_num(self.entered_value, 12, 2),      # Value (cents)
            self._pad_num(self.duty_rate * 100, 7, 4),     # Rate (4 decimals)
            self._pad_num(self.duty_amount, 12, 2),        # Duty (cents)
            self._pad(self.manufacturer_id, 10),           # MID
            self._pad(self.spi_code, 2),                   # SPI
            self._pad("", 2),                              # Filler
        ])


@dataclass
class ABIPartyRecord(ABIRecord):
    """Record Type 60: Party Information."""
    party_type: str = ""  # IOR, CNE, MFR, SEL
    name: str = ""
    address_1: str = ""
    address_2: str = ""
    city: str = ""
    state: str = ""
    postal_code: str = ""
    country: str = ""
    id_number: str = ""  # EIN, MID, etc.
    
    def __post_init__(self):
        self.record_type = ABIRecordType.PARTY
    
    def to_abi_string(self) -> str:
        return "".join([
            self._pad(self.record_type, 2),
            self._pad(self.sequence, 5, align="right", pad_char="0"),
            self._pad(self.party_type, 3),
            self._pad(self.name, 35),
            self._pad(self.id_number, 15),
            self._pad(self.country, 2),
            self._pad("", 18),  # Filler
        ])


@dataclass
class ABITotalsRecord(ABIRecord):
    """Record Type 90: Entry Summary Totals."""
    total_value: float = 0
    total_duty: float = 0
    total_other_fees: float = 0
    mpf: float = 0
    hmf: float = 0
    total_taxes: float = 0
    total_deposit: float = 0
    line_count: int = 0
    
    def __post_init__(self):
        self.record_type = ABIRecordType.TOTALS
    
    def to_abi_string(self) -> str:
        return "".join([
            self._pad(self.record_type, 2),
            self._pad(self.sequence, 5, align="right", pad_char="0"),
            self._pad_num(self.total_value, 15, 2),        # Total value
            self._pad_num(self.total_duty, 12, 2),         # Total duty
            self._pad_num(self.mpf, 10, 2),                # MPF
            self._pad_num(self.hmf, 10, 2),                # HMF
            self._pad_num(self.total_deposit, 15, 2),      # Total deposit
            self._pad_num(self.line_count, 3),             # Line count
            self._pad("", 8),                              # Filler
        ])


# ============================================================================
# ABI Message Container
# ============================================================================

@dataclass
class ABIMessage:
    """Complete ABI message with all records."""
    message_type: str = ABIMessageType.ENTRY_SUMMARY
    entry_id: str = ""
    records: List[ABIRecord] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    validation_errors: List[str] = field(default_factory=list)
    validation_warnings: List[str] = field(default_factory=list)
    
    def add_record(self, record: ABIRecord):
        """Add a record with auto-sequencing."""
        record.sequence = len(self.records) + 1
        self.records.append(record)
    
    def to_abi_string(self) -> str:
        """Generate complete ABI message."""
        return "\n".join(r.to_abi_string() for r in self.records)
    
    def validate(self) -> bool:
        """Validate message structure."""
        self.validation_errors = []
        self.validation_warnings = []
        
        # Must have header
        headers = [r for r in self.records if r.record_type == ABIRecordType.HEADER]
        if not headers:
            self.validation_errors.append("Missing header record (type 10)")
        
        # Must have totals
        totals = [r for r in self.records if r.record_type == ABIRecordType.TOTALS]
        if not totals:
            self.validation_errors.append("Missing totals record (type 90)")
        
        # Should have at least one line item
        lines = [r for r in self.records if r.record_type == ABIRecordType.LINE_ITEM]
        if not lines:
            self.validation_warnings.append("No line item records (type 50)")
        
        # Should have IOR party
        parties = [r for r in self.records if r.record_type == ABIRecordType.PARTY]
        ior_parties = [p for p in parties if isinstance(p, ABIPartyRecord) and p.party_type == "IOR"]
        if not ior_parties:
            self.validation_warnings.append("Missing Importer of Record party record")
        
        return len(self.validation_errors) == 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON response."""
        return {
            "message_type": self.message_type,
            "entry_id": self.entry_id,
            "created_at": self.created_at.isoformat(),
            "record_count": len(self.records),
            "records": [
                {
                    "type": r.record_type,
                    "sequence": r.sequence,
                    "content": r.to_abi_string(),
                }
                for r in self.records
            ],
            "validation": {
                "is_valid": len(self.validation_errors) == 0,
                "errors": self.validation_errors,
                "warnings": self.validation_warnings,
            },
            "abi_content": self.to_abi_string(),
        }


# ============================================================================
# ABI Message Generator
# ============================================================================

class ABIMessageGenerator:
    """
    Generates ABI messages from entry data.
    
    Supports:
    - SE (Entry Summary) - Primary filing
    - AD (Add Entry) - New entry submission
    - RM (Replace Entry) - Amendment
    """
    
    def generate_entry_summary(
        self,
        entry_data: Dict[str, Any],
        message_type: str = ABIMessageType.ENTRY_SUMMARY,
    ) -> ABIMessage:
        """
        Generate ABI Entry Summary message.
        
        Args:
            entry_data: Dictionary with entry information
            message_type: SE, AD, or RM
            
        Returns:
            ABIMessage with all records
        """
        message = ABIMessage(
            message_type=message_type,
            entry_id=entry_data.get("id", ""),
        )
        
        # 1. Header record
        header = ABIHeaderRecord(
            entry_number=entry_data.get("entry_number", ""),
            entry_type=entry_data.get("entry_type", "01"),
            filer_code=entry_data.get("filer_code", ""),
            entry_date=self._parse_date(entry_data.get("entry_date")),
            import_date=self._parse_date(entry_data.get("import_date")),
            surety_code=entry_data.get("surety_code", ""),
            bond_type=entry_data.get("bond_type", "8"),
            transmission_type=message_type,
        )
        message.add_record(header)
        
        # 2. Port record
        port = ABIPortRecord(
            port_of_entry=entry_data.get("port_of_entry", ""),
            port_of_unlading=entry_data.get("port_of_unlading", ""),
            foreign_port=entry_data.get("foreign_port_of_lading", ""),
            mode_of_transport=entry_data.get("mode_of_transport", ""),
            carrier_code=entry_data.get("carrier_code", ""),
            vessel_name=entry_data.get("vessel_name", ""),
            voyage_number=entry_data.get("voyage_flight_number", ""),
        )
        message.add_record(port)
        
        # 3. Bill of Lading
        if entry_data.get("bill_of_lading"):
            bol = ABIBillOfLadingRecord(
                bol_number=entry_data.get("bill_of_lading", ""),
                master_bill=entry_data.get("master_bill", ""),
                house_bill=entry_data.get("house_bill", ""),
            )
            message.add_record(bol)
        
        # 4. Containers
        containers = entry_data.get("container_numbers", []) or []
        for container_num in containers:
            container = ABIContainerRecord(container_number=container_num)
            message.add_record(container)
        
        # 5. Importer of Record party
        if entry_data.get("importer_of_record_name"):
            ior = ABIPartyRecord(
                party_type="IOR",
                name=entry_data.get("importer_of_record_name", ""),
                id_number=entry_data.get("importer_of_record_number", ""),
            )
            message.add_record(ior)
        
        # 6. Consignee
        if entry_data.get("ultimate_consignee_name"):
            cne = ABIPartyRecord(
                party_type="CNE",
                name=entry_data.get("ultimate_consignee_name", ""),
            )
            message.add_record(cne)
        
        # 7. Line items
        lines = entry_data.get("lines", [])
        for line_data in lines:
            line = ABILineItemRecord(
                line_number=line_data.get("line_number", 1),
                hts_code=line_data.get("hts_code", ""),
                country_of_origin=line_data.get("country_of_origin", ""),
                quantity_1=float(line_data.get("quantity_1", 0) or 0),
                uom_1=line_data.get("uom_1", "X"),
                entered_value=float(line_data.get("entered_value", 0) or 0),
                duty_rate=float(line_data.get("duty_rate", 0) or 0) / 100,  # Convert to decimal
                duty_amount=float(line_data.get("total_line_duty", 0) or 0),
                manufacturer_id=line_data.get("manufacturer_mid", ""),
                spi_code=line_data.get("special_program_indicator", ""),
            )
            message.add_record(line)
            
            # Manufacturer party for each line (if different)
            if line_data.get("manufacturer_name"):
                mfr = ABIPartyRecord(
                    party_type="MFR",
                    name=line_data.get("manufacturer_name", ""),
                    id_number=line_data.get("manufacturer_mid", ""),
                    country=line_data.get("country_of_origin", ""),
                )
                message.add_record(mfr)
        
        # 8. Totals record
        totals = ABITotalsRecord(
            total_value=float(entry_data.get("total_entered_value", 0) or 0),
            total_duty=float(entry_data.get("total_duty", 0) or 0),
            mpf=float(entry_data.get("mpf_amount", 0) or 0),
            hmf=float(entry_data.get("hmf_amount", 0) or 0),
            total_deposit=float(entry_data.get("total_amount_due", 0) or 0),
            line_count=len(lines),
        )
        message.add_record(totals)
        
        # Validate
        message.validate()
        
        return message
    
    def _parse_date(self, value) -> Optional[date]:
        """Parse date from various formats."""
        if not value:
            return None
        if isinstance(value, date):
            return value
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
            except:
                pass
            try:
                return datetime.strptime(value[:10], "%Y-%m-%d").date()
            except:
                pass
        return None


# ============================================================================
# ISF 10+2 Message Generator
# ============================================================================

@dataclass
class ISFMessage:
    """Importer Security Filing (10+2) message."""
    importer_of_record: str = ""
    consignee: str = ""
    seller: str = ""
    buyer: str = ""
    manufacturer: str = ""
    ship_to_party: str = ""
    container_stuffing_location: str = ""
    consolidator: str = ""
    hts_codes: List[str] = field(default_factory=list)
    bill_of_lading: str = ""
    
    # Carrier data (the +2)
    vessel: str = ""
    voyage: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "filing_type": "ISF-10",
            "importer_of_record": self.importer_of_record,
            "consignee": self.consignee,
            "seller": self.seller,
            "buyer": self.buyer,
            "manufacturer": self.manufacturer,
            "ship_to_party": self.ship_to_party,
            "container_stuffing_location": self.container_stuffing_location,
            "consolidator": self.consolidator,
            "hts_codes": self.hts_codes,
            "bill_of_lading": self.bill_of_lading,
            "carrier_info": {
                "vessel": self.vessel,
                "voyage": self.voyage,
            },
        }


# ============================================================================
# Convenience Functions
# ============================================================================

async def generate_abi_message(db, entry_id: str, message_type: str = "SE") -> ABIMessage:
    """
    Generate ABI message for an entry.
    
    Args:
        db: Database session
        entry_id: Entry UUID
        message_type: SE, AD, or RM
        
    Returns:
        ABIMessage
    """
    from uuid import UUID
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models.entry import Entry
    
    # Fetch entry with lines
    result = await db.execute(
        select(Entry)
        .options(
            selectinload(Entry.lines),
            selectinload(Entry.parties),
        )
        .where(Entry.id == UUID(entry_id))
    )
    entry = result.scalar_one_or_none()
    
    if not entry:
        raise ValueError(f"Entry {entry_id} not found")
    
    # Convert to dictionary
    entry_data = {
        "id": str(entry.id),
        "entry_number": entry.entry_number,
        "entry_type": entry.entry_type,
        "filer_code": entry.filer_code,
        "entry_date": entry.entry_date,
        "import_date": entry.import_date,
        "surety_code": entry.surety_code,
        "bond_type": entry.bond_type,
        "port_of_entry": entry.port_of_entry,
        "port_of_unlading": entry.port_of_unlading,
        "mode_of_transport": entry.mode_of_transport,
        "carrier_code": entry.carrier_code,
        "vessel_name": entry.vessel_name,
        "voyage_flight_number": entry.voyage_flight_number,
        "bill_of_lading": entry.bill_of_lading,
        "master_bill": entry.master_bill,
        "house_bill": entry.house_bill,
        "container_numbers": entry.container_numbers,
        "foreign_port_of_lading": entry.foreign_port_of_lading,
        "importer_of_record_name": entry.importer_of_record_name,
        "importer_of_record_number": entry.importer_of_record_number,
        "ultimate_consignee_name": entry.ultimate_consignee_name,
        "total_entered_value": float(entry.total_entered_value or 0),
        "total_duty": float(entry.total_duty or 0),
        "mpf_amount": float(entry.mpf_amount or 0),
        "hmf_amount": float(entry.hmf_amount or 0),
        "total_amount_due": float(entry.total_amount_due or 0),
        "lines": [],
    }
    
    # Add lines
    for line in entry.lines:
        entry_data["lines"].append({
            "line_number": line.line_number,
            "hts_code": line.hts_code,
            "country_of_origin": line.country_of_origin,
            "quantity_1": float(line.quantity_1 or 0),
            "uom_1": line.uom_1,
            "entered_value": float(line.entered_value or 0),
            "duty_rate": float(line.duty_rate or 0),
            "total_line_duty": float(line.total_line_duty or 0),
            "manufacturer_name": line.manufacturer_name,
            "manufacturer_mid": line.manufacturer_mid,
            "special_program_indicator": line.special_program_indicator,
        })
    
    # Generate message
    generator = ABIMessageGenerator()
    return generator.generate_entry_summary(entry_data, message_type)


# Singleton
abi_generator = ABIMessageGenerator()

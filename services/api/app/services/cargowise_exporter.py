"""
CargoWise Export Service.

Exports entry data in CargoWise-compatible XML format for integration
with CargoWise One World customs brokerage systems.

Supports:
- UniversalShipment format
- Entry Summary export
- Party/Address mapping
- Line item details

Usage:
    exporter = CargoWiseExporter(db)
    xml_content, filename = await exporter.export_entry(entry_id)
"""

import logging
import xml.etree.ElementTree as ET
from xml.dom import minidom
from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime
from uuid import UUID
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

logger = logging.getLogger(__name__)


# ============================================================================
# CargoWise XML Constants
# ============================================================================

CARGOWISE_NAMESPACE = "http://www.cargowise.com/Schemas/Universal/2011/11"
CARGOWISE_XSI = "http://www.w3.org/2001/XMLSchema-instance"


# Entry type mapping
ENTRY_TYPE_MAP = {
    "01": "CONSUMPTION",
    "02": "CONSUMPTION_FTZ",
    "03": "CONSUMPTION_ADD",
    "06": "WAREHOUSE",
    "07": "FTZ_ADMISSION",
}

# Party role mapping
PARTY_ROLE_MAP = {
    "IOR": "ImporterOfRecord",
    "CNE": "Consignee",
    "MFR": "Manufacturer",
    "SEL": "Seller",
    "BUY": "Buyer",
    "SHP": "Shipper",
}


# ============================================================================
# CargoWise XML Builder
# ============================================================================

class CargoWiseXMLBuilder:
    """Builds CargoWise-compatible XML documents."""
    
    def __init__(self):
        self.root = None
    
    def create_document(self, root_tag: str) -> ET.Element:
        """Create root element with namespaces."""
        self.root = ET.Element(root_tag)
        self.root.set("xmlns", CARGOWISE_NAMESPACE)
        self.root.set("xmlns:xsi", CARGOWISE_XSI)
        return self.root
    
    def add_element(
        self, 
        parent: ET.Element, 
        tag: str, 
        text: Optional[str] = None,
        attributes: Optional[Dict[str, str]] = None
    ) -> ET.Element:
        """Add child element with optional text and attributes."""
        elem = ET.SubElement(parent, tag)
        if text is not None:
            elem.text = str(text)
        if attributes:
            for key, value in attributes.items():
                elem.set(key, value)
        return elem
    
    def add_elements(
        self,
        parent: ET.Element,
        elements: Dict[str, Any]
    ) -> None:
        """Add multiple child elements from dictionary."""
        for key, value in elements.items():
            if value is not None:
                self.add_element(parent, key, str(value))
    
    def to_string(self, pretty: bool = True) -> str:
        """Convert to XML string."""
        xml_str = ET.tostring(self.root, encoding='unicode')
        if pretty:
            dom = minidom.parseString(xml_str)
            return dom.toprettyxml(indent="  ")
        return xml_str


# ============================================================================
# CargoWise Exporter
# ============================================================================

class CargoWiseExporter:
    """
    Exports customs entries to CargoWise XML format.
    
    Generates UniversalShipment format compatible with CargoWise One World.
    """
    
    def __init__(self, db: AsyncSession):
        """Initialize with database session."""
        self.db = db
        self.builder = CargoWiseXMLBuilder()
    
    async def export_entry(
        self,
        entry_id: str,
        include_documents: bool = False,
    ) -> Tuple[str, str]:
        """
        Export entry to CargoWise XML format.
        
        Args:
            entry_id: UUID of the entry
            include_documents: Include document references
            
        Returns:
            Tuple of (xml_content, filename)
        """
        from app.models.entry import Entry
        
        try:
            entry_uuid = UUID(entry_id)
        except ValueError:
            raise ValueError(f"Invalid entry ID: {entry_id}")
        
        # Fetch entry with related data
        result = await self.db.execute(
            select(Entry)
            .options(
                selectinload(Entry.lines),
                selectinload(Entry.parties),
            )
            .where(Entry.id == entry_uuid)
        )
        entry = result.scalar_one_or_none()
        
        if not entry:
            raise ValueError(f"Entry {entry_id} not found")
        
        # Build XML
        xml_content = self._build_universal_shipment(entry)
        
        # Generate filename
        entry_num = entry.entry_number or str(entry.id)[:8]
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"CW_Entry_{entry_num}_{timestamp}.xml"
        
        logger.info(f"Exported entry {entry_id} to CargoWise XML: {filename}")
        
        return xml_content, filename
    
    def _build_universal_shipment(self, entry) -> str:
        """Build UniversalShipment XML document."""
        builder = CargoWiseXMLBuilder()
        
        # Root element
        root = builder.create_document("UniversalShipment")
        
        # Shipment header
        shipment = builder.add_element(root, "Shipment")
        
        # Data context
        data_context = builder.add_element(shipment, "DataContext")
        builder.add_elements(data_context, {
            "Company": {"Code": "GATE"},
            "EnterpriseID": "GATE-CUSTOMS",
            "JobOwner": entry.assigned_to or "SYSTEM",
        })
        
        # Transport booking
        transport = builder.add_element(shipment, "TransportBooking")
        builder.add_elements(transport, {
            "LocalProcessing": "Import",
            "Direction": "Destination",
        })
        
        # Entry header info
        customs_entry = builder.add_element(shipment, "CustomsEntry")
        self._add_entry_header(builder, customs_entry, entry)
        self._add_parties(builder, customs_entry, entry)
        self._add_transport_info(builder, customs_entry, entry)
        self._add_line_items(builder, customs_entry, entry)
        self._add_totals(builder, customs_entry, entry)
        
        return builder.to_string(pretty=True)
    
    def _add_entry_header(self, builder: CargoWiseXMLBuilder, parent: ET.Element, entry) -> None:
        """Add entry header information."""
        header = builder.add_element(parent, "EntryHeader")
        
        entry_type = ENTRY_TYPE_MAP.get(entry.entry_type, "CONSUMPTION")
        
        builder.add_elements(header, {
            "EntryNumber": entry.entry_number,
            "EntryType": entry_type,
            "EntryTypeCode": entry.entry_type,
            "PortOfEntry": entry.port_of_entry,
            "PortOfUnlading": entry.port_of_unlading,
        })
        
        if entry.entry_date:
            builder.add_element(header, "EntryDate", 
                entry.entry_date.strftime("%Y-%m-%dT00:00:00"))
        
        if entry.import_date:
            builder.add_element(header, "ImportDate",
                entry.import_date.strftime("%Y-%m-%dT00:00:00"))
        
        # Bond information
        if entry.bond_type or entry.surety_code:
            bond = builder.add_element(header, "BondInfo")
            builder.add_elements(bond, {
                "BondType": entry.bond_type,
                "SuretyCode": entry.surety_code,
                "BondNumber": entry.bond_number,
            })
    
    def _add_parties(self, builder: CargoWiseXMLBuilder, parent: ET.Element, entry) -> None:
        """Add party information."""
        parties_elem = builder.add_element(parent, "Parties")
        
        # Importer of Record
        if entry.importer_of_record_name:
            ior = builder.add_element(parties_elem, "Party")
            builder.add_element(ior, "Role", "ImporterOfRecord")
            builder.add_element(ior, "Name", entry.importer_of_record_name)
            builder.add_element(ior, "IORNumber", entry.importer_of_record_number)
        
        # Ultimate Consignee
        if entry.ultimate_consignee_name:
            cne = builder.add_element(parties_elem, "Party")
            builder.add_element(cne, "Role", "Consignee")
            builder.add_element(cne, "Name", entry.ultimate_consignee_name)
        
        # Additional parties
        for party in entry.parties:
            party_elem = builder.add_element(parties_elem, "Party")
            role = PARTY_ROLE_MAP.get(party.role, party.role)
            builder.add_element(party_elem, "Role", role)
            builder.add_element(party_elem, "Name", party.name)
            
            if party.address_line_1:
                addr = builder.add_element(party_elem, "Address")
                builder.add_elements(addr, {
                    "Line1": party.address_line_1,
                    "City": party.city,
                    "StateProvince": party.state_province,
                    "PostalCode": party.postal_code,
                    "Country": party.country,
                })
    
    def _add_transport_info(self, builder: CargoWiseXMLBuilder, parent: ET.Element, entry) -> None:
        """Add transport/voyage information."""
        transport = builder.add_element(parent, "Transport")
        
        builder.add_elements(transport, {
            "ModeOfTransport": entry.mode_of_transport,
            "CarrierCode": entry.carrier_code,
            "VesselName": entry.vessel_name,
            "VoyageNumber": entry.voyage_flight_number,
            "BillOfLading": entry.bill_of_lading,
            "MasterBill": entry.master_bill,
            "HouseBill": entry.house_bill,
        })
        
        # Containers
        if entry.container_numbers:
            containers = builder.add_element(transport, "Containers")
            for container_num in entry.container_numbers:
                container = builder.add_element(containers, "Container")
                builder.add_element(container, "ContainerNumber", container_num)
    
    def _add_line_items(self, builder: CargoWiseXMLBuilder, parent: ET.Element, entry) -> None:
        """Add entry line items."""
        lines_elem = builder.add_element(parent, "LineItems")
        
        for line in entry.lines:
            line_elem = builder.add_element(lines_elem, "LineItem")
            
            builder.add_elements(line_elem, {
                "LineNumber": line.line_number,
                "HTSCode": line.hts_code,
                "HTSDescription": line.hts_description,
                "ProductDescription": line.product_description,
                "CountryOfOrigin": line.country_of_origin,
            })
            
            # Quantities
            qty = builder.add_element(line_elem, "Quantities")
            builder.add_elements(qty, {
                "Quantity1": float(line.quantity_1 or 0),
                "UOM1": line.uom_1,
                "Quantity2": float(line.quantity_2 or 0) if line.quantity_2 else None,
                "UOM2": line.uom_2,
                "GrossWeight": float(line.gross_weight or 0) if hasattr(line, 'gross_weight') and line.gross_weight else None,
                "NetWeight": float(line.net_weight or 0) if hasattr(line, 'net_weight') and line.net_weight else None,
            })
            
            # Values
            values = builder.add_element(line_elem, "Values")
            builder.add_elements(values, {
                "EnteredValue": float(line.entered_value or 0),
                "DutyRate": float(line.duty_rate or 0),
                "DutyAmount": float(line.duty_amount or 0),
                "Section301Duty": float(line.section_301_duty or 0) if hasattr(line, 'section_301_duty') and line.section_301_duty else None,
                "Section232Duty": float(line.section_232_duty or 0) if hasattr(line, 'section_232_duty') and line.section_232_duty else None,
                "ADDuty": float(line.add_duty or 0) if hasattr(line, 'add_duty') and line.add_duty else None,
                "CVDDuty": float(line.cvd_duty or 0) if hasattr(line, 'cvd_duty') and line.cvd_duty else None,
                "TotalLineDuty": float(line.total_line_duty or 0),
            })
            
            # Manufacturer
            if hasattr(line, 'manufacturer_name') and line.manufacturer_name:
                mfr = builder.add_element(line_elem, "Manufacturer")
                builder.add_elements(mfr, {
                    "Name": line.manufacturer_name,
                    "MID": line.manufacturer_mid,
                })
            
            # FTA
            if hasattr(line, 'fta_code') and line.fta_code:
                fta = builder.add_element(line_elem, "FTA")
                builder.add_elements(fta, {
                    "Code": line.fta_code,
                    "Eligible": "Y" if line.fta_eligible else "N",
                })
    
    def _add_totals(self, builder: CargoWiseXMLBuilder, parent: ET.Element, entry) -> None:
        """Add entry totals."""
        totals = builder.add_element(parent, "Totals")
        
        builder.add_elements(totals, {
            "LineCount": entry.line_count or len(entry.lines),
            "TotalEnteredValue": float(entry.total_entered_value or 0),
            "TotalDutiableValue": float(entry.total_dutiable_value or 0) if entry.total_dutiable_value else None,
            "TotalDuty": float(entry.total_duty or 0),
            "Section301Amount": float(entry.section_301_amount or 0) if entry.section_301_amount else None,
            "Section232Amount": float(entry.section_232_amount or 0) if entry.section_232_amount else None,
            "ADAmount": float(entry.add_amount or 0) if entry.add_amount else None,
            "CVDAmount": float(entry.cvd_amount or 0) if entry.cvd_amount else None,
            "MPF": float(entry.mpf_amount or 0),
            "HMF": float(entry.hmf_amount or 0),
            "TotalAmountDue": float(entry.total_amount_due or 0),
        })


# ============================================================================
# Convenience Functions
# ============================================================================

async def export_entry_to_cargowise(
    db: AsyncSession,
    entry_id: str,
) -> Tuple[str, str]:
    """
    Quick export function.
    
    Returns:
        Tuple of (xml_content, filename)
    """
    exporter = CargoWiseExporter(db)
    return await exporter.export_entry(entry_id)

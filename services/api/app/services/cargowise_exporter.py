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

    async def _load_entry(self, entry_id: str):
        """Load Entry with lines and parties."""
        from app.models.entry import Entry

        try:
            entry_uuid = UUID(entry_id)
        except ValueError:
            raise ValueError(f"Invalid entry ID: {entry_id}")

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
        return entry

    @staticmethod
    def _entry_to_summary_dict(entry) -> Dict[str, Any]:
        """Normalize an Entry ORM instance into a dictionary for PDF/Excel rendering."""
        return {
            "entry_number": entry.entry_number or f"DRAFT-{str(entry.id)[:8].upper()}",
            "entry_type": entry.entry_type or "01",
            "status": entry.status or "draft",
            "port_of_entry": entry.port_of_entry or "-",
            "port_of_unlading": entry.port_of_unlading or "-",
            "entry_date": entry.entry_date.strftime("%Y-%m-%d") if entry.entry_date else "-",
            "import_date": entry.import_date.strftime("%Y-%m-%d") if entry.import_date else "-",
            "mode_of_transport": entry.mode_of_transport or "10 (Vessel)",
            "carrier_code": entry.carrier_code or "-",
            "vessel_name": entry.vessel_name or "-",
            "voyage_number": entry.voyage_flight_number or "-",
            "bill_of_lading": entry.bill_of_lading or entry.master_bill or "-",
            "house_bill": entry.house_bill or "-",
            "bond_type": entry.bond_type or "8 (Continuous)",
            "surety_code": entry.surety_code or "-",
            "importer_name": entry.importer_of_record_name or "-",
            "importer_ior": entry.importer_of_record_number or "-",
            "consignee_name": entry.ultimate_consignee_name or entry.importer_of_record_name or "-",
            "country_of_origin": (entry.lines[0].country_of_origin if entry.lines else None) or "-",
            "totals": {
                "entered_value": float(entry.total_entered_value or 0),
                "base_duty": float(entry.total_duty or 0),
                "section_301": float(entry.section_301_amount or 0),
                "section_232": float(entry.section_232_amount or 0),
                "add_amount": float(entry.add_amount or 0),
                "cvd_amount": float(entry.cvd_amount or 0),
                "mpf": float(entry.mpf_amount or 0),
                "hmf": float(entry.hmf_amount or 0),
                "total_due": float(entry.total_amount_due or 0),
            },
            "lines": [
                {
                    "line_number": line.line_number,
                    "hts_code": line.hts_code or "-",
                    "description": line.product_description or line.hts_description or "-",
                    "country_of_origin": line.country_of_origin or "-",
                    "quantity": float(line.quantity_1 or 0),
                    "uom": line.uom_1 or "PCS",
                    "entered_value": float(line.entered_value or 0),
                    "duty_rate": float(line.duty_rate or 0),
                    "duty_amount": float(line.total_line_duty or line.duty_amount or 0),
                }
                for line in sorted(entry.lines, key=lambda x: x.line_number or 0)
            ],
            "parties": [
                {
                    "role": p.role,
                    "name": p.name,
                    "address": ", ".join(
                        filter(None, [p.address_line_1, p.city, p.state_province, p.postal_code, p.country])
                    ),
                }
                for p in (entry.parties or [])
            ],
        }

    async def export_entry_pdf(self, entry_id: str) -> Tuple[bytes, str]:
        """Export an Entry to a CBP Form 7501 Entry Summary PDF."""
        entry = await self._load_entry(entry_id)
        summary = self._entry_to_summary_dict(entry)
        pdf_bytes = self.build_7501_pdf_from_dict(summary)
        entry_num = entry.entry_number or str(entry.id)[:8]
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"CBP_7501_Entry_{entry_num}_{timestamp}.pdf"
        return pdf_bytes, filename

    async def export_entry_excel(self, entry_id: str) -> Tuple[bytes, str]:
        """Export an Entry to a multi-sheet CBP Form 7501 Excel (.xlsx) workbook."""
        entry = await self._load_entry(entry_id)
        summary = self._entry_to_summary_dict(entry)
        xlsx_bytes = self.build_7501_excel_from_dict(summary)
        entry_num = entry.entry_number or str(entry.id)[:8]
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"CBP_7501_Entry_{entry_num}_{timestamp}.xlsx"
        return xlsx_bytes, filename

    @staticmethod
    def build_7501_pdf_from_dict(summary: Dict[str, Any]) -> bytes:
        """Render a structured CBP Form 7501 Entry Summary PDF using ReportLab."""
        import io
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            leftMargin=0.45 * inch,
            rightMargin=0.45 * inch,
            topMargin=0.45 * inch,
            bottomMargin=0.45 * inch,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "Form7501Title",
            parent=styles["Heading1"],
            fontSize=14,
            leading=16,
            textColor=colors.HexColor("#111827"),
            spaceAfter=2,
        )
        subtitle_style = ParagraphStyle(
            "Form7501Subtitle",
            parent=styles["Normal"],
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#4B5563"),
            spaceAfter=10,
        )
        section_style = ParagraphStyle(
            "Form7501Section",
            parent=styles["Heading3"],
            fontSize=10,
            leading=12,
            textColor=colors.HexColor("#1E3A8A"),
            spaceBefore=8,
            spaceAfter=4,
        )
        cell_style = ParagraphStyle(
            "Form7501Cell",
            parent=styles["Normal"],
            fontSize=8,
            leading=10,
        )

        elements = []
        elements.append(Paragraph("DEPARTMENT OF HOMELAND SECURITY — U.S. Customs and Border Protection", subtitle_style))
        elements.append(Paragraph(f"CBP FORM 7501 — ENTRY SUMMARY ({summary.get('entry_number', 'DRAFT')})", title_style))
        elements.append(Spacer(1, 6))

        # Block 1: Header Grid
        header_data = [
            [
                f"1. Entry Number\n{summary.get('entry_number', '-')}",
                f"2. Entry Type\n{summary.get('entry_type', '01')}",
                f"3. Summary Date\n{summary.get('entry_date', '-')}",
                f"4. Port Code\n{summary.get('port_of_entry', '-')}",
            ],
            [
                f"5. Bond Type\n{summary.get('bond_type', '-')}",
                f"6. Mode of Transport\n{summary.get('mode_of_transport', '-')}",
                f"7. Importing Carrier / Vessel\n{summary.get('vessel_name', '-')} ({summary.get('carrier_code', '-')})",
                f"8. Import Date\n{summary.get('import_date', '-')}",
            ],
            [
                f"9. Master B/L or AWB\n{summary.get('bill_of_lading', '-')}",
                f"10. House B/L\n{summary.get('house_bill', '-')}",
                f"11. Country of Origin\n{summary.get('country_of_origin', '-')}",
                f"12. Filing Status\n{str(summary.get('status', 'draft')).upper()}",
            ],
        ]
        header_table = Table(header_data, colWidths=[1.9 * inch] * 4)
        header_table.setStyle(
            TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#9CA3AF")),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F9FAFB")),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ])
        )
        elements.append(header_table)

        # Block 2: Importer & Consignee
        elements.append(Paragraph("Importer of Record & Ultimate Consignee", section_style))
        party_data = [
            [
                f"Importer of Record:\n{summary.get('importer_name', '-')}\nIOR #: {summary.get('importer_ior', '-')}",
                f"Ultimate Consignee:\n{summary.get('consignee_name', '-')}",
            ]
        ]
        party_table = Table(party_data, colWidths=[3.8 * inch, 3.8 * inch])
        party_table.setStyle(
            TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#9CA3AF")),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ])
        )
        elements.append(party_table)

        # Block 3: Line Items (27-34 on Form 7501)
        elements.append(Paragraph("Line Items (27. Line # | 29. HTSUS No. | 30. Description | 31. Origin | 32. Qty | 33. Entered Value | 34. Duty)", section_style))
        line_rows = [["Line", "HTSUS Code", "Description of Merchandise", "Origin", "Quantity", "Entered Value", "Est. Duty"]]
        for line in summary.get("lines", []):
            line_rows.append([
                str(line.get("line_number", "")),
                str(line.get("hts_code", "-")),
                Paragraph(str(line.get("description", "-"))[:140], cell_style),
                str(line.get("country_of_origin", "-")),
                f"{float(line.get('quantity', 0)):,.2f} {line.get('uom', '')}".strip(),
                f"${float(line.get('entered_value', 0)):,.2f}",
                f"${float(line.get('duty_amount', 0)):,.2f}",
            ])
        if len(line_rows) == 1:
            line_rows.append(["-", "-", "No line items recorded", "-", "-", "$0.00", "$0.00"])

        lines_table = Table(
            line_rows,
            colWidths=[0.45 * inch, 1.05 * inch, 2.55 * inch, 0.55 * inch, 0.9 * inch, 1.05 * inch, 1.05 * inch],
        )
        lines_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D1D5DB")),
                ("ALIGN", (4, 1), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
            ])
        )
        elements.append(lines_table)

        # Block 4: Duty & Fee Totals (Boxes 37-40)
        elements.append(Paragraph("CBP Duty, Tax & Fee Summary (Boxes 37 - 40)", section_style))
        totals = summary.get("totals", {})
        totals_rows = [
            ["Total Entered Value", f"${float(totals.get('entered_value', 0)):,.2f}"],
            ["37. Base Customs Duty", f"${float(totals.get('base_duty', 0)):,.2f}"],
            ["Section 301 / 232 Trade Remedies", f"${float(totals.get('section_301', 0)) + float(totals.get('section_232', 0)):,.2f}"],
            ["AD / CVD Duties", f"${float(totals.get('add_amount', 0)) + float(totals.get('cvd_amount', 0)):,.2f}"],
            ["39. Merchandise Processing Fee (MPF - 499)", f"${float(totals.get('mpf', 0)):,.2f}"],
            ["39. Harbor Maintenance Fee (HMF - 501)", f"${float(totals.get('hmf', 0)):,.2f}"],
            ["40. TOTAL AMOUNT DUE CBP", f"${float(totals.get('total_due', 0)):,.2f}"],
        ]
        totals_table = Table(totals_rows, colWidths=[5.6 * inch, 2.0 * inch])
        totals_table.setStyle(
            TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#9CA3AF")),
                ("FONTNAME", (0, 0), (-1, -2), "Helvetica"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#EFF6FF")),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ])
        )
        elements.append(totals_table)

        doc.build(elements)
        return buffer.getvalue()

    @staticmethod
    def build_7501_excel_from_dict(summary: Dict[str, Any]) -> bytes:
        """Render a multi-sheet CBP Form 7501 Entry Summary Excel (.xlsx) workbook."""
        import io
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment

        wb = Workbook()

        # Sheet 1: Entry Summary Header & Totals
        ws_summary = wb.active
        ws_summary.title = "7501 Entry Summary"

        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
        bold_font = Font(bold=True)

        ws_summary.append(["CBP Form 7501 Field", "Value"])
        for cell in ws_summary[1]:
            cell.font = header_font
            cell.fill = header_fill

        totals = summary.get("totals", {})
        header_rows = [
            ("Entry Number", summary.get("entry_number", "-")),
            ("Entry Type", summary.get("entry_type", "01")),
            ("Filing Status", summary.get("status", "draft")),
            ("Port of Entry", summary.get("port_of_entry", "-")),
            ("Entry Date", summary.get("entry_date", "-")),
            ("Import Date", summary.get("import_date", "-")),
            ("Mode of Transport", summary.get("mode_of_transport", "-")),
            ("Carrier Code", summary.get("carrier_code", "-")),
            ("Vessel Name", summary.get("vessel_name", "-")),
            ("Master Bill of Lading", summary.get("bill_of_lading", "-")),
            ("House Bill of Lading", summary.get("house_bill", "-")),
            ("Importer of Record", summary.get("importer_name", "-")),
            ("Importer IOR Number", summary.get("importer_ior", "-")),
            ("Ultimate Consignee", summary.get("consignee_name", "-")),
            ("Country of Origin", summary.get("country_of_origin", "-")),
            ("Total Entered Value (USD)", float(totals.get("entered_value", 0))),
            ("Base Duty (USD)", float(totals.get("base_duty", 0))),
            ("Section 301 Duty (USD)", float(totals.get("section_301", 0))),
            ("Section 232 Duty (USD)", float(totals.get("section_232", 0))),
            ("MPF Fee (USD)", float(totals.get("mpf", 0))),
            ("HMF Fee (USD)", float(totals.get("hmf", 0))),
            ("Total Amount Due CBP (USD)", float(totals.get("total_due", 0))),
        ]
        for label, val in header_rows:
            ws_summary.append([label, val])
        ws_summary.column_dimensions["A"].width = 32
        ws_summary.column_dimensions["B"].width = 40

        # Sheet 2: Line Items
        ws_lines = wb.create_sheet(title="Line Items")
        line_headers = [
            "Line #",
            "HTS Code",
            "Product Description",
            "Country of Origin",
            "Quantity",
            "UOM",
            "Entered Value (USD)",
            "Duty Rate (%)",
            "Duty Amount (USD)",
        ]
        ws_lines.append(line_headers)
        for cell in ws_lines[1]:
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center")

        for line in summary.get("lines", []):
            ws_lines.append([
                line.get("line_number"),
                line.get("hts_code"),
                line.get("description"),
                line.get("country_of_origin"),
                float(line.get("quantity", 0)),
                line.get("uom", "PCS"),
                float(line.get("entered_value", 0)),
                float(line.get("duty_rate", 0)),
                float(line.get("duty_amount", 0)),
            ])

        for col_letter, width in [("A", 10), ("B", 16), ("C", 45), ("D", 18), ("E", 14), ("F", 10), ("G", 20), ("H", 15), ("I", 20)]:
            ws_lines.column_dimensions[col_letter].width = width

        # Sheet 3: Parties
        ws_parties = wb.create_sheet(title="Parties")
        ws_parties.append(["Role", "Name", "Address"])
        for cell in ws_parties[1]:
            cell.font = header_font
            cell.fill = header_fill
        ws_parties.append(["ImporterOfRecord", summary.get("importer_name", "-"), f"IOR: {summary.get('importer_ior', '-')}"])
        ws_parties.append(["UltimateConsignee", summary.get("consignee_name", "-"), ""])
        for p in summary.get("parties", []):
            ws_parties.append([p.get("role", ""), p.get("name", ""), p.get("address", "")])
        ws_parties.column_dimensions["A"].width = 22
        ws_parties.column_dimensions["B"].width = 35
        ws_parties.column_dimensions["C"].width = 50

        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()


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

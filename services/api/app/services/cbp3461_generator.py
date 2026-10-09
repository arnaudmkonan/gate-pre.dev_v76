"""
CBP Form 3461 Entry Manifest Generator  (Task 2.3)

Generates CBP Form 3461 (Entry / Immediate Delivery) which allows cargo
release before the formal Entry Summary (7501) is filed and duties are paid.

CBP 3461 is the pre-release form:
  - Must be filed within 5 days of arrival for ocean freight
  - Triggers examination/release decision
  - OGA (Other Government Agency) holds are noted here
  - Entry type determines if formal entry follows

Entry types supported:
  01 - Consumption     (most common — full duties due)
  03 - Consumption, Antidumping/CVD
  06 - FTZ Admission
  11 - Informal (<$800 de minimis)
  51 - Defense

This generator produces:
  a) A Python dict of all 3461 fields (for ACE ABI transmission)
  b) A PDF rendering via reportlab (for broker records)

Mirrors the pattern of cbp7501_generator.py.
"""
import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
    )
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    logger.warning("reportlab not installed. CBP 3461 PDF generation disabled.")


@dataclass
class CBP3461Data:
    """All fields required for CBP Form 3461 (Entry / Immediate Delivery)."""

    # ---- Header --------------------------------------------------------
    entry_number: Optional[str] = None             # Entry filer code + port + year + seq
    entry_type: str = "01"                         # Entry type code
    entry_date: Optional[date] = None
    port_of_entry: Optional[str] = None            # US port (CBSA port code)
    port_of_unlading: Optional[str] = None
    filer_code: Optional[str] = None               # CBP-assigned 3-char filer code

    # ---- Importer / Consignee ------------------------------------------
    importer_of_record_number: Optional[str] = None    # IOR / EIN
    importer_name: Optional[str] = None
    importer_address: Optional[str] = None
    consignee_name: Optional[str] = None
    consignee_address: Optional[str] = None

    # ---- Carrier / Transport -------------------------------------------
    carrier_code: Optional[str] = None             # SCAC code
    vessel_name: Optional[str] = None
    voyage_flight_number: Optional[str] = None
    master_bill_of_lading: Optional[str] = None
    house_bill_of_lading: Optional[str] = None
    bill_of_lading_date: Optional[date] = None
    country_of_origin: Optional[str] = None
    export_date: Optional[date] = None
    arrival_date: Optional[date] = None

    # ---- Bond ----------------------------------------------------------
    bond_type: str = "9"                           # 9 = Continuous bond
    surety_code: Optional[str] = None
    bond_number: Optional[str] = None

    # ---- Line Items ----------------------------------------------------
    line_items: List[Dict[str, Any]] = field(default_factory=list)

    # ---- Value Summary -------------------------------------------------
    total_entered_value: Decimal = Decimal("0.00")
    manifest_quantity: Optional[int] = None
    manifest_unit: Optional[str] = None           # CTN, PCS, etc.

    # ---- Special Actions -----------------------------------------------
    is_immediate_delivery: bool = False
    immediate_delivery_reason: Optional[str] = None   # PGA, Perishable, etc.
    ogas_required: List[str] = field(default_factory=list)  # FDA, EPA, USDA, etc.

    # ---- Broker Certification ------------------------------------------
    broker_license_number: Optional[str] = None
    certification_date: Optional[date] = None


class CBP3461Generator:
    """
    Generates CBP Form 3461 (Entry / Immediate Delivery) documents.

    Usage:
        gen = CBP3461Generator()
        data = CBP3461Data(entry_number="ABC-1234-001", ...)
        pdf_bytes = gen.generate_pdf(data)
        field_dict = gen.to_dict(data)
    """

    ENTRY_TYPE_LABELS = {
        "01": "Consumption",
        "03": "Consumption - AD/CVD",
        "06": "FTZ - Admission",
        "11": "Informal - De Minimis",
        "51": "Defense Material",
    }

    def to_dict(self, data: CBP3461Data) -> Dict[str, Any]:
        """
        Serialize CBP3461Data to a plain dict.

        Suitable for ABI transmission or API response.
        """
        return {
            "form": "CBP-3461",
            "entry_number": data.entry_number,
            "entry_type": data.entry_type,
            "entry_type_label": self.ENTRY_TYPE_LABELS.get(data.entry_type, "Other"),
            "entry_date": data.entry_date.isoformat() if data.entry_date else None,
            "port_of_entry": data.port_of_entry,
            "port_of_unlading": data.port_of_unlading,
            "filer_code": data.filer_code,
            "importer_of_record_number": data.importer_of_record_number,
            "importer_name": data.importer_name,
            "importer_address": data.importer_address,
            "consignee_name": data.consignee_name,
            "consignee_address": data.consignee_address,
            "carrier_code": data.carrier_code,
            "vessel_name": data.vessel_name,
            "voyage_flight_number": data.voyage_flight_number,
            "master_bill_of_lading": data.master_bill_of_lading,
            "house_bill_of_lading": data.house_bill_of_lading,
            "country_of_origin": data.country_of_origin,
            "export_date": data.export_date.isoformat() if data.export_date else None,
            "arrival_date": data.arrival_date.isoformat() if data.arrival_date else None,
            "bond_type": data.bond_type,
            "surety_code": data.surety_code,
            "total_entered_value": str(data.total_entered_value),
            "manifest_quantity": data.manifest_quantity,
            "manifest_unit": data.manifest_unit,
            "is_immediate_delivery": data.is_immediate_delivery,
            "immediate_delivery_reason": data.immediate_delivery_reason,
            "ogas_required": data.ogas_required,
            "line_items": data.line_items,
            "broker_license_number": data.broker_license_number,
            "certification_date": (
                data.certification_date.isoformat() if data.certification_date else None
            ),
        }

    def validate(self, data: CBP3461Data) -> List[str]:
        """
        Return a list of validation errors.  Empty list = OK to file.
        """
        errors = []
        if not data.entry_type:
            errors.append("entry_type is required")
        if data.entry_type not in self.ENTRY_TYPE_LABELS:
            errors.append(f"Unknown entry_type '{data.entry_type}'. "
                          f"Valid: {list(self.ENTRY_TYPE_LABELS)}")
        if not data.importer_of_record_number:
            errors.append("importer_of_record_number (IOR/EIN) is required")
        if not data.port_of_entry:
            errors.append("port_of_entry is required")
        if not data.master_bill_of_lading:
            errors.append("master_bill_of_lading is required")
        if data.total_entered_value <= 0:
            errors.append("total_entered_value must be > 0")
        if not data.filer_code:
            errors.append("filer_code (broker's CBP 3-char code) is required")
        return errors

    def is_informal_entry(self, data: CBP3461Data) -> bool:
        """Return True if this qualifies as an informal (de minimis) entry."""
        return (
            data.entry_type == "11"
            or data.total_entered_value <= Decimal("800.00")
        )

    def generate_pdf(self, data: CBP3461Data) -> bytes:
        """
        Generate a CBP 3461 PDF.

        Returns PDF bytes.  Raises RuntimeError if reportlab is absent.
        """
        if not REPORTLAB_AVAILABLE:
            raise RuntimeError(
                "reportlab is required for PDF generation. "
                "Install with: pip install reportlab"
            )

        buf = BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=letter,
            rightMargin=0.5 * inch,
            leftMargin=0.5 * inch,
            topMargin=0.5 * inch,
            bottomMargin=0.5 * inch,
        )

        styles = getSampleStyleSheet()
        elements = []

        # ---- Title block -----------------------------------------------
        elements.append(
            Paragraph(
                "<b>U.S. CUSTOMS AND BORDER PROTECTION</b><br/>"
                "ENTRY / IMMEDIATE DELIVERY — CBP FORM 3461",
                styles["Title"],
            )
        )
        elements.append(Spacer(1, 0.1 * inch))

        # ---- Header table ----------------------------------------------
        header_data = [
            ["Entry Number", data.entry_number or "TBD",
             "Entry Type", f"{data.entry_type} - {self.ENTRY_TYPE_LABELS.get(data.entry_type, '')}"],
            ["Entry Date", (data.entry_date or date.today()).isoformat(),
             "Port of Entry", data.port_of_entry or ""],
            ["Filer Code", data.filer_code or "",
             "Port of Unlading", data.port_of_unlading or ""],
        ]
        t = Table(header_data, colWidths=[1.5 * inch, 2.5 * inch, 1.5 * inch, 2 * inch])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey),
            ("BACKGROUND", (2, 0), (2, -1), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 0.1 * inch))

        # ---- Importer block --------------------------------------------
        imp_data = [
            ["IMPORTER OF RECORD", "", "CONSIGNEE", ""],
            ["Name", data.importer_name or "", "Name", data.consignee_name or ""],
            ["IOR Number", data.importer_of_record_number or "", "Address", data.consignee_address or ""],
            ["Address", data.importer_address or "", "", ""],
        ]
        t2 = Table(imp_data, colWidths=[1.5 * inch, 2.5 * inch, 1.5 * inch, 2 * inch])
        t2.setStyle(TableStyle([
            ("SPAN", (0, 0), (1, 0)),
            ("SPAN", (2, 0), (3, 0)),
            ("BACKGROUND", (0, 0), (3, 0), colors.grey),
            ("TEXTCOLOR", (0, 0), (3, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
        ]))
        elements.append(t2)
        elements.append(Spacer(1, 0.1 * inch))

        # ---- Transport block -------------------------------------------
        trans_data = [
            ["CARRIER / VESSEL INFORMATION", "", "", ""],
            ["Carrier SCAC", data.carrier_code or "", "Vessel", data.vessel_name or ""],
            ["Voyage/Flight", data.voyage_flight_number or "", "Arrival Date",
             data.arrival_date.isoformat() if data.arrival_date else ""],
            ["Master Bill", data.master_bill_of_lading or "", "House Bill",
             data.house_bill_of_lading or ""],
        ]
        t3 = Table(trans_data, colWidths=[1.5 * inch, 2.5 * inch, 1.5 * inch, 2 * inch])
        t3.setStyle(TableStyle([
            ("SPAN", (0, 0), (3, 0)),
            ("BACKGROUND", (0, 0), (3, 0), colors.grey),
            ("TEXTCOLOR", (0, 0), (3, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
        ]))
        elements.append(t3)
        elements.append(Spacer(1, 0.1 * inch))

        # ---- Value summary ---------------------------------------------
        val_data = [
            ["Total Entered Value", f"${data.total_entered_value:,.2f}",
             "Manifest Qty", f"{data.manifest_quantity or ''} {data.manifest_unit or ''}"],
            ["Bond Type", data.bond_type,
             "OGAs Required", ", ".join(data.ogas_required) if data.ogas_required else "None"],
        ]
        t4 = Table(val_data, colWidths=[2 * inch, 2 * inch, 2 * inch, 1.5 * inch])
        t4.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey),
            ("BACKGROUND", (2, 0), (2, -1), colors.lightgrey),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
        ]))
        elements.append(t4)
        elements.append(Spacer(1, 0.15 * inch))

        # ---- Certification block ---------------------------------------
        cert_text = (
            f"I hereby make application for entry of the merchandise described above "
            f"and certify that the information is true and accurate to the best of my knowledge.\n\n"
            f"Broker License: {data.broker_license_number or '___________'}    "
            f"Date: {(data.certification_date or date.today()).isoformat()}"
        )
        elements.append(Paragraph(cert_text, styles["Normal"]))

        doc.build(elements)
        return buf.getvalue()

    @classmethod
    def from_entry(cls, entry: Any) -> "CBP3461Data":
        """
        Build a CBP3461Data from an `Entry` ORM object.

        This provides a convenient factory for the API route.
        """
        data = CBP3461Data(
            entry_number=getattr(entry, "entry_number", None),
            entry_type=getattr(entry, "entry_type", "01"),
            entry_date=getattr(entry, "entry_date", date.today()),
            port_of_entry=getattr(entry, "port_of_entry", None),
            port_of_unlading=getattr(entry, "port_of_unlading", None),
            filer_code=getattr(entry, "filer_code", None),
            importer_of_record_number=getattr(entry, "importer_of_record_number", None),
            importer_name=getattr(entry, "importer_name", None),
            importer_address=getattr(entry, "importer_address", None),
            consignee_name=getattr(entry, "consignee_name", None),
            consignee_address=getattr(entry, "consignee_address", None),
            carrier_code=getattr(entry, "carrier_code", None),
            vessel_name=getattr(entry, "vessel_name", None),
            voyage_number=None,
            master_bill_of_lading=getattr(entry, "master_bill", None),
            house_bill_of_lading=getattr(entry, "house_bill", None),
            country_of_origin=getattr(entry, "country_of_origin", None),
            bond_type=getattr(entry, "bond_type", "9"),
            total_entered_value=Decimal(str(getattr(entry, "total_entered_value", 0) or 0)),
            broker_license_number=getattr(entry, "broker_license_number", None),
        )
        return data

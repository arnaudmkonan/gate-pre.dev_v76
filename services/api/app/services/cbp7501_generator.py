"""
CBP Form 7501 Generator Service.

Generates CBP Form 7501 (Entry Summary) PDF from entry data.

Task 3.1 from ROADMAP_FULL_WORKFLOW.md
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from decimal import Decimal
from io import BytesIO
import logging

logger = logging.getLogger(__name__)

# Check for reportlab
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
    from reportlab.pdfgen import canvas
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    logger.warning("reportlab not installed. PDF generation will not be available.")


# CBP 7501 Field Positions (simplified layout)
# In a real implementation, these would match the exact form layout

class CBP7501Generator:
    """
    Generates CBP Form 7501 Entry Summary PDFs.
    
    The form includes:
    - Header: Entry number, filer info, port, entry type
    - Importer/Consignee information
    - Transport information
    - Line items with HTS, description, quantity, value, duty
    - Totals: Duty, MPF, HMF, total deposit
    - Certification block
    """
    
    def __init__(self):
        if not REPORTLAB_AVAILABLE:
            raise ImportError("reportlab is required for PDF generation. Install with: pip install reportlab")
        
        self.styles = getSampleStyleSheet()
        self.page_width, self.page_height = letter
        
        # Custom styles
        self.styles.add(ParagraphStyle(
            name='BoxTitle',
            fontSize=7,
            leading=8,
            textColor=colors.grey,
        ))
        self.styles.add(ParagraphStyle(
            name='BoxValue',
            fontSize=9,
            leading=10,
        ))
        self.styles.add(ParagraphStyle(
            name='FormTitle',
            fontSize=14,
            leading=16,
            alignment=1,
            fontName='Helvetica-Bold',
        ))
    
    def generate(self, entry_data: Dict[str, Any]) -> bytes:
        """
        Generate CBP 7501 PDF from entry data.
        
        Args:
            entry_data: Dictionary containing entry information
            
        Returns:
            PDF bytes
        """
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=0.5*inch,
            leftMargin=0.5*inch,
            topMargin=0.5*inch,
            bottomMargin=0.5*inch,
        )
        
        story = []
        
        # Header
        story.extend(self._build_header(entry_data))
        story.append(Spacer(1, 0.1*inch))
        
        # Entry identification block
        story.extend(self._build_entry_block(entry_data))
        story.append(Spacer(1, 0.1*inch))
        
        # Importer/Consignee block
        story.extend(self._build_importer_block(entry_data))
        story.append(Spacer(1, 0.1*inch))
        
        # Transport block
        story.extend(self._build_transport_block(entry_data))
        story.append(Spacer(1, 0.1*inch))
        
        # Line items
        story.extend(self._build_line_items(entry_data))
        story.append(Spacer(1, 0.15*inch))
        
        # Totals block
        story.extend(self._build_totals_block(entry_data))
        story.append(Spacer(1, 0.2*inch))
        
        # Certification block
        story.extend(self._build_certification_block(entry_data))
        
        doc.build(story)
        
        pdf_bytes = buffer.getvalue()
        buffer.close()
        
        return pdf_bytes
    
    def _build_header(self, entry_data: Dict) -> List:
        """Build form header."""
        elements = []
        
        # Form header
        header_data = [
            [
                Paragraph("DEPARTMENT OF HOMELAND SECURITY", self.styles['BoxTitle']),
                Paragraph("CBP FORM 7501", self.styles['FormTitle']),
                Paragraph(f"OMB No. 1651-0022", self.styles['BoxTitle']),
            ],
            [
                Paragraph("U.S. Customs and Border Protection", self.styles['BoxTitle']),
                Paragraph("ENTRY SUMMARY", self.styles['FormTitle']),
                Paragraph(f"Expiration Date: 12/31/2027", self.styles['BoxTitle']),
            ],
        ]
        
        header_table = Table(header_data, colWidths=[2*inch, 3.5*inch, 2*inch])
        header_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'CENTER'),
            ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        elements.append(header_table)
        elements.append(HRFlowable(width="100%", thickness=2, color=colors.black))
        
        return elements
    
    def _build_entry_block(self, entry_data: Dict) -> List:
        """Build entry identification block (boxes 1-9)."""
        elements = []
        
        # Row 1: Entry Number, Entry Type, Summary Date, etc.
        entry_number = entry_data.get('entry_number', '')
        entry_type = entry_data.get('entry_type', '01')
        entry_date = entry_data.get('entry_date', '')
        if isinstance(entry_date, datetime):
            entry_date = entry_date.strftime('%m/%d/%Y')
        
        port = entry_data.get('port_of_entry', '')
        
        box_data = [
            # Labels
            [
                Paragraph("1. Entry Number", self.styles['BoxTitle']),
                Paragraph("2. Entry Type", self.styles['BoxTitle']),
                Paragraph("3. Summary Date", self.styles['BoxTitle']),
                Paragraph("4. Surety No.", self.styles['BoxTitle']),
                Paragraph("5. Bond Type", self.styles['BoxTitle']),
            ],
            # Values
            [
                Paragraph(str(entry_number or 'PENDING'), self.styles['BoxValue']),
                Paragraph(self._get_entry_type_name(entry_type), self.styles['BoxValue']),
                Paragraph(str(entry_date or datetime.now().strftime('%m/%d/%Y')), self.styles['BoxValue']),
                Paragraph(str(entry_data.get('surety_code', '')), self.styles['BoxValue']),
                Paragraph(str(entry_data.get('bond_type', '8-Continuous')), self.styles['BoxValue']),
            ],
        ]
        
        table = Table(box_data, colWidths=[2*inch, 1.2*inch, 1.2*inch, 1.4*inch, 1.4*inch])
        table.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        
        elements.append(table)
        
        # Row 2: Port, Import Date, Arrival Date
        box_data2 = [
            [
                Paragraph("6. Port Code", self.styles['BoxTitle']),
                Paragraph("7. Entry Date", self.styles['BoxTitle']),
                Paragraph("8. Import Date", self.styles['BoxTitle']),
                Paragraph("9. Country of Origin", self.styles['BoxTitle']),
            ],
            [
                Paragraph(str(port or ''), self.styles['BoxValue']),
                Paragraph(str(entry_date or ''), self.styles['BoxValue']),
                Paragraph(self._format_date(entry_data.get('import_date')), self.styles['BoxValue']),
                Paragraph(str(entry_data.get('primary_country', '')), self.styles['BoxValue']),
            ],
        ]
        
        table2 = Table(box_data2, colWidths=[1.8*inch, 1.8*inch, 1.8*inch, 1.8*inch])
        table2.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        
        elements.append(table2)
        
        return elements
    
    def _build_importer_block(self, entry_data: Dict) -> List:
        """Build importer/consignee information block."""
        elements = []
        
        importer_name = entry_data.get('importer_of_record_name', '')
        importer_number = entry_data.get('importer_of_record_number', '')
        consignee_name = entry_data.get('ultimate_consignee_name', '')
        
        box_data = [
            [
                Paragraph("10. Importer of Record Name & Address", self.styles['BoxTitle']),
                Paragraph("11. Importer Number", self.styles['BoxTitle']),
            ],
            [
                Paragraph(str(importer_name or ''), self.styles['BoxValue']),
                Paragraph(str(importer_number or ''), self.styles['BoxValue']),
            ],
            [
                Paragraph("12. Consignee Name & Address (If different from importer)", self.styles['BoxTitle']),
                Paragraph("", self.styles['BoxTitle']),
            ],
            [
                Paragraph(str(consignee_name or 'SAME AS ABOVE'), self.styles['BoxValue']),
                Paragraph("", self.styles['BoxValue']),
            ],
        ]
        
        table = Table(box_data, colWidths=[5.2*inch, 2*inch])
        table.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('SPAN', (0, 2), (1, 2)),
            ('SPAN', (0, 3), (1, 3)),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        
        elements.append(table)
        
        return elements
    
    def _build_transport_block(self, entry_data: Dict) -> List:
        """Build transport information block."""
        elements = []
        
        box_data = [
            [
                Paragraph("13. Carrier Code", self.styles['BoxTitle']),
                Paragraph("14. Mode of Transport", self.styles['BoxTitle']),
                Paragraph("15. Vessel/Aircraft Name", self.styles['BoxTitle']),
                Paragraph("16. Bill of Lading/AWB", self.styles['BoxTitle']),
            ],
            [
                Paragraph(str(entry_data.get('carrier_code', '')), self.styles['BoxValue']),
                Paragraph(self._get_transport_mode(entry_data.get('mode_of_transport')), self.styles['BoxValue']),
                Paragraph(str(entry_data.get('vessel_name', '')), self.styles['BoxValue']),
                Paragraph(str(entry_data.get('bill_of_lading', '')), self.styles['BoxValue']),
            ],
        ]
        
        table = Table(box_data, colWidths=[1.4*inch, 1.6*inch, 2.2*inch, 2*inch])
        table.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        
        elements.append(table)
        
        return elements
    
    def _build_line_items(self, entry_data: Dict) -> List:
        """Build line items table."""
        elements = []
        
        # Section header
        elements.append(Paragraph("LINE ITEMS", self.styles['Heading2']))
        
        # Header row
        header = [
            "Line",
            "HTS Number",
            "Description",
            "CO",
            "Qty",
            "Value",
            "Rate",
            "Duty",
        ]
        
        # Data rows
        lines = entry_data.get('lines', [])
        table_data = [header]
        
        for line in lines:
            row = [
                str(line.get('line_number', '')),
                str(line.get('hts_code', '')),
                str(line.get('product_description', line.get('hts_description', '')))[:40],
                str(line.get('country_of_origin', '')),
                f"{float(line.get('quantity_1', 0)):,.0f}",
                f"${float(line.get('entered_value', 0)):,.2f}",
                f"{float(line.get('duty_rate', 0)):.2f}%",
                f"${float(line.get('total_line_duty', 0)):,.2f}",
            ]
            table_data.append(row)
        
        # If no lines, add a placeholder
        if not lines:
            table_data.append(['1', '', 'No line items', '', '', '$0.00', '0.00%', '$0.00'])
        
        col_widths = [0.4*inch, 1*inch, 2.2*inch, 0.4*inch, 0.7*inch, 1*inch, 0.7*inch, 0.9*inch]
        
        table = Table(table_data, colWidths=col_widths)
        table.setStyle(TableStyle([
            # Header styling
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            
            # Data styling
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('ALIGN', (0, 1), (0, -1), 'CENTER'),  # Line number
            ('ALIGN', (3, 1), (3, -1), 'CENTER'),  # CO
            ('ALIGN', (4, 1), (4, -1), 'RIGHT'),   # Qty
            ('ALIGN', (5, 1), (5, -1), 'RIGHT'),   # Value
            ('ALIGN', (6, 1), (6, -1), 'RIGHT'),   # Rate
            ('ALIGN', (7, 1), (7, -1), 'RIGHT'),   # Duty
            
            # Grid
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        
        elements.append(table)
        
        return elements
    
    def _build_totals_block(self, entry_data: Dict) -> List:
        """Build totals block."""
        elements = []
        
        # Calculate totals
        total_value = float(entry_data.get('total_entered_value', 0))
        total_duty = float(entry_data.get('total_duty', 0))
        mpf = float(entry_data.get('mpf_amount', 0))
        hmf = float(entry_data.get('hmf_amount', 0))
        total_fee = float(entry_data.get('total_fee', mpf + hmf))
        section_301 = float(entry_data.get('section_301_amount', 0))
        section_232 = float(entry_data.get('section_232_amount', 0))
        add_cvd = float(entry_data.get('add_amount', 0)) + float(entry_data.get('cvd_amount', 0))
        total_deposit = float(entry_data.get('total_amount_due', total_duty + total_fee + section_301 + section_232 + add_cvd))
        
        totals_data = [
            [
                Paragraph("SUMMARY OF DUTIES, TAXES, AND FEES", self.styles['BoxTitle']),
                "", "", "",
            ],
            [
                "Total Entered Value:",
                f"${total_value:,.2f}",
                "Merchandise Processing Fee:",
                f"${mpf:,.2f}",
            ],
            [
                "Ordinary Customs Duty:",
                f"${total_duty:,.2f}",
                "Harbor Maintenance Fee:",
                f"${hmf:,.2f}",
            ],
            [
                "Section 301 Tariff:",
                f"${section_301:,.2f}",
                "Total Fees:",
                f"${total_fee:,.2f}",
            ],
            [
                "Section 232 Tariff:",
                f"${section_232:,.2f}",
                "",
                "",
            ],
            [
                "ADD/CVD:",
                f"${add_cvd:,.2f}",
                "",
                "",
            ],
            [
                "",
                "",
                Paragraph("<b>TOTAL DEPOSIT:</b>", self.styles['BoxValue']),
                Paragraph(f"<b>${total_deposit:,.2f}</b>", self.styles['BoxValue']),
            ],
        ]
        
        table = Table(totals_data, colWidths=[2*inch, 1.5*inch, 2*inch, 1.7*inch])
        table.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
            ('SPAN', (0, 0), (-1, 0)),
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('FONTNAME', (0, 1), (0, -1), 'Helvetica'),
            ('FONTNAME', (2, 1), (2, -1), 'Helvetica'),
            ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
            ('ALIGN', (3, 1), (3, -1), 'RIGHT'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('BACKGROUND', (2, -1), (-1, -1), colors.lightyellow),
        ]))
        
        elements.append(table)
        
        return elements
    
    def _build_certification_block(self, entry_data: Dict) -> List:
        """Build certification/signature block."""
        elements = []
        
        cert_text = """
        <b>DECLARATION OF IMPORTER OF RECORD (OWNER OR PURCHASER) OR AUTHORIZED AGENT</b>
        <br/><br/>
        I declare that I am the ☐ Importer of Record / ☐ Agent and that the information contained in this 
        document is accurate and complete. I understand that civil and criminal penalties may be imposed 
        for making false statements.
        """
        
        elements.append(Paragraph(cert_text, self.styles['Normal']))
        elements.append(Spacer(1, 0.2*inch))
        
        sig_data = [
            [
                "Signature:",
                "_" * 30,
                "Date:",
                entry_data.get('filed_at', datetime.now()).strftime('%m/%d/%Y') if isinstance(entry_data.get('filed_at'), datetime) else datetime.now().strftime('%m/%d/%Y'),
            ],
            [
                "Name:",
                str(entry_data.get('certified_by', '')),
                "Title:",
                str(entry_data.get('certified_title', 'Licensed Customs Broker')),
            ],
        ]
        
        table = Table(sig_data, colWidths=[1*inch, 3*inch, 0.7*inch, 2.5*inch])
        table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        
        elements.append(table)
        
        return elements
    
    def _get_entry_type_name(self, entry_type: str) -> str:
        """Get entry type description."""
        types = {
            "01": "01-Consumption",
            "02": "02-Consumption/FTZ",
            "03": "03-Consumption/ADD-CVD",
            "05": "05-Informal",
            "06": "06-Warehouse",
            "07": "07-FTZ Admission",
            "09": "09-Reconciliation",
            "22": "22-Drawback",
            "23": "23-Temp Import",
        }
        return types.get(entry_type, entry_type)
    
    def _get_transport_mode(self, mode: Optional[str]) -> str:
        """Get transport mode description."""
        if not mode:
            return ""
        modes = {
            "10": "10-Vessel",
            "20": "20-Rail",
            "30": "30-Truck",
            "40": "40-Air",
            "50": "50-Mail",
            "60": "60-Passenger",
        }
        return modes.get(mode, mode)
    
    def _format_date(self, dt) -> str:
        """Format date for form."""
        if not dt:
            return ""
        if isinstance(dt, datetime):
            return dt.strftime('%m/%d/%Y')
        if isinstance(dt, date):
            return dt.strftime('%m/%d/%Y')
        if isinstance(dt, str):
            return dt
        return str(dt)


async def generate_cbp_7501(db, entry_id: str) -> bytes:
    """
    Generate CBP 7501 PDF for an entry.
    
    Args:
        db: Database session
        entry_id: Entry UUID
        
    Returns:
        PDF bytes
    """
    from uuid import UUID
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models.entry import Entry, EntryLine
    
    # Fetch entry with lines
    result = await db.execute(
        select(Entry)
        .options(selectinload(Entry.lines))
        .where(Entry.id == UUID(entry_id))
    )
    entry = result.scalar_one_or_none()
    
    if not entry:
        raise ValueError(f"Entry {entry_id} not found")
    
    # Convert to dictionary
    entry_data = {
        'entry_number': entry.entry_number,
        'entry_type': entry.entry_type,
        'entry_date': entry.entry_date,
        'import_date': entry.import_date,
        'port_of_entry': entry.port_of_entry,
        'surety_code': entry.surety_code,
        'bond_type': entry.bond_type,
        'importer_of_record_name': entry.importer_of_record_name,
        'importer_of_record_number': entry.importer_of_record_number,
        'ultimate_consignee_name': entry.ultimate_consignee_name,
        'carrier_code': entry.carrier_code,
        'mode_of_transport': entry.mode_of_transport,
        'vessel_name': entry.vessel_name,
        'bill_of_lading': entry.bill_of_lading,
        'total_entered_value': float(entry.total_entered_value or 0),
        'total_duty': float(entry.total_duty or 0),
        'mpf_amount': float(entry.mpf_amount or 0),
        'hmf_amount': float(entry.hmf_amount or 0),
        'total_fee': float((entry.mpf_amount or 0) + (entry.hmf_amount or 0)),
        'section_301_amount': float(entry.section_301_amount or 0),
        'section_232_amount': float(entry.section_232_amount or 0),
        'add_amount': float(entry.add_amount or 0),
        'cvd_amount': float(entry.cvd_amount or 0),
        'total_amount_due': float(entry.total_amount_due or 0),
        'filed_at': entry.filed_at,
        'lines': [],
    }
    
    # Add line items
    for line in entry.lines:
        entry_data['lines'].append({
            'line_number': line.line_number,
            'hts_code': line.hts_code,
            'hts_description': line.hts_description,
            'product_description': line.product_description,
            'country_of_origin': line.country_of_origin,
            'quantity_1': float(line.quantity_1 or 0),
            'entered_value': float(line.entered_value or 0),
            'duty_rate': float(line.duty_rate or 0),
            'total_line_duty': float(line.total_line_duty or 0),
        })
    
    # Calculate primary country (most common in lines)
    if entry_data['lines']:
        countries = [l['country_of_origin'] for l in entry_data['lines'] if l['country_of_origin']]
        if countries:
            entry_data['primary_country'] = max(set(countries), key=countries.count)
    
    # Generate PDF
    generator = CBP7501Generator()
    return generator.generate(entry_data)


# Singleton for convenience
cbp7501_generator = CBP7501Generator() if REPORTLAB_AVAILABLE else None

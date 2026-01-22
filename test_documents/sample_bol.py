# Generate a sample Bill of Lading PDF for testing
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch

def create_bol():
    c = canvas.Canvas("sample_bol.pdf", pagesize=letter)
    width, height = letter

    # Header - Bill of Lading Title
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(width/2, height - 0.75*inch, "BILL OF LADING")

    c.setFont("Helvetica", 10)
    c.drawCentredString(width/2, height - 1*inch, "STRAIGHT BILL OF LADING - SHORT FORM - NOT NEGOTIABLE")

    # BOL Number and Date
    c.setFont("Helvetica-Bold", 11)
    c.drawString(5.5*inch, height - 1.5*inch, "BOL Number:")
    c.drawString(5.5*inch, height - 1.75*inch, "Date:")
    c.setFont("Helvetica", 11)
    c.drawString(6.5*inch, height - 1.5*inch, "BOL-2026-0042")
    c.drawString(6.5*inch, height - 1.75*inch, "January 21, 2026")

    # Shipper Section
    c.setFont("Helvetica-Bold", 11)
    c.drawString(0.75*inch, height - 1.5*inch, "SHIPPER (From):")
    c.setFont("Helvetica", 10)
    c.drawString(0.75*inch, height - 1.75*inch, "Pacific Manufacturing Co.")
    c.drawString(0.75*inch, height - 1.95*inch, "4500 Industrial Blvd, Suite 100")
    c.drawString(0.75*inch, height - 2.15*inch, "Los Angeles, CA 90058")
    c.drawString(0.75*inch, height - 2.35*inch, "Contact: John Miller")
    c.drawString(0.75*inch, height - 2.55*inch, "Phone: (310) 555-1234")

    # Consignee Section
    c.setFont("Helvetica-Bold", 11)
    c.drawString(0.75*inch, height - 3*inch, "CONSIGNEE (To):")
    c.setFont("Helvetica", 10)
    c.drawString(0.75*inch, height - 3.25*inch, "Eastern Distribution Center")
    c.drawString(0.75*inch, height - 3.45*inch, "789 Warehouse Road")
    c.drawString(0.75*inch, height - 3.65*inch, "Newark, NJ 07102")
    c.drawString(0.75*inch, height - 3.85*inch, "Contact: Sarah Johnson")
    c.drawString(0.75*inch, height - 4.05*inch, "Phone: (973) 555-9876")

    # Carrier Section
    c.setFont("Helvetica-Bold", 11)
    c.drawString(4.25*inch, height - 3*inch, "CARRIER:")
    c.setFont("Helvetica", 10)
    c.drawString(4.25*inch, height - 3.25*inch, "TransContinental Freight LLC")
    c.drawString(4.25*inch, height - 3.45*inch, "MC Number: MC-123456")
    c.drawString(4.25*inch, height - 3.65*inch, "SCAC Code: TCFL")
    c.drawString(4.25*inch, height - 3.85*inch, "Driver: Mike Thompson")
    c.drawString(4.25*inch, height - 4.05*inch, "Truck #: TRK-4521")

    # Horizontal line
    c.line(0.5*inch, height - 4.4*inch, width - 0.5*inch, height - 4.4*inch)

    # Shipment Details Table Header
    c.setFont("Helvetica-Bold", 9)
    c.drawString(0.75*inch, height - 4.65*inch, "Pieces")
    c.drawString(1.5*inch, height - 4.65*inch, "Packaging")
    c.drawString(2.75*inch, height - 4.65*inch, "Description of Goods")
    c.drawString(5*inch, height - 4.65*inch, "Weight (lbs)")
    c.drawString(6*inch, height - 4.65*inch, "Class")
    c.drawString(7*inch, height - 4.65*inch, "NMFC#")

    c.line(0.5*inch, height - 4.75*inch, width - 0.5*inch, height - 4.75*inch)

    # Shipment Items
    c.setFont("Helvetica", 9)
    items = [
        ("24", "Pallets", "Electronic Components - Printed Circuit Boards", "4,800", "85", "100610"),
        ("12", "Crates", "Industrial Control Panels - Class II", "2,400", "70", "133520"),
        ("48", "Cartons", "Electrical Connectors & Wiring Harnesses", "960", "92.5", "117860"),
        ("6", "Drums", "Industrial Lubricants (Non-Hazardous)", "1,200", "55", "145100"),
    ]

    y = height - 5*inch
    for pieces, pkg, desc, weight, freight_class, nmfc in items:
        c.drawString(0.75*inch, y, pieces)
        c.drawString(1.5*inch, y, pkg)
        c.drawString(2.75*inch, y, desc)
        c.drawString(5*inch, y, weight)
        c.drawString(6*inch, y, freight_class)
        c.drawString(7*inch, y, nmfc)
        y -= 0.3*inch

    c.line(0.5*inch, y - 0.1*inch, width - 0.5*inch, y - 0.1*inch)

    # Totals
    c.setFont("Helvetica-Bold", 10)
    c.drawString(0.75*inch, y - 0.35*inch, "TOTAL:")
    c.drawString(0.75*inch, y - 0.55*inch, "90 Pieces")
    c.drawString(5*inch, y - 0.35*inch, "Total Weight:")
    c.drawString(5*inch, y - 0.55*inch, "9,360 lbs")

    # Special Instructions
    c.setFont("Helvetica-Bold", 10)
    c.drawString(0.75*inch, y - 1*inch, "SPECIAL INSTRUCTIONS:")
    c.setFont("Helvetica", 9)
    c.drawString(0.75*inch, y - 1.2*inch, "- Delivery appointment required 24 hours in advance")
    c.drawString(0.75*inch, y - 1.4*inch, "- Inside delivery to Dock Door 5")
    c.drawString(0.75*inch, y - 1.6*inch, "- Liftgate service required")
    c.drawString(0.75*inch, y - 1.8*inch, "- Temperature controlled storage upon arrival")

    # Reference Numbers
    c.setFont("Helvetica-Bold", 10)
    c.drawString(4.25*inch, y - 1*inch, "REFERENCE NUMBERS:")
    c.setFont("Helvetica", 9)
    c.drawString(4.25*inch, y - 1.2*inch, "PO Number: PO-2026-88421")
    c.drawString(4.25*inch, y - 1.4*inch, "PRO Number: PRO-774521")
    c.drawString(4.25*inch, y - 1.6*inch, "Load Number: LD-2026-0042")
    c.drawString(4.25*inch, y - 1.8*inch, "Seal Number: SEAL-99871")

    # Freight Charges Section
    c.line(0.5*inch, y - 2.1*inch, width - 0.5*inch, y - 2.1*inch)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(0.75*inch, y - 2.35*inch, "FREIGHT CHARGES:")
    c.setFont("Helvetica", 9)
    c.drawString(0.75*inch, y - 2.55*inch, "Prepaid")
    c.drawRightString(3.5*inch, y - 2.35*inch, "Freight Rate: $2.85/cwt")
    c.drawRightString(3.5*inch, y - 2.55*inch, "Total Charges: $2,667.60")

    c.setFont("Helvetica-Bold", 10)
    c.drawString(4.25*inch, y - 2.35*inch, "Estimated Transit:")
    c.setFont("Helvetica", 9)
    c.drawString(5.75*inch, y - 2.35*inch, "3-5 Business Days")

    # Signatures Section
    c.line(0.5*inch, y - 2.85*inch, width - 0.5*inch, y - 2.85*inch)

    c.setFont("Helvetica-Bold", 9)
    c.drawString(0.75*inch, y - 3.1*inch, "SHIPPER SIGNATURE:")
    c.line(0.75*inch, y - 3.35*inch, 3.25*inch, y - 3.35*inch)
    c.drawString(0.75*inch, y - 3.5*inch, "Date: _______________")

    c.drawString(4.25*inch, y - 3.1*inch, "CARRIER SIGNATURE:")
    c.line(4.25*inch, y - 3.35*inch, 6.75*inch, y - 3.35*inch)
    c.drawString(4.25*inch, y - 3.5*inch, "Date: _______________")

    # Footer
    c.setFont("Helvetica", 8)
    c.drawCentredString(width/2, 0.5*inch, "This is to certify that the above named materials are properly classified, described, packaged, marked and labeled,")
    c.drawCentredString(width/2, 0.35*inch, "and are in proper condition for transportation according to applicable regulations of the DOT.")

    c.save()
    print("Created sample_bol.pdf")

if __name__ == "__main__":
    create_bol()

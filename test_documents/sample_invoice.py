# Generate a sample PDF invoice for testing
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch

def create_invoice():
    c = canvas.Canvas("sample_invoice.pdf", pagesize=letter)
    width, height = letter
    
    # Header
    c.setFont("Helvetica-Bold", 24)
    c.drawString(1*inch, height - 1*inch, "INVOICE")
    
    c.setFont("Helvetica", 12)
    c.drawString(1*inch, height - 1.5*inch, "Invoice Number: INV-2026-001")
    c.drawString(1*inch, height - 1.75*inch, "Date: January 21, 2026")
    
    # Bill To
    c.setFont("Helvetica-Bold", 12)
    c.drawString(1*inch, height - 2.5*inch, "Bill To:")
    c.setFont("Helvetica", 12)
    c.drawString(1*inch, height - 2.75*inch, "ACME Corporation")
    c.drawString(1*inch, height - 3*inch, "123 Business Street")
    c.drawString(1*inch, height - 3.25*inch, "New York, NY 10001")
    
    # Table Header
    c.setFont("Helvetica-Bold", 10)
    c.drawString(1*inch, height - 4*inch, "Description")
    c.drawString(4*inch, height - 4*inch, "Quantity")
    c.drawString(5*inch, height - 4*inch, "Unit Price")
    c.drawString(6*inch, height - 4*inch, "Total")
    
    # Line
    c.line(1*inch, height - 4.1*inch, 7*inch, height - 4.1*inch)
    
    # Items
    c.setFont("Helvetica", 10)
    items = [
        ("Document Processing Service", "100", "$5.00", "$500.00"),
        ("OCR Processing", "50", "$2.00", "$100.00"),
        ("API Access (Monthly)", "1", "$99.00", "$99.00"),
        ("Storage (10GB)", "1", "$25.00", "$25.00"),
    ]
    
    y = height - 4.4*inch
    for desc, qty, price, total in items:
        c.drawString(1*inch, y, desc)
        c.drawString(4*inch, y, qty)
        c.drawString(5*inch, y, price)
        c.drawString(6*inch, y, total)
        y -= 0.25*inch
    
    # Total
    c.line(1*inch, y - 0.1*inch, 7*inch, y - 0.1*inch)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(5*inch, y - 0.4*inch, "TOTAL:")
    c.drawString(6*inch, y - 0.4*inch, "$724.00")
    
    # Footer
    c.setFont("Helvetica", 10)
    c.drawString(1*inch, 1.5*inch, "Payment Terms: Net 30")
    c.drawString(1*inch, 1.25*inch, "Please remit payment to: DataEntry AI Platform, Inc.")
    
    c.save()
    print("Created sample_invoice.pdf")

if __name__ == "__main__":
    create_invoice()

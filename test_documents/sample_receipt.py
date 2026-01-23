"""Generate a sample receipt PDF for testing."""

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib import colors

def create_receipt_pdf(filename):
    """Create a realistic store receipt PDF."""
    # Create a narrower page to simulate receipt paper
    page_width = 3 * inch
    page_height = 8 * inch

    c = canvas.Canvas(filename, pagesize=(page_width, page_height))

    # Starting Y position from top
    y = page_height - 0.3 * inch
    line_height = 12

    def draw_centered_text(text, y_pos, font="Helvetica", size=10):
        c.setFont(font, size)
        text_width = c.stringWidth(text, font, size)
        x = (page_width - text_width) / 2
        c.drawString(x, y_pos, text)
        return y_pos - line_height

    def draw_left_text(text, y_pos, font="Helvetica", size=9):
        c.setFont(font, size)
        c.drawString(0.2 * inch, y_pos, text)
        return y_pos - line_height

    def draw_line_item(desc, qty, price, y_pos):
        c.setFont("Helvetica", 9)
        c.drawString(0.2 * inch, y_pos, desc)
        c.drawString(1.8 * inch, y_pos, str(qty))
        c.drawRightString(page_width - 0.2 * inch, y_pos, f"${price:.2f}")
        return y_pos - line_height

    def draw_total_line(label, amount, y_pos, bold=False):
        font = "Helvetica-Bold" if bold else "Helvetica"
        c.setFont(font, 10 if bold else 9)
        c.drawString(0.2 * inch, y_pos, label)
        c.drawRightString(page_width - 0.2 * inch, y_pos, f"${amount:.2f}")
        return y_pos - line_height

    def draw_separator(y_pos):
        c.setStrokeColor(colors.black)
        c.setLineWidth(0.5)
        c.line(0.2 * inch, y_pos, page_width - 0.2 * inch, y_pos)
        return y_pos - 8

    # Store Header
    y = draw_centered_text("SUPER MART", y, "Helvetica-Bold", 14)
    y = draw_centered_text("Your Neighborhood Store", y, "Helvetica", 8)
    y -= 5
    y = draw_centered_text("1234 Main Street", y, "Helvetica", 9)
    y = draw_centered_text("Springfield, IL 62701", y, "Helvetica", 9)
    y = draw_centered_text("(217) 555-0123", y, "Helvetica", 9)

    y = draw_separator(y - 5)

    # Transaction Info
    y = draw_left_text("Date: 01/22/2026    Time: 2:45 PM", y)
    y = draw_left_text("Receipt #: 00847291", y)
    y = draw_left_text("Cashier: Maria S.", y)
    y = draw_left_text("Register: 04", y)

    y = draw_separator(y - 5)

    # Column Headers
    c.setFont("Helvetica-Bold", 9)
    c.drawString(0.2 * inch, y, "Item")
    c.drawString(1.8 * inch, y, "Qty")
    c.drawRightString(page_width - 0.2 * inch, y, "Price")
    y -= line_height

    y = draw_separator(y)

    # Line Items
    items = [
        ("Organic Milk 1gal", 1, 5.99),
        ("Whole Wheat Bread", 2, 3.49),
        ("Bananas (lb)", 3, 0.59),
        ("Chicken Breast lb", 2, 8.99),
        ("Cheddar Cheese 8oz", 1, 4.49),
        ("Eggs Large Dozen", 1, 3.79),
        ("Orange Juice 64oz", 1, 4.29),
        ("Greek Yogurt 4pk", 2, 5.99),
    ]

    subtotal = 0
    for desc, qty, price in items:
        total_price = qty * price
        subtotal += total_price
        y = draw_line_item(desc, qty, total_price, y)

    y = draw_separator(y - 5)

    # Totals
    tax_rate = 0.0825
    tax_amount = subtotal * tax_rate
    total = subtotal + tax_amount

    y = draw_total_line("Subtotal:", subtotal, y)
    y = draw_total_line(f"Tax (8.25%):", tax_amount, y)
    y -= 3
    y = draw_total_line("TOTAL:", total, y, bold=True)

    y = draw_separator(y - 5)

    # Payment Info
    amount_tendered = 70.00
    change = amount_tendered - total

    y = draw_total_line("CASH:", amount_tendered, y)
    y = draw_total_line("Change:", change, y)

    y = draw_separator(y - 5)

    # Footer
    y -= 10
    y = draw_centered_text("Thank you for shopping", y, "Helvetica-Bold", 10)
    y = draw_centered_text("at SUPER MART!", y, "Helvetica-Bold", 10)
    y -= 10
    y = draw_centered_text("Visit us online at", y, "Helvetica", 8)
    y = draw_centered_text("www.supermart.example.com", y, "Helvetica", 8)
    y -= 10
    y = draw_centered_text("*** CUSTOMER COPY ***", y, "Helvetica", 8)

    c.save()
    print(f"Created receipt PDF: {filename}")

if __name__ == "__main__":
    create_receipt_pdf("sample_receipt.pdf")

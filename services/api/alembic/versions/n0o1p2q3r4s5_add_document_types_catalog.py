"""Add document_types catalog for missing-doc requests.

Revision ID: n0o1p2q3r4s5
Revises: m9n0o1p2q3r4
Create Date: 2026-11-19
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "n0o1p2q3r4s5"
down_revision: Union[str, None] = "m9n0o1p2q3r4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SEED_TYPES = [
    (
        "commercial_invoice",
        "Commercial Invoice",
        "pre_loading",
        10,
        "Please provide a signed Commercial Invoice showing seller/buyer, unit prices, "
        "extended totals, currency, Incoterms, HTS (if available), and Country of Origin "
        "for each line. Reply to this email with the PDF attached (or upload via the link).",
    ),
    (
        "packing_list",
        "Packing List",
        "pre_loading",
        20,
        "Please provide the Packing List with carton/pallet counts, weights (gross/net), "
        "dimensions, and marks & numbers matching the Commercial Invoice and BOL. "
        "Reply with the PDF attached.",
    ),
    (
        "bill_of_lading",
        "Bill of Lading (MBL / HBL)",
        "in_transit",
        30,
        "Please provide the Master and/or House Bill of Lading showing carrier, vessel/voyage "
        "(or flight), ports, consignee, and container numbers. Reply with a clear PDF/scan.",
    ),
    (
        "arrival_notice",
        "Arrival Notice",
        "arrival",
        40,
        "Please forward the carrier Arrival Notice with ETA, place of delivery, freight "
        "charges (if shown), and container/seal details. Reply with the notice attached.",
    ),
    (
        "power_of_attorney",
        "Power of Attorney (POA)",
        "setup",
        50,
        "Please complete and return a signed Customs Power of Attorney authorizing our "
        "brokerage to file entries on your behalf. Reply with the signed PDF.",
    ),
    (
        "pga_certificate",
        "PGA / FDA / Lacey Act Certificate",
        "clearance",
        60,
        "Please provide the required Partner Government Agency certificate(s) "
        "(FDA, USDA, Lacey Act, FCC, etc.) applicable to this shipment. Reply with PDFs attached.",
    ),
    (
        "certificate_of_origin",
        "Certificate of Origin",
        "clearance",
        70,
        "Please provide a Certificate of Origin (or FTA preferential COO if claiming preference) "
        "covering the goods on this shipment. Reply with the signed certificate PDF.",
    ),
    (
        "isf_worksheet",
        "ISF / 10+2 Data Worksheet",
        "pre_loading",
        80,
        "Please complete the ISF (10+2) data worksheet: seller, buyer, importer of record, "
        "consignee, manufacturer, ship-to, container stuffing location, consolidator, and "
        "HTS / country of origin. Reply with the completed form attached.",
    ),
    (
        "other",
        "Other / Specify in Instructions",
        "general",
        900,
        "Please provide the document described in the instructions below. "
        "Reply to this email with the file attached (or use the upload link).",
    ),
]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "document_types" not in set(inspector.get_table_names()):
        op.create_table(
            "document_types",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("code", sa.String(100), nullable=False),
            sa.Column("label", sa.String(200), nullable=False),
            sa.Column("category", sa.String(100), nullable=True),
            sa.Column("request_instructions", sa.Text(), nullable=True),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="100"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.UniqueConstraint("code", name="uq_document_types_code"),
        )
        op.create_index("ix_document_types_code", "document_types", ["code"])
        op.create_index("ix_document_types_sort_order", "document_types", ["sort_order"])

    for code, label, category, sort_order, instructions in SEED_TYPES:
        bind.execute(
            sa.text(
                """
                INSERT INTO document_types (code, label, category, request_instructions, sort_order, is_active)
                VALUES (:code, :label, :category, :instructions, :sort_order, true)
                ON CONFLICT (code) DO UPDATE SET
                    label = EXCLUDED.label,
                    category = EXCLUDED.category,
                    request_instructions = EXCLUDED.request_instructions,
                    sort_order = EXCLUDED.sort_order,
                    is_active = true,
                    updated_at = now()
                """
            ),
            {
                "code": code,
                "label": label,
                "category": category,
                "instructions": instructions,
                "sort_order": sort_order,
            },
        )


def downgrade() -> None:
    op.drop_index("ix_document_types_sort_order", table_name="document_types")
    op.drop_index("ix_document_types_code", table_name="document_types")
    op.drop_table("document_types")

"""Add shipment suggestion + client assembly preference tables.

Revision ID: m9n0o1p2q3r4
Revises: l8m9n0p1q2r3
Create Date: 2026-11-18

Unblocks post-ingest shipment assembly workers that previously crashed on
UndefinedTable for client_assembly_preferences / shipment_suggestions.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "m9n0o1p2q3r4"
down_revision: Union[str, None] = "l8m9n0p1q2r3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

suggestion_status = postgresql.ENUM(
    "pending",
    "accepted",
    "rejected",
    "merged",
    "expired",
    name="suggestionstatus",
    create_type=False,
)
assembly_mode = postgresql.ENUM(
    "auto",
    "manual",
    "assisted",
    name="assemblymode",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    suggestion_status.create(bind, checkfirst=True)
    assembly_mode.create(bind, checkfirst=True)

    if "shipment_suggestions" not in tables:
        op.create_table(
            "shipment_suggestions",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("master_bl", sa.String(50), nullable=True),
            sa.Column("house_bl", sa.String(50), nullable=True),
            sa.Column("container_numbers", postgresql.ARRAY(sa.String()), nullable=True),
            sa.Column("booking_number", sa.String(50), nullable=True),
            sa.Column("confidence_score", sa.Float(), nullable=True, server_default="0"),
            sa.Column("match_reasons", sa.JSON(), nullable=True),
            sa.Column("status", suggestion_status, nullable=False, server_default="pending"),
            sa.Column("document_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False),
            sa.Column("document_count", sa.String(), nullable=True, server_default="0"),
            sa.Column("suggested_details", sa.JSON(), nullable=True),
            sa.Column(
                "created_shipment_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("shipments.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("reviewed_by", sa.String(255), nullable=True),
            sa.Column("rejection_reason", sa.Text(), nullable=True),
            sa.Column("tenant_id", sa.String(100), nullable=True),
        )
        op.create_index("ix_shipment_suggestions_master_bl", "shipment_suggestions", ["master_bl"])
        op.create_index("ix_shipment_suggestions_house_bl", "shipment_suggestions", ["house_bl"])
        op.create_index("ix_shipment_suggestions_tenant_id", "shipment_suggestions", ["tenant_id"])

    if "shipment_suggestion_documents" not in tables:
        op.create_table(
            "shipment_suggestion_documents",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "suggestion_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("shipment_suggestions.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "document_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("document_metadata.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("document_type", sa.String(100), nullable=True),
            sa.Column("document_role", sa.String(50), nullable=True),
            sa.Column("extracted_identifiers", sa.JSON(), nullable=True),
            sa.Column("match_confidence", sa.Float(), nullable=True, server_default="1"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        )

    if "client_assembly_preferences" not in tables:
        op.create_table(
            "client_assembly_preferences",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("client_id", sa.String(100), nullable=False),
            sa.Column("assembly_mode", assembly_mode, nullable=False, server_default="manual"),
            sa.Column("auto_accept_threshold", sa.Float(), nullable=True, server_default="0.9"),
            sa.Column("notify_on_suggestion", sa.Boolean(), nullable=True, server_default=sa.text("true")),
            sa.Column("notify_on_auto_accept", sa.Boolean(), nullable=True, server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint("client_id", name="uq_client_assembly_preferences_client_id"),
        )
        op.create_index(
            "ix_client_assembly_preferences_client_id",
            "client_assembly_preferences",
            ["client_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "shipment_suggestion_documents" in tables:
        op.drop_table("shipment_suggestion_documents")
    if "shipment_suggestions" in tables:
        op.drop_index("ix_shipment_suggestions_tenant_id", table_name="shipment_suggestions")
        op.drop_index("ix_shipment_suggestions_house_bl", table_name="shipment_suggestions")
        op.drop_index("ix_shipment_suggestions_master_bl", table_name="shipment_suggestions")
        op.drop_table("shipment_suggestions")
    if "client_assembly_preferences" in tables:
        op.drop_index(
            "ix_client_assembly_preferences_client_id",
            table_name="client_assembly_preferences",
        )
        op.drop_table("client_assembly_preferences")

    suggestion_status.drop(bind, checkfirst=True)
    assembly_mode.drop(bind, checkfirst=True)

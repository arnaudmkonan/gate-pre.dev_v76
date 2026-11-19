"""Seed starter USITC HTS codes when tariff schedule is empty.

Revision ID: l8m9n0p1q2r3
Revises: k7l8m9n0p1q2
Create Date: 2026-11-18
"""
from decimal import Decimal
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "l8m9n0p1q2r3"
down_revision: Union[str, None] = "k7l8m9n0p1q2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "hts_codes" not in set(inspector.get_table_names()):
        return

    # Resync serial sequence if hts_codes uses an integer primary key with pre-seeded explicit IDs
    seq_name = bind.execute(sa.text("SELECT pg_get_serial_sequence('hts_codes', 'id')")).scalar()
    if seq_name:
        max_id = bind.execute(sa.text("SELECT MAX(id) FROM hts_codes")).scalar()
        if max_id is not None:
            bind.execute(sa.text("SELECT setval(:seq, :val, true)"), {"seq": seq_name, "val": int(max_id)})

    from app.startup.hts_seed import STARTER_USITC_HTS_CODES

    stmt = sa.text(
        """
        INSERT INTO hts_codes (hts_code, description, chapter, duty_rate, duty_rate_percent)
        VALUES (:hts_code, :description, :chapter, :duty_rate, :duty_rate_percent)
        ON CONFLICT (hts_code) DO NOTHING
        """
    )
    for code, desc, chapter, rate_str, rate_pct in STARTER_USITC_HTS_CODES:
        bind.execute(
            stmt,
            {
                "hts_code": code,
                "description": desc,
                "chapter": chapter,
                "duty_rate": rate_str,
                "duty_rate_percent": Decimal(rate_pct),
            },
        )


def downgrade() -> None:
    # Reference tariff rows are preserved on downgrade so entries referencing HTS codes remain valid.
    pass

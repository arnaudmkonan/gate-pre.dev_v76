"""Merge Alembic heads (extraction_metadata + api_keys chain).

Revision ID: h4i5j6k7l8m9
Revises: e1f2a3b4c5d6, 6ba76a0b6501
Create Date: 2026-03-27

"""
from typing import Sequence, Union

from alembic import op

revision: str = "h4i5j6k7l8m9"
down_revision: Union[str, Sequence[str], None] = ("e1f2a3b4c5d6", "6ba76a0b6501")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

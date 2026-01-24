"""
ACE Entry SQLAlchemy model for CBP import entry data.
"""
from sqlalchemy import Column, String, Text, Integer, Numeric, DateTime, Boolean, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.models.base import BaseModel


class ACEEntry(BaseModel):
    """
    ACE (Automated Commercial Environment) Entry record.
    Represents a single line item from a CBP entry.
    """
    __tablename__ = "ace_entries"

    # Entry identification
    entry_number = Column(String(50), nullable=False, index=True)
    entry_date = Column(DateTime(timezone=True), nullable=True)
    entry_type = Column(String(10), nullable=True)  # 01=Consumption, 03=AD/CVD, etc.

    # Importer information
    importer_name = Column(String(500), nullable=True, index=True)
    importer_number = Column(String(50), nullable=True)  # EIN/CBP assigned number

    # Port information
    port_code = Column(String(10), nullable=True)
    port_name = Column(String(200), nullable=True)

    # Line item details
    hts_code = Column(String(20), nullable=True, index=True)
    description = Column(Text, nullable=True)
    country_of_origin = Column(String(100), nullable=True, index=True)
    quantity = Column(Numeric(15, 4), nullable=True)
    unit = Column(String(20), nullable=True)

    # Value and duties
    entered_value = Column(Numeric(15, 2), nullable=True)
    duty_rate = Column(Numeric(10, 4), nullable=True)
    duty_amount = Column(Numeric(15, 2), nullable=True)
    mpf_amount = Column(Numeric(15, 2), nullable=True)  # Merchandise Processing Fee
    hmf_amount = Column(Numeric(15, 2), nullable=True)  # Harbor Maintenance Fee

    # Liquidation tracking
    liquidation_date = Column(DateTime(timezone=True), nullable=True)
    liquidation_status = Column(String(50), nullable=True)  # extended, final, pending

    # Additional data
    raw_data = Column(JSONB, nullable=True)  # Original row data
    batch_id = Column(String(50), nullable=True, index=True)  # Import batch identifier

    __table_args__ = (
        Index('ix_ace_entries_entry_number_hts', 'entry_number', 'hts_code'),
        Index('ix_ace_entries_entry_date', 'entry_date'),
    )

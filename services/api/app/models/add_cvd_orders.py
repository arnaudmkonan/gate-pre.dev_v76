"""
ADD/CVD Orders Model.

Reference table for antidumping and countervailing duty orders.

Task 2.3 from ROADMAP_FULL_WORKFLOW.md
"""
from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    Column, String, Numeric, Text, Boolean, DateTime, Index,
)
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base



class AddCvdOrder(Base):
    """
    Antidumping (ADD) and Countervailing (CVD) Duty Orders.
    
    This table stores active ADD/CVD orders from the ITA/CBP.
    Orders are looked up by HTS code + country of origin combination.
    """
    __tablename__ = "add_cvd_orders"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Case identification
    case_number = Column(String(50), nullable=False, index=True)
    case_type = Column(String(10), nullable=False)  # ADD, CVD, or ADD/CVD
    
    # Product scope
    hts_chapter = Column(String(2), nullable=False, index=True)  # 2-digit chapter
    hts_heading = Column(String(4), nullable=True)  # 4-digit heading
    hts_subheading = Column(String(6), nullable=True)  # 6-digit subheading
    hts_full = Column(String(14), nullable=True)  # Full HTS if specific
    
    # Country
    country_code = Column(String(2), nullable=False, index=True)  # ISO 2-letter
    country_name = Column(String(100), nullable=True)
    
    # Product description
    product_description = Column(Text, nullable=True)
    scope_description = Column(Text, nullable=True)
    
    # Rates
    add_rate = Column(Numeric(10, 4), nullable=True)  # ADD rate as decimal
    cvd_rate = Column(Numeric(10, 4), nullable=True)  # CVD rate as decimal
    combined_rate = Column(Numeric(10, 4), nullable=True)  # Total if both apply
    
    # Rate type
    is_all_others_rate = Column(Boolean, default=True)  # All-others rate vs. company-specific
    company_name = Column(String(255), nullable=True)  # If company-specific rate
    
    # Status
    is_active = Column(Boolean, default=True, index=True)
    effective_date = Column(DateTime, nullable=True)
    expiration_date = Column(DateTime, nullable=True)
    last_review_date = Column(DateTime, nullable=True)
    
    # Federal Register reference
    federal_register_citation = Column(String(100), nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    notes = Column(Text, nullable=True)
    
    # Indexes for fast lookup
    __table_args__ = (
        Index('ix_add_cvd_hts_country', 'hts_chapter', 'country_code', 'is_active'),
        Index('ix_add_cvd_case', 'case_number', 'case_type'),
    )
    
    def __repr__(self):
        return f"<AddCvdOrder {self.case_number}: {self.case_type} {self.country_code}>"


# Sample seed data for common ADD/CVD orders
SAMPLE_ADD_CVD_ORDERS = [
    # Steel - China
    {
        "case_number": "A-570-xxx",
        "case_type": "ADD",
        "hts_chapter": "72",
        "hts_heading": "7208",
        "country_code": "CN",
        "country_name": "China",
        "product_description": "Hot-Rolled Steel Flat Products",
        "add_rate": 0.6792,  # 67.92%
        "is_active": True,
    },
    {
        "case_number": "C-570-xxx",
        "case_type": "CVD",
        "hts_chapter": "72",
        "hts_heading": "7208",
        "country_code": "CN",
        "country_name": "China",
        "product_description": "Hot-Rolled Steel Flat Products",
        "cvd_rate": 0.1581,  # 15.81%
        "is_active": True,
    },
    # Steel - Vietnam
    {
        "case_number": "A-552-xxx",
        "case_type": "ADD",
        "hts_chapter": "72",
        "hts_heading": "7210",
        "country_code": "VN",
        "country_name": "Vietnam",
        "product_description": "Corrosion-Resistant Steel Products",
        "add_rate": 1.9957,  # 199.57%
        "is_active": True,
    },
    # Aluminum Extrusions - China
    {
        "case_number": "A-570-967",
        "case_type": "ADD",
        "hts_chapter": "76",
        "country_code": "CN",
        "country_name": "China",
        "product_description": "Aluminum Extrusions",
        "add_rate": 0.3767,  # 37.67%
        "is_active": True,
    },
    {
        "case_number": "C-570-968",
        "case_type": "CVD",
        "hts_chapter": "76",
        "country_code": "CN",
        "country_name": "China",
        "product_description": "Aluminum Extrusions",
        "cvd_rate": 0.1895,  # 18.95%
        "is_active": True,
    },
    # Solar Cells - China
    {
        "case_number": "A-570-979",
        "case_type": "ADD",
        "hts_chapter": "85",
        "hts_heading": "8541",
        "country_code": "CN",
        "country_name": "China",
        "product_description": "Crystalline Silicon Photovoltaic Cells",
        "add_rate": 0.2503,  # 25.03%
        "is_active": True,
    },
    # Wooden Bedroom Furniture - China
    {
        "case_number": "A-570-890",
        "case_type": "ADD",
        "hts_chapter": "94",
        "hts_heading": "9403",
        "country_code": "CN",
        "country_name": "China",
        "product_description": "Wooden Bedroom Furniture",
        "add_rate": 2.1618,  # 216.18%
        "is_active": True,
    },
    # Magnesium - China
    {
        "case_number": "A-570-896",
        "case_type": "ADD",
        "hts_chapter": "81",
        "hts_heading": "8104",
        "country_code": "CN",
        "country_name": "China",
        "product_description": "Pure Magnesium",
        "add_rate": 1.4183,  # 141.83%
        "is_active": True,
    },
    # Tires - Korea
    {
        "case_number": "A-580-xxx",
        "case_type": "ADD",
        "hts_chapter": "40",
        "hts_heading": "4011",
        "country_code": "KR",
        "country_name": "Korea",
        "product_description": "Passenger Vehicle and Light Truck Tires",
        "add_rate": 0.0805,  # 8.05%
        "is_active": True,
    },
]

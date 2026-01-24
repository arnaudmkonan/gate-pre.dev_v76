"""
DocumentKey model for extracted linking identifiers from documents.

Key types (priority order for linking):
1. ENTRY_NUM - CBP Entry Number (strongest, unique per filing)
2. BOL_NUM - Bill of Lading Number (ocean shipments)
3. CONTAINER_NUM - Container Number (ocean FCL shipments)
4. AWB_NUM - Air Waybill Number (air shipments)
5. PO_NUM - Purchase Order Number (commercial)
6. INVOICE_NUM - Invoice Number (commercial)
7. HTS_CODE - Harmonized Tariff Code
8. IMPORTER_NAME - Importer of Record name
9. VENDOR_NAME - Seller/Exporter name
10. MANUFACTURER_NAME - Manufacturer name
"""
from enum import Enum
from sqlalchemy import Column, Index, String, Text, Float, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class KeyType(str, Enum):
    """Types of linking keys extracted from documents."""
    # Regulatory (Strongest)
    ENTRY_NUM = "ENTRY_NUM"
    ACE_BILL = "ACE_BILL"
    
    # Logistics
    BOL_NUM = "BOL_NUM"
    AWB_NUM = "AWB_NUM"
    CONTAINER_NUM = "CONTAINER_NUM"
    
    # Commercial
    INVOICE_NUM = "INVOICE_NUM"
    PO_NUM = "PO_NUM"
    
    # Entity
    IMPORTER_NAME = "IMPORTER_NAME"
    VENDOR_NAME = "VENDOR_NAME"
    MANUFACTURER_NAME = "MANUFACTURER_NAME"
    
    # Additional
    HTS_CODE = "HTS_CODE"
    COUNTRY_ORIGIN = "COUNTRY_ORIGIN"


class ExtractionMethod(str, Enum):
    """How the key was extracted."""
    REGEX = "regex"
    LLM = "llm"
    MANUAL = "manual"
    OCR = "ocr"
    STRUCTURED = "structured"


# Priority order for key types (lower = stronger/higher priority)
KEY_PRIORITY = {
    KeyType.ENTRY_NUM: 1,
    KeyType.ACE_BILL: 2,
    KeyType.BOL_NUM: 3,
    KeyType.AWB_NUM: 4,
    KeyType.CONTAINER_NUM: 5,
    KeyType.INVOICE_NUM: 6,
    KeyType.PO_NUM: 7,
    KeyType.IMPORTER_NAME: 8,
    KeyType.VENDOR_NAME: 9,
    KeyType.MANUFACTURER_NAME: 10,
    KeyType.HTS_CODE: 11,
    KeyType.COUNTRY_ORIGIN: 12,
}


class DocumentKey(BaseModel):
    """
    Extracted linking key from a document.
    
    Used to automatically group documents into shipments by finding
    documents that share the same key values (e.g., same Entry Number,
    same BOL Number, etc.)
    """
    __tablename__ = "document_keys"

    # Link to the source document (raw_files table)
    document_id = Column(UUID(as_uuid=True), ForeignKey("raw_files.id", ondelete="CASCADE"), nullable=False)
    
    # Key identification
    key_type = Column(String(50), nullable=False)  # KeyType enum value
    key_value = Column(String(500), nullable=False)  # Original extracted value
    key_value_normalized = Column(String(500), nullable=True)  # Normalized for matching (uppercase, no separators)
    
    # Extraction metadata
    confidence = Column(Float, default=1.0, nullable=False)  # 0.0-1.0 confidence score
    extraction_method = Column(String(20), default=ExtractionMethod.REGEX, nullable=False)
    source_text = Column(Text, nullable=True)  # Context snippet where key was found
    
    __table_args__ = (
        # Primary lookup indexes
        Index("ix_document_keys_document_id", "document_id"),
        Index("ix_document_keys_key_type", "key_type"),
        Index("ix_document_keys_key_value", "key_value"),
        Index("ix_document_keys_normalized", "key_value_normalized"),
        
        # Compound indexes for linking queries
        Index("ix_document_keys_type_value", "key_type", "key_value"),
        Index("ix_document_keys_type_normalized", "key_type", "key_value_normalized"),
    )
    
    def __repr__(self):
        return f"<DocumentKey {self.key_type}={self.key_value}>"

"""
Pydantic schemas for Entry API endpoints.

Extracted from entries.py routes for reusability.
"""
from typing import Optional, List
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.entry import EntryType


# ==================== Entry CRUD Schemas ====================

class EntryLineCreate(BaseModel):
    """Create/update entry line."""
    line_number: int = Field(ge=1)
    hts_code: Optional[str] = None
    product_description: Optional[str] = None
    country_of_origin: Optional[str] = None
    manufacturer_name: Optional[str] = None
    quantity_1: Optional[float] = None
    uom_1: Optional[str] = None
    entered_value: Optional[float] = None
    duty_rate: Optional[float] = None
    fta_code: Optional[str] = None


class EntryPartyCreate(BaseModel):
    """Create entry party."""
    role: str
    name: str
    address_line_1: Optional[str] = None
    city: Optional[str] = None
    state_province: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    cbp_number: Optional[str] = None


class EntryLineCreateInline(BaseModel):
    """Line item to create with entry (for wizard)."""
    line_number: int = Field(ge=1)
    hts_code: Optional[str] = None
    hts_description: Optional[str] = None
    product_description: Optional[str] = None
    country_of_origin: Optional[str] = None
    quantity: Optional[float] = None
    unit_of_measure: Optional[str] = None
    unit_value: Optional[float] = None
    entered_value: Optional[float] = None
    gross_weight: Optional[float] = None
    net_weight: Optional[float] = None


class EntryCreate(BaseModel):
    """Create new entry."""
    entry_type: str = EntryType.CONSUMPTION.value
    port_of_entry: Optional[str] = None
    entry_date: Optional[datetime] = None
    importer_of_record_number: Optional[str] = None
    importer_of_record_name: Optional[str] = None
    bill_of_lading: Optional[str] = None
    mode_of_transport: Optional[str] = None
    client_id: Optional[str] = None
    internal_reference: Optional[str] = None
    notes: Optional[str] = None
    # For wizard — include line items with entry creation
    line_items: Optional[List[EntryLineCreateInline]] = None


class EntryUpdate(BaseModel):
    """Update entry fields."""
    entry_type: Optional[str] = None
    port_of_entry: Optional[str] = None
    port_of_unlading: Optional[str] = None
    entry_date: Optional[datetime] = None
    import_date: Optional[datetime] = None
    importer_of_record_number: Optional[str] = None
    importer_of_record_name: Optional[str] = None
    ultimate_consignee_name: Optional[str] = None
    bill_of_lading: Optional[str] = None
    master_bill: Optional[str] = None
    house_bill: Optional[str] = None
    vessel_name: Optional[str] = None
    carrier_code: Optional[str] = None
    mode_of_transport: Optional[str] = None
    bond_type: Optional[str] = None
    bond_number: Optional[str] = None
    status: Optional[str] = None
    assigned_to: Optional[str] = None
    internal_reference: Optional[str] = None
    notes: Optional[str] = None


# ==================== Response Schemas ====================

class EntryValidationResponse(BaseModel):
    """Entry validation result."""
    valid: bool
    filing_ready: bool = False
    errors: List[dict] = []
    warnings: List[dict] = []
    info: List[dict] = []
    error_count: int = 0
    warning_count: int = 0
    summary: str = ""


class EntryListResponse(BaseModel):
    """Paginated entry list."""
    count: int
    total: int
    offset: int
    limit: int
    entries: List[dict]


# ==================== Document Linking Schemas ====================

class EntryFromDocumentsRequest(BaseModel):
    """Create entry from extracted documents."""
    document_ids: List[str]
    client_id: Optional[str] = None


class LinkDocumentsRequest(BaseModel):
    """Link documents to entry request."""
    document_ids: List[str]
    auto_populate: bool = True  # Automatically populate entry fields from extraction data


class ExtractionSuggestion(BaseModel):
    """Field suggestion from extraction."""
    field_name: str
    current_value: Optional[str] = None
    suggested_value: str
    confidence: float
    source_document_id: str
    source_document_type: Optional[str] = None


# ==================== ABI / ACE Schemas ====================

class BulkABIExportRequest(BaseModel):
    """Request for bulk ABI export."""
    entry_ids: List[str]
    message_type: str = "SE"


class SimulateACEResponseRequest(BaseModel):
    """Request to simulate an ACE response."""
    ace_status: str
    message: str = "Simulated ACE response"
    error_codes: Optional[List[str]] = None


# ==================== Amendment Schemas ====================

class AmendmentChangeRequest(BaseModel):
    """Single field change in an amendment."""
    field_name: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    change_type: str = "other"
    line_number: Optional[int] = None


class CreateAmendmentRequest(BaseModel):
    """Request to create an amendment."""
    changes: List[AmendmentChangeRequest]
    reason: str = "clerical_error"
    is_prior_disclosure: bool = False
    notes: Optional[str] = None


class PreviewAmendmentRequest(BaseModel):
    """Request to preview an amendment."""
    total_entered_value: Optional[float] = None
    importer_of_record_number: Optional[str] = None
    importer_of_record_name: Optional[str] = None
    lines: Optional[List[dict]] = None

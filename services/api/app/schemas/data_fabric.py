from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel

# --- Silver Layer Schemas ---

class AddressResponse(BaseModel):
    id: UUID
    street: Optional[str]
    city: Optional[str]
    state: Optional[str]
    postal_code: Optional[str]
    country: Optional[str]
    normalized_address: Optional[str]
    
    class Config:
        from_attributes = True

class PartyResponse(BaseModel):
    id: UUID
    canonical_name: str
    party_type: Optional[str] = None
    tax_id: Optional[str] = None
    aliases: List[str] = []
    contact_info: Optional[Dict[str, Any]] = None
    golden_record_id: Optional[UUID] = None
    
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class ProductResponse(BaseModel):
    id: UUID
    description: str
    hs_code: Optional[str]
    country_of_origin: Optional[str]
    unit_of_measure: Optional[str]
    aliases: List[str] = []
    golden_record_id: Optional[UUID]
    
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# --- Gold Layer Schemas ---

class InvoiceLineResponse(BaseModel):
    id: UUID
    line_num: Optional[int]
    description: Optional[str]
    quantity: Optional[float]
    unit_price: Optional[float]
    amount: Optional[float]
    hs_code: Optional[str]
    product: Optional[ProductResponse]
    
    class Config:
        from_attributes = True

class CommercialInvoiceResponse(BaseModel):
    id: UUID
    invoice_num: str
    invoice_date: Optional[datetime]
    currency: Optional[str]
    total_amount: Optional[float]
    
    vendor: Optional[PartyResponse]
    buyer: Optional[PartyResponse]
    lines: List[InvoiceLineResponse] = []
    
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ShipmentResponse(BaseModel):
    id: UUID
    reference_num: Optional[str]
    origin: Optional[str]
    destination: Optional[str]
    ship_date: Optional[datetime]
    status: Optional[str]
    
    shipper: Optional[PartyResponse]
    consignee: Optional[PartyResponse]
    
    invoices: List[CommercialInvoiceResponse] = []
    
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# --- List Responses ---

class PartyListResponse(BaseModel):
    items: List[PartyResponse]
    total: int
    page: int
    page_size: int

class ProductListResponse(BaseModel):
    items: List[ProductResponse]
    total: int
    page: int
    page_size: int

class ShipmentListResponse(BaseModel):
    items: List[ShipmentResponse]
    total: int
    page: int
    page_size: int

class InvoiceListResponse(BaseModel):
    items: List[CommercialInvoiceResponse]
    total: int
    page: int
    page_size: int

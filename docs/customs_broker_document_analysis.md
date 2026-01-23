# Customs Brokerage Document Analysis

## Purpose
Deep-dive into the documents and data a customs broker handles daily to identify:
1. All document types and their sources
2. Key data fields that link documents together
3. Ingestion strategies for each document type
4. Anchor points for creating unified shipment records

---

## 📋 Part 1: Document Universe

### 1.1 Import Transaction Documents

| Document | Source | Format | Frequency | Key Data |
|:---|:---|:---|:---|:---|
| **Commercial Invoice** | Seller/Exporter | PDF, Excel, EDI | Every shipment | Invoice #, Value, Seller, Buyer, Products, Terms |
| **Packing List** | Seller/Exporter | PDF, Excel | Every shipment | Carton counts, Weights, Dimensions, SKUs |
| **Bill of Lading (B/L)** | Carrier (Ocean) | PDF, EDI 310 | Per ocean shipment | B/L #, Vessel, Voyage, Port, Shipper, Consignee |
| **Air Waybill (AWB)** | Carrier (Air) | PDF, EDI | Per air shipment | AWB #, Flight, Origin, Destination, HAWB/MAWB |
| **ISF Filing (10+2)** | Broker-generated | ACE submission | 24hr before loading | Seller, Buyer, Manufacturer, Ship-to, HTS, Container |
| **Arrival Notice** | Carrier/Forwarder | PDF, Email | 24-48hr pre-arrival | ETA, Vessel, Port, Freight charges, Demurrage |
| **Delivery Order (D/O)** | Terminal/Forwarder | PDF | At cargo release | Container #, Release location, Delivery instructions |

### 1.2 Customs Filing Documents

| Document | Source | Format | When | Key Data |
|:---|:---|:---|:---|:---|
| **CBP Form 7501** | Broker-generated | ACE/ABI submission | At entry | Entry #, Entry Type, HTS codes, Duty, Fees |
| **CBP Form 3461** | Broker-generated | ACE submission | Immediate delivery | Entry #, Port, Consignee, Carrier |
| **Power of Attorney** | Importer | PDF (signed) | One-time | Entity info, Authority scope, Expiration |
| **Customs Bond** | Surety company | PDF | Annual or single | Bond #, Amount, Coverage dates |
| **Classification Ruling** | CBP | PDF, HTML | As needed | Ruling #, HTS determination, Product description |

### 1.3 Regulatory/Agency Documents

| Document | Agency | Format | When | Key Data |
|:---|:---|:---|:---|:---|
| **FDA Prior Notice** | FDA | PNSI submission | 15 days before | Product, Manufacturer, FCE/SID |
| **USDA/APHIS Permit** | USDA | PDF, APHIS system | Before import | Permit #, Species, Origin, Facility |
| **FCC Declaration** | FCC | 740 form | With entry | Device type, FCC ID, Compliance |
| **EPA Form 3520** | EPA | Paper/electronic | With entry | Chemical, ODS, Vehicle compliance |
| **CPSC Certificate** | Manufacturer | PDF | With shipment | Testing lab, Standard, Certification |
| **Lacey Act Declaration** | Importer | PDF | Wood/plant products | Species, Origin, Harvest info |

### 1.4 Post-Entry Documents

| Document | Source | Format | When | Key Data |
|:---|:---|:---|:---|:---|
| **Liquidation Notice** | CBP | EDI, ACE | 314 days post-entry | Final duty, Adjustments |
| **Request for Information** | CBP | Letter, Email | Audit | Questions, Deadline |
| **Prior Disclosure** | Broker-initiated | Paper | Voluntary | Errors, Duty owed |
| **Protest (CBP 19)** | Broker-filed | Paper | Dispute ruling | Entry #, Issue, Legal basis |
| **Drawback Claim** | Broker-filed | ACE | Export of imported goods | Entry #, Export ref, Refund amount |

---

## 🔗 Part 2: Document Relationships & Anchor Points

### 2.1 The Anchor Dilemma

The challenge: A single shipment generates 10-20 documents, but there's **no single universal ID** across all of them.

| ID Type | Present In | Coverage |
|:---|:---|:---|
| **B/L Number** | B/L, ISF, Arrival Notice, D/O | Ocean only, not air |
| **AWB Number** | AWB, Air Manifest | Air only |
| **Entry Number** | 7501, 3461, Liquidation, Protests | CBP docs only |
| **Invoice Number** | Commercial Invoice, 7501 | Seller-generated, not unique |
| **Container Number** | B/L, Arrival Notice, D/O | Ocean FCL only |
| **PO Number** | Invoice, Packing List | Buyer-generated, optional |

### 2.2 Proposed Anchor Strategy

**Primary Anchor: Internal Shipment ID (`shipment_ref`)**

We create our own canonical shipment record and link all documents to it via secondary identifiers.

```
┌─────────────────────────────────────────────────────────────────┐
│                    SHIPMENT (Internal Anchor)                    │
│  shipment_ref: "SHP-2026-00123"                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Transport IDs:         Filing IDs:           Commercial IDs:   │
│  ├─ B/L: MAEU123456    ├─ Entry: 123-4567890  ├─ Invoice: INV-X │
│  ├─ Container: MSKU123 ├─ ISF: 2026-ISF-001   ├─ PO: PO-12345   │
│  └─ Vessel/Voyage      └─ Bond: 123456        └─ HBL: ABCD123   │
│                                                                  │
│  Documents:                                                      │
│  ├─ commercial_invoice.pdf    (extracted → InvoiceLines)        │
│  ├─ packing_list.pdf          (extracted → PackingDetails)      │
│  ├─ bill_of_lading.pdf        (extracted → TransportInfo)       │
│  ├─ arrival_notice.pdf        (extracted → ArrivalInfo)         │
│  └─ cbp_7501.pdf              (extracted → EntryData)           │
│                                                                  │
│  Linked Entities:                                                │
│  ├─ Importer: Acme Corp (Party)                                 │
│  ├─ Exporter: Shanghai Mfg (Party)                              │
│  ├─ Carrier: MAERSK (Party)                                     │
│  └─ Products: [Steel Bearings, PCBs] (Product[])                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.3 Linking Logic

When a new document arrives, we attempt to match it to an existing shipment using:

| Priority | Identifier | Match Confidence |
|:---|:---|:---|
| 1 | B/L Number (exact) | 100% |
| 2 | Container Number | 95% |
| 3 | Entry Number | 100% |
| 4 | Invoice # + Importer | 90% |
| 5 | PO # + Importer | 85% |
| 6 | Vessel/Voyage + Consignee | 80% |
| 7 | Date + Value + Parties (fuzzy) | 70% |

If no match: Create new shipment, present to user for confirmation.

---

## 📥 Part 3: Ingestion Strategy by Document Type

### 3.1 Path Assignment

| Document Type | Path | Extraction Method | Notes |
|:---|:---|:---|:---|
| Commercial Invoice (PDF) | A | Docling + LLM | Table extraction critical |
| Commercial Invoice (Excel) | B | Schema Mapping | Direct column mapping |
| Packing List (PDF) | A | Docling + LLM | Nested tables, carton details |
| Packing List (Excel) | B | Schema Mapping | Usually structured |
| Bill of Lading (PDF) | A | Layout Analysis | Fixed form, key positions |
| Bill of Lading (EDI 310) | B | EDI Parser | Segment parsing |
| ISF Acknowledgment | B | XML/JSON Parser | ACE response format |
| Arrival Notice (PDF) | A | LLM Extraction | Varies by carrier |
| CBP 7501 (filled) | A | Form Field Extraction | OCR + field mapping |
| FDA Prior Notice | C (API) | PNSI Integration | Pull from FDA system |

### 3.2 Key Extraction Fields by Document

#### Commercial Invoice
```yaml
header:
  - invoice_number
  - invoice_date
  - currency
  - incoterms
  - payment_terms
parties:
  - seller_name, seller_address
  - buyer_name, buyer_address
  - ship_to_name, ship_to_address
lines:
  - description
  - quantity
  - unit_price
  - total_price
  - hs_code (if present)
  - country_of_origin
totals:
  - gross_total
  - discounts
  - net_total
  - freight (CIF)
  - insurance (CIF)
```

#### Bill of Lading
```yaml
transport:
  - bl_number
  - booking_number
  - vessel_name
  - voyage_number
  - port_of_loading
  - port_of_discharge
  - place_of_delivery
parties:
  - shipper_name, shipper_address
  - consignee_name, consignee_address
  - notify_party
cargo:
  - container_number
  - seal_number
  - container_type
  - commodity_description
  - gross_weight
  - measurement
dates:
  - bl_date
  - on_board_date
  - eta
```

#### Packing List
```yaml
summary:
  - total_cartons
  - total_gross_weight
  - total_net_weight
  - total_volume
cartons:
  - carton_number
  - product_description
  - quantity_per_carton
  - net_weight
  - gross_weight
  - dimensions (L x W x H)
```

---

## 🏗️ Part 4: Enhanced Data Model

### 4.1 Current State (What We Have)

```
Bronze Layer: Raw files, metadata, extraction results
Silver Layer: Party, Product, Address, EntityLink
Gold Layer: Shipment, CommercialInvoice, InvoiceLine, CustomsEntry
```

### 4.2 Proposed Additions

```python
# New Gold Layer models for comprehensive shipment tracking

class ShipmentIdentifier(BaseModel):
    """Links multiple external IDs to a single shipment."""
    shipment_id: UUID
    identifier_type: str  # 'bl_number', 'awb_number', 'entry_number', 'container', etc.
    identifier_value: str
    source_document_id: UUID  # Which document provided this ID
    confidence: float

class TransportLeg(BaseModel):
    """Ocean/Air/Truck leg of a shipment."""
    shipment_id: UUID
    mode: str  # 'ocean', 'air', 'truck', 'rail'
    carrier_id: UUID  # Party
    vessel_voyage: str
    origin_port: str
    destination_port: str
    etd: datetime
    eta: datetime
    actual_arrival: datetime

class Container(BaseModel):
    """Container details for ocean shipments."""
    shipment_id: UUID
    container_number: str
    container_type: str  # '40HC', '20GP', etc.
    seal_number: str
    gross_weight_kg: float
    volume_cbm: float

class PackingCarton(BaseModel):
    """Individual carton from packing list."""
    shipment_id: UUID
    carton_number: str
    product_id: UUID
    quantity: float
    net_weight_kg: float
    gross_weight_kg: float
    dimensions_cm: dict  # {l, w, h}

class CustomsLine(BaseModel):
    """Line item from CBP 7501."""
    entry_id: UUID
    line_number: int
    hts_code: str
    description: str
    country_of_origin: str
    entered_value: Decimal
    duty_rate: Decimal
    calculated_duty: Decimal
    mpf: Decimal
    hmf: Decimal
    add_cvd: Decimal  # Anti-dumping/Countervailing

class ISFFiling(BaseModel):
    """Importer Security Filing (10+2) data."""
    shipment_id: UUID
    isf_number: str
    filing_date: datetime
    seller_id: UUID
    buyer_id: UUID
    manufacturer_id: UUID
    ship_to_id: UUID
    container_stuffing_location: str
    consolidator_id: UUID
    hts_codes: list[str]
    status: str  # 'filed', 'accepted', 'rejected'
```

---

## 📐 Part 5: Implementation Plan

### Phase 1: Foundation (This Sprint)
1. **Enhance Shipment model** with identifier linking table
2. **Add ShipmentIdentifier** model for multi-ID matching
3. **Implement document-to-shipment linking** service
4. **Create unified Shipment Dashboard** showing all linked documents

### Phase 2: Core Document Ingestion (1-2 weeks)
1. **Bill of Lading template** - Extract B/L#, vessel, cargo, parties
2. **Enhanced Packing List** - Extract carton-level details
3. **Linking service** - Auto-match documents to shipments

### Phase 3: Customs Filing Support (2-3 weeks)
1. **CBP 7501 model** - Line items, duties, fees
2. **ISF Filing model** - Track 10+2 submissions
3. **Entry-Invoice reconciliation** - Compare values before filing

### Phase 4: Agency Documents (3-4 weeks)
1. **FDA Prior Notice** integration
2. **USDA permit** tracking
3. **Compliance flag engine** - Auto-detect regulatory requirements

---

## ❓ Questions Before Proceeding

1. **Shipment Creation Trigger**: Should we auto-create shipments from B/L, or require user initiation?

2. **Multi-Invoice Shipments**: How do we handle consolidated shipments with 10+ invoices?

3. **Entry Number Format**: Do we need to support both old (10-digit) and new (15-digit) entry numbers?

4. **EDI Ingestion**: Is EDI (850, 310, 315) ingestion a priority, or PDF-first?

5. **ACE Integration**: Should we plan for direct ACE submission, or focus on data prep only?

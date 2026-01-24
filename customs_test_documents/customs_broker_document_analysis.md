# 📦 Customs Broker Document Ecosystem Analysis

## 🎯 PRIMARY ANCHOR POINTS (The "Keys" to Link Everything)

### 1. **Bill of Lading Number (BL/BOL)** - STRONGEST ANCHOR
- **Master Bill of Lading (MBL)**: Carrier-issued (e.g., `MAEU123456789`)
- **House Bill of Lading (HBL)**: Forwarder-issued (e.g., `FWDR-HBL-2024-001`)
- Present in: ISF Filing, Arrival Notice, Commercial Invoice, Packing List, Entry documents
- **Why it's the best anchor**: Unique per shipment, appears in nearly every document

### 2. **Container Number** - Physical Identifier
- Format: `ABCD1234567` (4 letters + 7 digits)
- Example: `MSCU1234567`, `TCLU9876543`
- Present in: MBL, HBL, Arrival Notice, ISF, sometimes on invoices

### 3. **Entry Number** - CBP Official Identifier
- Format: `XXX-NNNNNNN-C` (11 characters)
  - XXX = Entry Filer Code (broker's CBP-assigned code)
  - NNNNNNN = Transaction number (7 digits)
  - C = Check digit
- Example: `ABC-1234567-8`
- Present in: CBP Form 7501, Entry Summary, customs communications
- **Note**: Only exists AFTER initial filing

### 4. **Purchase Order (PO) Number** - Business Reference
- Format: Varies by company (e.g., `PO-2024-1001`, `INV-20240115-001`)
- Present in: Commercial Invoice, Packing List, sometimes on BL
- Links documents from buyer/seller perspective

### 5. **Shipper/Consignee Combination** - Party Identifier
- Company names + addresses
- Present in: ALL documents
- Helps validate document relationships

---

## 📋 DOCUMENT TYPES & HIERARCHY

### **Pre-Arrival Documents** (Before cargo reaches US port)

#### 1. **ISF (Importer Security Filing) - 10+2 Filing**
- **When**: Filed 24hrs before vessel departs origin port
- **Purpose**: Security screening by CBP
- **Key Fields**:
  - Master Bill of Lading Number
  - Container Number(s)
  - Shipper name/address
  - Consignee name/address
  - Manufacturer name/address
  - HTS Code (6-digit minimum)
  - Country of Origin
  - Commodity description
- **Formats**: Usually Excel spreadsheet or PDF form
- **Anchor Links**: MBL, Container#, Consignee

#### 2. **Commercial Invoice**
- **Source**: Seller/exporter
- **Purpose**: Financial record of transaction
- **Key Fields**:
  - Invoice Number & Date
  - Bill of Lading Number (reference)
  - PO Number
  - Seller/Buyer details
  - Line items with:
    - Product description
    - Quantity
    - Unit price
    - Total value
    - Country of Origin
    - Sometimes HTS codes
- **Formats**: PDF, Excel, Word, sometimes scanned images
- **Anchor Links**: BL#, PO#, Invoice#

#### 3. **Packing List**
- **Source**: Exporter/freight forwarder
- **Purpose**: Physical inventory breakdown
- **Key Fields**:
  - Bill of Lading Number
  - PO Number
  - Container Number(s)
  - Package details:
    - Carton numbers
    - Dimensions (L×W×H)
    - Weight (Gross/Net)
    - Piece count
  - Product descriptions
- **Formats**: PDF, Excel
- **Anchor Links**: BL#, Container#, PO#

#### 4. **Bill of Lading (BL/BOL)**
- **Master BL (MBL)**:
  - Issued by: Ocean carrier
  - Covers: Entire container shipment
  - Format: PDF, sometimes EDI messages
- **House BL (HBL)**:
  - Issued by: Freight forwarder
  - Covers: Individual shipper's cargo within container
  - Format: PDF
- **Key Fields**:
  - BL Number
  - Shipper/Consignee
  - Notify Party
  - Vessel name & voyage
  - Port of Loading/Discharge
  - Container numbers & seal numbers
  - Package count & description
  - Freight terms (Prepaid/Collect)
- **Anchor Links**: MBL#, HBL#, Container#, Vessel

---

### **Arrival Documents** (When cargo reaches US)

#### 5. **Arrival Notice**
- **Source**: Ocean carrier or freight forwarder
- **Purpose**: Notify consignee of cargo arrival
- **Key Fields**:
  - Bill of Lading Number
  - Container Number
  - Vessel name & voyage
  - Arrival date
  - Last Free Day (demurrage starts after)
  - Available for pickup location
  - Freight charges (if collect)
- **Formats**: PDF, email (often forwarded by freight forwarder)
- **Anchor Links**: MBL/HBL#, Container#, Vessel

#### 6. **Delivery Order (D/O)**
- **Source**: Carrier or terminal
- **Purpose**: Authorization to release cargo
- **Key Fields**:
  - BL Number
  - Container Number
  - Release authorization number
  - Pickup terminal location
- **Formats**: PDF, sometimes electronic portal
- **Anchor Links**: BL#, Container#

---

### **Customs Entry Documents** (Filing with CBP)

#### 7. **CBP Form 3461 - Entry/Immediate Delivery**
- **When**: At time of arrival (before full entry)
- **Purpose**: Request immediate release of cargo
- **Key Fields**:
  - Entry Number (assigned by broker)
  - Bill of Lading Number
  - Importer of Record details
  - Bond number
  - Estimated duties
- **Formats**: Electronic via ACE (Automated Commercial Environment)
- **Anchor Links**: Entry#, BL#, Importer

#### 8. **CBP Form 7501 - Entry Summary**
- **When**: Within 10 business days of cargo release
- **Purpose**: Official customs declaration & duty payment
- **Key Fields**:
  - **Header Section**:
    - Entry Number (XXX-NNNNNNN-C)
    - Entry Type (01=Consumption, 11=Informal, etc.)
    - Port of Entry (4-digit code)
    - Importer Number (EIN or SSN)
    - Consignee details
    - Manufacturer/Shipper ID
    - Bill of Lading Number
    - Country of Origin
    - Export Date
  - **Line Items** (per commodity):
    - Line number
    - HTS Code (10-digit)
    - Country of Origin
    - Quantity & Unit of Measure
    - Entered Value
    - Duty Rate
    - Calculated duty
  - **Summary Section**:
    - Total declared value
    - Total duty owed
    - Fees (MPF, HMF)
- **Formats**: Electronic ACE submission, PDF output
- **Anchor Links**: Entry#, BL#, Invoice#, Importer

---

### **Supporting Documents**

#### 9. **Certificate of Origin**
- **Source**: Exporter or Chamber of Commerce
- **Purpose**: Prove country of origin for duty benefits (e.g., USMCA)
- **Formats**: PDF (often with official stamps/seals)
- **Anchor Links**: Invoice#, BL#

#### 10. **Importer's Declaration / Power of Attorney**
- **Purpose**: Authorize broker to file on behalf of importer
- **Formats**: PDF (signed document)
- **Anchor Links**: Importer company name

#### 11. **Shipper's Email Communications**
- **Content**: Attachments with documents above
- **Subject lines**: Often contain BL#, PO#, container#
- **Importance**: **EMAIL INGESTION** feature extracts these

---

## 🔗 DATA RELATIONSHIP MAP

```
┌─────────────────────────────────────────────────────────────┐
│                    SHIPMENT LIFECYCLE                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────┐
        │   EMAIL FROM SHIPPER/FORWARDER          │
        │   Subject: "BL# MAEU123456789"          │
        │   Attachments: Commercial Invoice,       │
        │                Packing List, HBL        │
        └─────────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────┐
        │   MASTER BILL OF LADING (MBL)           │
        │   MBL#: MAEU123456789                   │
        │   Container: MSCU1234567                │
        │   Vessel: EVER GIVEN / V.123            │
        └─────────────────────────────────────────┘
                              │
                ┌─────────────┴─────────────┐
                ▼                           ▼
    ┌───────────────────────┐   ┌───────────────────────┐
    │  HOUSE BL (HBL)       │   │   HOUSE BL (HBL)      │
    │  HBL#: FWDR-001       │   │   HBL#: FWDR-002      │
    │  Container: MSCU1234567│   │  Container: MSCU1234567│
    └───────────────────────┘   └───────────────────────┘
                │                           │
                ▼                           ▼
    ┌───────────────────────┐   ┌───────────────────────┐
    │  COMMERCIAL INVOICE   │   │  COMMERCIAL INVOICE   │
    │  Invoice: INV-2024-001│   │  Invoice: INV-2024-002│
    │  BL: FWDR-001         │   │  BL: FWDR-002         │
    │  PO: PO-1001          │   │  PO: PO-1002          │
    └───────────────────────┘   └───────────────────────┘
                │                           │
                ▼                           ▼
    ┌───────────────────────┐   ┌───────────────────────┐
    │   PACKING LIST        │   │   PACKING LIST        │
    │   BL: FWDR-001        │   │   BL: FWDR-002        │
    │   Container: MSCU...  │   │   Container: MSCU...  │
    │   20 Cartons, 500kg   │   │   15 Cartons, 350kg   │
    └───────────────────────┘   └───────────────────────┘
                │                           │
                └───────────┬───────────────┘
                            ▼
            ┌──────────────────────────────┐
            │   ISF FILING                 │
            │   MBL: MAEU123456789         │
            │   Container: MSCU1234567     │
            │   Filed 24hrs before sailing │
            └──────────────────────────────┘
                            │
                            ▼
            ┌──────────────────────────────┐
            │   ARRIVAL NOTICE             │
            │   MBL: MAEU123456789         │
            │   Container: MSCU1234567     │
            │   ETA: 2024-03-15           │
            └──────────────────────────────┘
                            │
                            ▼
            ┌──────────────────────────────┐
            │   CUSTOMS ENTRY (3461)       │
            │   Entry#: ABC-1234567-8      │
            │   BL: MAEU123456789         │
            │   Importer: XYZ Corp        │
            └──────────────────────────────┘
                            │
                            ▼
            ┌──────────────────────────────┐
            │   ENTRY SUMMARY (7501)       │
            │   Entry#: ABC-1234567-8      │
            │   BL: MAEU123456789         │
            │   HTS: 6204.62.4020         │
            │   Value: $25,000            │
            │   Duty: $1,825              │
            └──────────────────────────────┘
                            │
                            ▼
            ┌──────────────────────────────┐
            │   CARGOWISE INTEGRATION      │
            │   Sync entry data for billing│
            │   Track shipment status      │
            └──────────────────────────────┘
```

---

## 🎯 ANCHOR POINT STRATEGY FOR YOUR SYSTEM

### **Recommended Primary Key Hierarchy**:

1. **Master Bill of Lading (MBL)** - Global shipment identifier
2. **House Bill of Lading (HBL)** - Individual consignment identifier
3. **Container Number** - Physical cargo identifier
4. **Entry Number** - Customs filing identifier (created later)
5. **Invoice Number** - Commercial transaction identifier

### **Document Matching Logic**:

```python
# Pseudo-code for document linking
def link_documents(doc_collection):
    # Level 1: Group by MBL/HBL
    shipments = group_by(doc_collection, ["MBL", "HBL"])
    
    # Level 2: Validate with Container Numbers
    for shipment in shipments:
        validate_containers(shipment.documents)
    
    # Level 3: Match Invoices to Packing Lists
    for shipment in shipments:
        match_invoices_to_packing_lists(shipment, by=["PO_number", "BL"])
    
    # Level 4: Create Entry Number (if not exists)
    for shipment in shipments:
        if not shipment.entry_number:
            shipment.entry_number = generate_entry_number()
    
    # Level 5: Link everything to Entry Number
    for shipment in shipments:
        link_all_docs_to_entry(shipment)
```

---

## 📊 DOCUMENT FORMATS IN THE WILD

| Document Type | PDF | Excel | Word | Email | Scanned Image | EDI/XML |
|--------------|-----|-------|------|-------|---------------|---------|
| Commercial Invoice | ✅✅✅ | ✅✅ | ✅ | - | ✅ | - |
| Packing List | ✅✅ | ✅✅✅ | ✅ | - | ✅ | - |
| Bill of Lading | ✅✅✅ | - | - | - | ✅ | ✅ |
| ISF Form | ✅ | ✅✅✅ | - | - | - | - |
| Arrival Notice | ✅✅✅ | - | - | ✅✅✅ | - | - |
| CBP 7501 | ✅✅✅ | - | - | - | - | ✅ |
| Certificate of Origin | ✅✅✅ | - | - | - | ✅✅ | - |

**Legend**: ✅✅✅ = Very Common, ✅✅ = Common, ✅ = Occasional

---

## 🧪 TEST DATA REQUIREMENTS

To properly test your ingestion pipeline, you need:

### **Scenario 1: Single Container, Single Consignee**
- 1 × MBL
- 1 × HBL
- 1 × Commercial Invoice
- 1 × Packing List
- 1 × ISF Form
- 1 × Arrival Notice

### **Scenario 2: Single Container, Multiple Consignees (LCL)**
- 1 × MBL
- 3 × HBLs (different shippers)
- 3 × Commercial Invoices
- 3 × Packing Lists
- 1 × Consolidated ISF Form
- 1 × Arrival Notice

### **Scenario 3: Multiple Containers, Single Consignee (FCL)**
- 1 × MBL
- 2 × Container Numbers on same MBL
- 1 × HBL (covering both containers)
- 1 × Commercial Invoice
- 1 × Packing List (with container breakdown)
- 1 × ISF Form

### **Scenario 4: Email Ingestion Test**
- Email with subject containing BL number
- Multiple attachments (PDF + Excel)
- Forwarded email chain (reply-to headers)

---

## 🚀 NEXT STEPS

1. **Generate synthetic test documents** for each scenario
2. **Vary formats**: Same content in PDF, Excel, scanned PDF
3. **Add edge cases**:
   - Missing BL numbers
   - Mismatched container numbers
   - Partial data in documents
   - Multiple PO numbers on one invoice
4. **Test OCR quality** on scanned vs. digital PDFs
5. **Validate extraction accuracy** across formats

Would you like me to proceed with generating these test documents now?

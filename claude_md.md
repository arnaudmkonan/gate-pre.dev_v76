⏺ Platform Flow: Document Ingestion to Compliance

  This is a trade compliance document processing platform that ingests documents, extracts structured data, and performs automated compliance checks.

  ---
  High-Level Architecture

  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                              USER / SYSTEM                                  │
  │                         (Upload documents via UI/API)                       │
  └─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                            1. INGESTION LAYER                               │
  │   Upload → Storage (Supabase S3) → Queue Job (Redis) → Celery Worker        │
  └─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                         2. BRONZE LAYER (Raw Data)                          │
  │   Parse Document → Extract Text → Store Raw Content → Generate Embeddings   │
  └─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                      3. AGENT PROCESSING PIPELINE                           │
  │   Triage → Classification → Template Matching → Field Extraction            │
  └─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                       4. COMPLIANCE INTEGRATION (NEW)                       │
  │   HTS Validation → OFAC Screening → NAICS Classification → Risk Assessment  │
  └─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                         5. SILVER LAYER (Normalized)                        │
  │   Normalize Parties → Normalize Products → Entity Resolution → Link Records │
  └─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                          6. GOLD LAYER (Business)                           │
  │   Create Shipments → Link Documents → Auto-Link by Keys → Compliance Screens│
  └─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                            7. OUTPUT / ACTIONS                              │
  │   Human Review Queue → Compliance Reports → ACE Filing → Drawback Claims    │
  └─────────────────────────────────────────────────────────────────────────────┘

  ---
  Detailed Step-by-Step Flow

  Step 1: Document Upload

  User uploads file (PDF, Excel, Word, etc.)
           │
           ▼
      POST /api/storage/upload
           │
           ▼
      File stored in Supabase S3
           │
           ▼
      Job queued in Redis
           │
           ▼
      RawFile record created in PostgreSQL

  Step 2: Document Parsing (Bronze Layer)

  Celery worker picks up job
           │
           ▼
      Docling parser extracts text/tables
           │
           ▼
      RawExtraction record created
           │
           ▼
      OpenAI generates embeddings (text-embedding-3-small)
           │
           ▼
      VectorEmbedding stored in pgvector

  Step 3: Agent Processing Pipeline

      ┌─────────────────┐
      │  Triage Agent   │ ─── Determines document priority & routing path
      └────────┬────────┘
               │
               ▼
      ┌─────────────────┐
      │  Classifier     │ ─── Identifies document type (Invoice, BOL, Entry, etc.)
      └────────┬────────┘
               │
               ▼
      ┌─────────────────┐
      │ Template Match  │ ─── Finds best extraction template for document type
      └────────┬────────┘
               │
               ▼
      ┌─────────────────┐
      │ Template Extract│ ─── Extracts structured fields using template
      └────────┬────────┘     (seller, buyer, HTS codes, amounts, etc.)
               │
               ▼
        Extraction Results

  Example: Commercial Invoice Extraction
  {
    "seller_name": "Acme Trading Co.",
    "buyer_name": "US Import Corp",
    "invoice_number": "INV-2024-001",
    "total_amount": 50000.00,
    "country_of_origin": "China",
    "line_items": [
      {"description": "Electronics", "hs_code": "8471.30.01", "quantity": 100}
    ]
  }

  Step 4: Compliance Integration (NEW)

      Extraction Results
               │
               ▼
      ┌─────────────────────────────────────────────┐
      │         PostExtractionService               │
      │                                             │
      │  ┌─────────────┐  ┌─────────────┐           │
      │  │ HTS Validate│  │ OFAC Screen │           │
      │  │ 8471.30.01  │  │ Acme Trading│           │
      │  │   ✓ Valid   │  │  ✓ Clear    │           │
      │  │ Duty: Free  │  │             │           │
      │  └─────────────┘  └─────────────┘           │
      │                                             │
      │  ┌─────────────┐  ┌─────────────┐           │
      │  │NAICS Suggest│  │ Risk Level  │           │
      │  │ 334-Computer│  │   CLEAR     │           │
      │  └─────────────┘  └─────────────┘           │
      └─────────────────────────────────────────────┘
               │
               ▼
      ComplianceScreen records created
      (If HIGH/CRITICAL → flagged for human review)

  Step 5: Silver Layer (Normalization)

      Extracted entities
               │
               ▼
      ┌───────────────────────────────┐
      │    Entity Resolution          │
      │                               │
      │  "Acme Trading Co."           │
      │  "ACME TRADING COMPANY"  ───► Party record (deduplicated)
      │  "Acme Trading Company"       │
      │                               │
      │  Product normalization        │
      │  Address standardization      │
      └───────────────────────────────┘
               │
               ▼
      Party, Product, Address records in Silver tables

  Step 6: Gold Layer (Business Records)

      ┌─────────────────────────────────────────────┐
      │           Key Extraction                    │
      │                                             │
      │  Document → Extract identifiers:            │
      │    • Entry Number: ABC12345678              │
      │    • BOL Number: MAEU1234567890             │
      │    • Container: MSCU1234567                 │
      │    • PO Number: PO-2024-001                 │
      └─────────────────────────────────────────────┘
                           │
                           ▼
      ┌─────────────────────────────────────────────┐
      │           Auto-Linker Service               │
      │                                             │
      │  Find documents with shared keys:           │
      │                                             │
      │  Invoice ─┐                                 │
      │  BOL ─────┼──► Same Entry# ──► SHIPMENT     │
      │  Packing ─┤                                 │
      │  Entry ───┘                                 │
      │                                             │
      └─────────────────────────────────────────────┘
                           │
                           ▼
      Shipment record with linked documents

  Step 7: Outputs & Actions

  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
  │  Review Queue   │  │ Compliance      │  │  Trade Actions  │
  │                 │  │ Dashboard       │  │                 │
  │ • Low confidence│  │ • Risk scores   │  │ • ACE filing    │
  │ • OFAC matches  │  │ • OFAC hits     │  │ • Drawback claim│
  │ • Invalid HTS   │  │ • HTS errors    │  │ • Entry recon   │
  │ • Duplicates    │  │ • Audit trail   │  │ • Prior discl.  │
  └─────────────────┘  └─────────────────┘  └─────────────────┘

  ---
  Data Model Summary

  BRONZE (Raw)              SILVER (Normalized)         GOLD (Business)
  ─────────────────         ──────────────────          ───────────────
  RawFile                   Party                       Shipment
  RawExtraction             Product                     CommercialInvoice
  VectorEmbedding           Address                     CustomsEntry
  DocumentMetadata          EntityLink                  InvoiceLine
  DocumentKey               SilverMetadata              ComplianceScreen
                                                        DrawbackLedger

  REFERENCE DATA
  ──────────────
  HTSCode (with embeddings)
  NAICSCode (with embeddings)
  OFACSdn (with embeddings)

  ---
  Example End-to-End Scenario

  Scenario: Importer uploads a Commercial Invoice PDF

  1. Upload → File stored, job queued
  2. Parse → Text extracted: "Invoice INV-001, Seller: Acme Corp, HTS: 8471.30.01..."
  3. Classify → Document type: commercial_invoice
  4. Extract → Template extracts 15 fields (seller, buyer, items, amounts)
  5. Compliance:
    - HTS 8471.30.01 → ✓ Valid, Duty: Free
    - Seller "Acme Corp" → ✓ OFAC Clear
    - NAICS suggestion: 334 (Computer Manufacturing)
  6. Normalize → Party "Acme Corp" linked to existing Party record
  7. Link → Entry number found → Linked to existing Shipment with BOL and Packing List
  8. Output → Shipment now has 3 documents, ready for audit

  ---
  Key Integration Points
  ┌────────────────────┬──────────────────────────┬──────────────────────────────────────────┐
  │     Component      │         Triggers         │                 Produces                 │
  ├────────────────────┼──────────────────────────┼──────────────────────────────────────────┤
  │ Upload API         │ User action              │ RawFile + Job                            │
  ├────────────────────┼──────────────────────────┼──────────────────────────────────────────┤
  │ Extract Worker     │ Job queue                │ RawExtraction + Embeddings               │
  ├────────────────────┼──────────────────────────┼──────────────────────────────────────────┤
  │ Agent Pipeline     │ Extraction complete      │ Classifications + Extractions            │
  ├────────────────────┼──────────────────────────┼──────────────────────────────────────────┤
  │ Compliance Service │ Template extraction      │ HTS validation, OFAC screens, Risk level │
  ├────────────────────┼──────────────────────────┼──────────────────────────────────────────┤
  │ Auto-Linker        │ Key extraction           │ Shipment linkages                        │
  ├────────────────────┼──────────────────────────┼──────────────────────────────────────────┤
  │ Review Service     │ Low confidence/High risk │ Review queue items                       │
  └────────────────────┴──────────────────────────┴──────────────────────────────────────────┘

  
  
  Data Being Saved to DB
  ┌────────────────────┬────────────────────────────┬───────────────────────┐
  │       Table        │        When Created        │         Auto?         │
  ├────────────────────┼────────────────────────────┼───────────────────────┤
  │ raw_files          │ On upload                  │ ✅ Yes                │
  ├────────────────────┼────────────────────────────┼───────────────────────┤
  │ raw_extractions    │ After text extraction      │ ✅ Yes                │
  ├────────────────────┼────────────────────────────┼───────────────────────┤
  │ document_keys      │ After key extraction       │ ✅ Yes                │
  ├────────────────────┼────────────────────────────┼───────────────────────┤
  │ shipments          │ When documents auto-linked │ ✅ Yes                │
  ├────────────────────┼────────────────────────────┼───────────────────────┤
  │ shipment_documents │ When linked                │ ✅ Yes                │
  ├────────────────────┼────────────────────────────┼───────────────────────┤
  │ document_metadata  │ During job processing      │ ✅ Yes                │
  ├────────────────────┼────────────────────────────┼───────────────────────┤
  │ extraction_results │ After template extraction  │ ⚠️ Only if agent runs │
  ├────────────────────┼────────────────────────────┼───────────────────────┤
  │ compliance_screens │ After OFAC screening       │ ⚠️ Only if agent runs │
  ├────────────────────┼────────────────────────────┼───────────────────────┤
  │ review_queue_items │ If flagged for review      │ ⚠️ Only if agent runs │
  └────────────────────┴────────────────────────────┴───────────────────────┘

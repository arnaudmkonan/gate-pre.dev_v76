# Trade Document Extraction Template

This folder contains prompts and schemas for extracting structured data from 
trade and customs documents using LLM-based analysis.

## Document Types Supported

1. **Arrival Notice** - Shipping notifications with deadlines
2. **Master Bill of Lading** - Ocean carrier documents
3. **House Bill of Lading** - Freight forwarder documents  
4. **Packing List** - Cargo details and quantities
5. **Commercial Invoice** - Financial documents with values
6. **Certificate of Origin** - Country of origin documentation
7. **Insurance Certificate** - Cargo insurance
8. **Customs Entry** - CBP filing documents

## Output Schema

All extractions produce JSON with these sections:
- `document_metadata` - Type, date, references
- `parties` - Shipper, consignee, notify party, carrier
- `shipment` - BOLs, vessel, ports, dates
- `cargo` - Items with HS codes, quantities, weights
- `financials` - Invoice, charges, totals
- `deadlines_and_risks` - LFD, demurrage, per diem
- `compliance` - Signatures, originals, declarations

## Usage

The prompt is used by the agent processor to extract data that populates:
- Bronze layer: Raw extraction results
- Silver layer: Normalized parties, products, addresses
- Gold layer: Shipments, entries, invoices

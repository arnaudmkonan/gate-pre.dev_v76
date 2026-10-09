# GATE Platform: MVP User Guide & Evaluation

**Status:** 🟢 **READY FOR MVP**
Based on comprehensive testing of the backend data ingestion pipelines, ACE/CBP compliance engine, and the frontend React portal, the GATE (Global Automated Trade Entry) platform exhibits all the required functionality for a Minimum Viable Product (MVP) release. The critical "Golden Path" (Document Ingestion -> AI Extraction -> Human Review -> Trade Compliance Validations -> ACE Transmission) is completely wired.

This document serves as the primary user manual for operating the MVP.

---

## 1. Getting Started & Authentication

The GATE Platform utilizes a secure, role-based architecture designed for Customs Brokers and their Clients. 

### Logging In
1. Navigate to the web portal URL (e.g., `http://localhost:3000`).
2. **For Evaluators/Testing:** Public registration is intentionally disabled. You can instantly access the system using the **Demo Accounts** panel on the login screen:
   * **Admin User:** Click "Admin User" (`admin@example.com`) for full system configuration and oversight access.
   * **Standard User:** Click "Standard User" (`demo@example.com`) for standard operational access.
3. Click **Sign in**.

---

## 2. Core Workflow: Document Ingestion & Review

The heart of GATE is its DocuMind AI extraction pipeline, designed to automatically digitize physical trade documents.

### Step 2.1: Ingesting Documents
1. From the left sidebar, navigate to **Documents > Ingest Documents**.
2. Click or drag-and-drop your Customs Documents (Commercial Invoices, Packing Lists, Bills of Lading).
*Note: Once uploaded, the documents are asynchronously placed in a queue and processed by background AI workers (Celery) extracting text via OCR and LLM-based structured extraction.*

### Step 2.2: Review Queue (Human-in-the-Loop)
1. Navigate to **Documents > Review Queue**.
2. Documents that have been processed will appear here. The system highlights fields with a "Low Confidence" score.
3. Click on a document to open the **Review Item Detail** view. You will see a side-by-side layout:
   * **Left side:** The original document viewer.
   * **Right side:** The structured data extracted by the AI.
4. Correct any highlighted fields, then click **Approve Extraction** to convert the document into a structured entity.

---

## 3. Customs Operations & Compliance

Once documents are digitized, they move into the Gold Layer (Data Fabric) for compliance validation and CBP filing preparation.

### Step 3.1: Shipment Assembly
1. Go to **Documents > Shipment Assembly**.
2. Group related approved documents (e.g., linking a Commercial Invoice with its corresponding Bill of Lading) into a single "Shipment" entity.

### Step 3.2: Trade Compliance Verification
1. Navigate to **Compliance > Trade Compliance** or open a specific shipment.
2. The Trade Compliance Engine automatically evaluates the data against CBP rules:
   * Validates HTSUS (Harmonized Tariff Schedule) Codes.
   * Runs the **PGA Determination Engine** (Partner Government Agencies like FDA, EPA, DOT) to verify if additional forms are required based on the commodities.
   * Flags missing mandatory elements.

### Step 3.3: Managing Customs Entries
1. Navigate to **Core > Customs Entries**.
2. View automatically drafted Entry Summaries (equivalent to CBP Form 7501). 
3. Duty calculations and fee assessments are finalized here.

---

## 4. ACE Transmission (CBP Filing)

The MVP includes live integration points for the Automated Commercial Environment (ACE).

1. Navigate to **Tools > ACE Import**.
2. Authorized brokers can securely transmit validated Entry Summaries to CBP via the `ACETransmitter` (SFTP).
3. The platform continuously monitors responses. When CBP accepts the entry or issues an ABI (Automated Broker Interface) message, the status on the dashboard updates dynamically in real-time.

---

## 5. System Administration (Admins Only)

Users logged in as Admins have access to the **System** and **Admin** configuration bays.

*   **Role Management:** Under **Admin > Roles & Permissions**, you can configure access levels (Admin, User, Read-Only) for internal staff and external clients.
*   **Infrastructure:** Under **System**, Admins can monitor the health of the queues (**DLQ Management**, **Monitoring**), manage embeddings databases (**Vector Store Config**), and adjust cloud storage locations (**Storage Config**).

---
*Generated for the GATE MVP release (Feb 2026).*

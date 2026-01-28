# GATE User Manual

## Customs Entry Management System

**Version 1.0** | Last Updated: January 2026

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Dashboard](#dashboard)
3. [Customs Entries](#customs-entries)
4. [Client Management](#client-management)
5. [Duty Calculator](#duty-calculator)
6. [ISF Filing (10+2)](#isf-filing)
7. [Entry Lifecycle](#entry-lifecycle)
8. [Analytics & Reporting](#analytics)
9. [Subscription & Billing](#billing)
10. [Troubleshooting](#troubleshooting)

---

## Getting Started {#getting-started}

### First Login & Onboarding

When you first log in to GATE, you'll be guided through a setup wizard:

1. **Welcome** - Introduction to the platform
2. **Company Profile** - Enter your brokerage information
3. **ACE Credentials** - Connect to CBP's ACE portal (optional, can skip)
4. **First Client** - Add your first importer client
5. **Upload Sample Document** - Try AI-powered document extraction
6. **Create First Entry** - Walk through creating a customs entry

You can skip the wizard and come back later from Settings → Onboarding.

### Navigation

The sidebar provides access to all features:

| Section | Purpose |
|---------|---------|
| **Dashboard** | Overview of pipeline status, metrics, and analytics |
| **Customs Entries** | Create and manage CBP Form 7501 entries |
| **Duty Calculator** | Calculate duties, tariffs, fees |
| **AI Agents** | Automated document processing |
| **Review Queue** | Review AI-extracted data |
| **Clients** | Manage importer clients |
| **Duty Drawback** | Manage drawback claims |
| **ACE Import** | Import CBP data |
| **Settings** | System configuration |

---

## Dashboard {#dashboard}

The Dashboard provides a real-time overview of your operations:

### Key Metrics

- **Total Entries** - Entries filed this period
- **Pending Review** - Documents awaiting review
- **Total Duty** - Cumulative duty collected
- **Success Rate** - Processing accuracy

### Pipeline Status

Shows the status of document processing:
- Uploaded → Processing → Extracted → Reviewed → Filed

### Recent Activity

Timeline of recent actions, alerts, and system notifications.

---

## Customs Entries {#customs-entries}

### Creating a New Entry

#### Method 1: Manual Entry

1. Click **+ New Entry**
2. Select Entry Type:
   - **Consumption (01)** - Standard import entry
   - **Warehouse (21)** - Bonded warehouse
   - **FTZ (06)** - Foreign Trade Zone
3. Fill in required fields:
   - Port of Entry (e.g., 4601 for Los Angeles)
   - Importer of Record Number
   - Entry Date
4. Add line items (HTS codes, values, quantities)
5. Save as Draft or Submit

#### Method 2: From Documents (Recommended)

1. Upload commercial invoice and packing list
2. AI extracts data automatically
3. Review in Review Queue
4. Click **Create Entry** to populate form
5. Verify and submit

### Entry Fields Reference

| Field | Description | Example |
|-------|-------------|---------|
| **Entry Number** | 11-digit CBP entry number | 123-1234567-8 |
| **Entry Type** | Type of consumption entry | 01 (Consumption) |
| **Port of Entry** | 4-digit port code | 4601 (Los Angeles) |
| **IOR Number** | Importer of Record ID | 12-3456789 |
| **Entry Date** | Date of entry | 2026-01-15 |
| **Arrival Date** | Vessel/cargo arrival | 2026-01-14 |
| **Bond Type** | Continuous or Single Entry | C (Continuous) |

### Entry Line Items

Each line requires:

| Field | Required | Description |
|-------|----------|-------------|
| HTS Code | ✅ | 10-digit tariff code |
| Country of Origin | ✅ | ISO 2-letter code (CN, MX, etc.) |
| Entered Value | ✅ | FOB value in USD |
| Description | ✅ | Product description |
| Quantity | ✅ | Number of units |
| Gross Weight | ❌ | Weight in KG |

### Entry Status Workflow

```
DRAFT → PENDING_REVIEW → READY → FILED → ACCEPTED → LIQUIDATED
                              ↓
                           REJECTED → AMENDED
```

---

## Client Management {#client-management}

### Adding a New Client

1. Navigate to **Clients** → **+ Add Client**
2. Enter client details:
   - Company Name
   - IOR Number (Importer of Record)
   - Tax ID / EIN
   - Address
   - Primary Contact
3. Configure client settings:
   - Default port of entry
   - Bond information
   - Billing preferences

### Client Dashboard

View client-specific metrics:
- Total entries filed
- Duty paid YTD
- Compliance score
- Recent activity

### Client Preferences

Configure per-client settings:
- Email notifications
- Report schedules
- Document request preferences
- Billing alerts

---

## Duty Calculator {#duty-calculator}

### Quick Calculation

1. Go to **Duty Calculator**
2. Enter:
   - HTS Code (e.g., 8471.30.0100)
   - Entered Value (USD)
   - Country of Origin
   - Quantity (for specific duties)
3. Click **Calculate**

### Duty Components

| Component | Description |
|-----------|-------------|
| **Base Duty** | Normal MFN duty rate (0-50%) |
| **Section 301** | China-specific tariffs (7.5-25%) |
| **Section 232** | Steel/Aluminum tariffs (10-25%) |
| **ADD** | Antidumping duties |
| **CVD** | Countervailing duties |
| **MPF** | Merchandise Processing Fee (0.3464%) |
| **HMF** | Harbor Maintenance Fee (0.125%) |

### FTA Eligibility Check

1. Select origin country
2. Enter HTS code
3. System shows:
   - Available FTA (USMCA, KORUS, etc.)
   - Preferential rate
   - Potential savings
   - Certificate requirements

### Landed Cost Calculator

Calculate total cost of importing:
- Product cost
- Freight & insurance
- All duties and fees
- Total landed cost

---

## ISF Filing (10+2) {#isf-filing}

### Creating an ISF

ISF must be filed 24 hours before vessel departure for ocean shipments.

1. Go to **ISF Filing** → **+ New ISF**
2. Enter the 10 importer elements:
   - Seller name/address
   - Buyer name/address
   - Importer of Record number
   - Consignee number
   - Manufacturer (MID)
   - Ship-to party
   - Country of origin
   - HTS codes (6-digit)
   - Container stuffing location
   - Consolidator

3. Carrier provides +2 elements:
   - Vessel stow plan
   - Container status messages

### ISF Status

| Status | Meaning |
|--------|---------|
| **Draft** | In progress, not submitted |
| **Pending** | Submitted, awaiting CBP response |
| **Accepted** | CBP accepted the filing |
| **Rejected** | CBP rejected - review errors |
| **Matched** | Matched to entry |

### Amendments

ISF supports "flexible filing" - you can file with partial information and amend later, as long as it's before cargo arrival.

---

## Entry Lifecycle {#entry-lifecycle}

### Liquidation Tracking

Entries liquidate approximately 314 days after entry date.

1. Navigate to **Entry Lifecycle** → **Liquidation**
2. View entries approaching liquidation:
   - Entry number
   - Estimated liquidation date
   - Duty difference (estimated vs. liquidated)
   - Refund owed

### Protests

If you disagree with CBP's liquidation:

1. Go to **Protests** → **+ New Protest**
2. Select entry to protest
3. Enter:
   - Protest category
   - Reason
   - Duty contested
   - Refund requested
4. File within 180 days of liquidation

### Reconciliation Entries

For entries flagged for reconciliation:

1. View flagged entries grouped by flag type
2. Calculate final values
3. Submit reconciliation entry
4. Track CBP acceptance

### Duty Drawback

Claim duty refunds on re-exported goods:

1. **Eligibility Check** - Verify items qualify
2. **Create Claim** - Link import entries and export records
3. **Calculate Refund** - Up to 99% of duties paid
4. **Submit** - File with CBP
5. **Track** - Monitor approval status

---

## Analytics & Reporting {#analytics}

### Dashboard Analytics

The analytics dashboard shows:

- **Entry Volume** - Entries by day/week/month
- **Duty by Category** - Breakdown by tariff chapter
- **Top HTS Codes** - Most frequent products
- **Client Distribution** - Entries by client
- **Compliance Metrics** - Accuracy and error rates

### Compliance Scorecard

Track compliance health:

| Score | Rating | Description |
|-------|--------|-------------|
| 90-100 | Excellent | Minimal issues |
| 75-89 | Good | Minor improvements needed |
| 60-74 | Fair | Attention required |
| <60 | Poor | Immediate action needed |

### Scheduled Reports

Set up automated reports:

1. Go to **Reports** → **Schedule New**
2. Select report type:
   - Entry Summary
   - Duty Analysis
   - Client Activity
   - Compliance Report
3. Set frequency: Daily, Weekly, Monthly
4. Choose recipients
5. Activate

Reports are delivered via email as PDF/Excel.

### Export Data

Export data to CSV/Excel:

1. Go to any list view (Entries, Clients, etc.)
2. Apply filters if needed
3. Click **Export**
4. Select format (CSV or Excel)
5. Download

---

## Subscription & Billing {#billing}

### Subscription Tiers

| Tier | Price | Entries/Month | Clients | Features |
|------|-------|---------------|---------|----------|
| **Free** | $0 | 10 | 1 | Core features |
| **Starter** | $299/mo | 50 | 5 | + ISF, Analytics |
| **Professional** | $599/mo | 500 | 50 | + Drawback, API |
| **Enterprise** | $1,499/mo | Unlimited | Unlimited | All features + Support |

### Managing Subscription

1. Go to **Settings** → **Subscription**
2. View current plan and usage
3. Upgrade/downgrade as needed
4. Update payment method
5. View invoice history

### Usage Tracking

Monitor your usage:
- Entries filed this month
- Entries remaining
- Storage used

---

## Troubleshooting {#troubleshooting}

### Common Issues

| Issue | Solution |
|-------|----------|
| Entry won't submit | Check for validation errors (red highlights) |
| HTS code not found | Verify 10-digit code, check for typos |
| Document upload fails | Ensure PDF < 50MB, try different browser |
| ISF rejected | Review CBP response, correct data, resubmit |
| Slow performance | Clear browser cache, try Chrome/Edge |

### Getting Help

1. **Help Center** - Click **?** icon for contextual help
2. **Search Docs** - Use `/help` to search articles
3. **Contact Support** - support@yourbrokerage.com
4. **Phone** - 1-800-XXX-XXXX (Enterprise only)

### Error Messages

| Error | Meaning |
|-------|---------|
| `Entry limit reached` | Upgrade plan or wait for next month |
| `Invalid HTS code` | Code doesn't exist in current tariff schedule |
| `Bond not on file` | Add valid bond in client settings |
| `IOR not validated` | Verify IOR number with CBP |

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl + N` | New entry |
| `Ctrl + S` | Save draft |
| `Ctrl + Enter` | Submit entry |
| `Ctrl + /` | Search |
| `Escape` | Close modal |

---

## Glossary

| Term | Definition |
|------|------------|
| **ACE** | Automated Commercial Environment (CBP system) |
| **ADD** | Antidumping Duties |
| **CBP** | Customs and Border Protection |
| **CVD** | Countervailing Duties |
| **FTA** | Free Trade Agreement |
| **HMF** | Harbor Maintenance Fee |
| **HTS** | Harmonized Tariff Schedule |
| **IOR** | Importer of Record |
| **ISF** | Importer Security Filing (10+2) |
| **MFN** | Most Favored Nation (normal rates) |
| **MID** | Manufacturer Identification |
| **MPF** | Merchandise Processing Fee |
| **USMCA** | US-Mexico-Canada Agreement |

---

*For questions or support, contact: support@yourbrokerage.com*

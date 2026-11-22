# Broker Pilot Onboarding

Use this to put a boutique customs broker on a **dedicated single-tenant pilot** for acceptance testing.

**Positioning (say this explicitly):**  
AI document intake, compliance triage, and **CBP Form 7501 / ISF / CargoWise entry-prep workbench**.  
v1 **exports drafts** (7501 PDF/Excel, ISF-10 ABI, CargoWise XML). The broker files to CBP via **their existing ABI software** unless live ACE SFTP is separately scoped.

Related ops docs: [ARCHITECTURE.md](ARCHITECTURE.md) · [PILOT_SMTP.md](PILOT_SMTP.md) · [PILOT_HTTPS.md](PILOT_HTTPS.md) · [PILOT_ACE.md](PILOT_ACE.md)

---

## 1. Collect from the broker (before provision)

| Field | Required | Example / notes |
|-------|----------|-----------------|
| Legal brokerage name | Yes | Used as `BROKER_NAME` / UI brand |
| Admin email | Yes | First portal admin |
| CBP filer code (3-char) | Yes | `BROKER_FILER_CODE` |
| Default port of entry | Nice | 4-digit CBP port |
| CargoWise company code | Yes if they use CW | `CARGOWISE_COMPANY_CODE` |
| CargoWise enterprise ID | Yes if they use CW | `CARGOWISE_ENTERPRISE_ID` |
| SMTP for outbound mail | Yes for doc requests / resets | See PILOT_SMTP |
| Brand subtitle (optional) | No | Shown under product name |
| Pilot subdomain | Yes | e.g. `acme` → `acme.gateplatform.com` |
| Sample docs for day-1 walkthrough | Yes | Invoice + packing list + BOL (or their real set) |

**Do not promise:** live ACE/ISF SFTP, unsupervised HTS classification, multi-broker SaaS tenancy.

---

## 2. Operator: provision & harden

```bash
# From repo root
export BROKER_FILER_CODE=AB1          # from intake
export BROKER_DEFAULT_PORT=2704       # optional

./provisioning/scripts/provision.sh \
  acme-broker \
  "Acme Customs Brokerage" \
  admin@acme-broker.com \
  acme

cd instances/acme-broker
# Merge any SMTP / OpenAI / brand overrides into .env
# (template: provisioning/templates/pilot.env.example)
./start.sh
./init.sh
```

Production-safe defaults that `provision.sh` already sets:

- `ENVIRONMENT=production`
- `ACE_ALLOW_SIMULATION=false`
- `ACE_SFTP_ENABLED=false`
- `AUDIT_LOG_RETENTION_DAYS=2555`
- `SEED_DEMO_USERS=false` (or disable after smoke)

White-label: rebuild/restart frontend if you change `VITE_BRAND_*` (bake-time).

### Smoke before sharing credentials

```bash
./provisioning/scripts/verify-instance.sh \
  http://localhost:8101 \
  admin@acme-broker.com \
  '<provisioned-password>'
```

Expect: health OK, scrypt session, broker profile, 19 CFR 163 retention, HTS seed ≥ 50.

Then:

1. Admin logs in → **Settings → Broker Profile** → confirm name / filer / CargoWise codes  
2. Rotate admin password  
3. Create one broker_staff user (optional)  
4. Confirm SMTP with a password-reset or Request Doc test  

---

## 3. Broker day-1 acceptance walkthrough (~30–45 min)

Give them this script; stay on the call for the first run.

| Step | Action | Pass criteria |
|------|--------|----------------|
| A | Login at pilot URL | Lands on app; no demo shortcuts in production |
| B | **Ingest** → upload invoice + packing list + BOL | “File uploaded successfully”; jobs complete |
| C | **Review Queue** → open an item | DocumentViewer: Original / Extracted Text / Download |
| D | Approve / correct key fields if needed | Shipment / gold fields update |
| E | **Shipments** → open assembled shipment | Header shows BOL / importer / values from docs |
| F | **Generate ISF (10+2)** + **Download ISF-10 ABI Draft** | Draft downloads; no claim of CBP transmission |
| G | **Request Doc** (optional) | Dropdown from `document_types` catalog; template instructions load; email sent **or** clear SMTP/contact message. With `EMAIL_IMAP_*` set, replies carrying `[GATE-DOCREQ:…]` auto-ingest and link to the shipment |
| H | **Prepare 7501** → review lines / HTS search | No fake G76 / EIN / \$48,500 fillers |
| I | Export **7501 PDF** + **Excel** | Files open; broker name / filer present when configured |
| J | **Save as Official Entry** → Export **CargoWise XML** | XML has their company code; imports or validates in CW sandbox |
| K | Confirm ACE File / Simulate hidden or blocked | No fake “filed with CBP” success in production |

---

## 4. Acceptance checklist (sign-off)

Broker initials / date:

- [ ] Understands product is **draft/export workbench**, not live CBP filing  
- [ ] Ingest + review path works on their sample docs  
- [ ] 7501 PDF/Excel usable for their ABI handoff  
- [ ] CargoWise XML acceptable **or** deferred to Phase 2 tweak  
- [ ] ISF ABI draft acceptable **or** deferred  
- [ ] Admin password rotated; only their staff have access  
- [ ] SMTP works for resets / missing-doc requests **or** waived for pilot week 1  
- [ ] Known limitations acknowledged (live ACE, GRI HTS, KMS column encryption)

**Pilot success =** they complete A–K once on their docs without blocker tickets.

---

## 5. First-week support posture

| Severity | Example | Response |
|----------|---------|----------|
| Blocker | Cannot upload / login / export 7501 | Same-day fix or rollback |
| Major | Wrong CW company code, SMTP fail | Config patch within 1 business day |
| Minor | UI copy, HTS seed gap | Batch into next pilot build |

Collect: screenshot, entry/shipment ID, approx time UTC, whether production ACE simulation is off (`GET /api/reference-data/broker-profile` → `ace_mode` should be `export_only` when SFTP off + simulation false).

---

## 6. Upsell / Phase 2 (do not include in pilot scope)

1. Live ACE ABI / ISF SFTP (needs their CBP circuit) — [PILOT_ACE.md](PILOT_ACE.md)  
2. Deeper GRI HTS agent assist  
3. KMS / column encryption for tax IDs  
4. Shared inbox IMAP tuning for their mail domain  

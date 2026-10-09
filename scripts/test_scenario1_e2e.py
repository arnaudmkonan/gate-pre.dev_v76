#!/usr/bin/env python3
"""
E2E Test Script for Scenario 1 Documents
Location: data/demo_documents/scenario_1/
"""
import os
import sys
import time
import json
import requests

API_BASE = os.getenv("API_URL", "http://localhost:8000")
ADMIN_EMAIL = "admin@gate.local"
ADMIN_PASSWORD = "GatesAdmin2024!"
DATA_DIR = "/Users/karnaudmac/projects/gate-pre.dev_v76/data/demo_documents/scenario_1"

def log(msg, symbol="ℹ️"):
    print(f"{symbol}  {msg}")

def run_test():
    print("==================================================================")
    print("🚀 GATES E2E Test — Scenario 1 (data/demo_documents/scenario_1)")
    print("==================================================================")
    
    # 1. Login
    log("Logging in as admin@gate.local...", "🔑")
    resp = requests.post(f"{API_BASE}/api/portal/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    
    if resp.status_code != 200:
        log(f"Login failed! HTTP {resp.status_code}: {resp.text}", "❌")
        sys.exit(1)
        
    auth_data = resp.json()
    token = auth_data.get("session_token")
    headers = {"Authorization": f"Bearer {token}"}
    log(f"Authenticated successfully! Token: {token[:16]}...", "✅")
    
    # 2. Inspect Files to Upload
    files_to_upload = [
        f for f in os.listdir(DATA_DIR)
        if os.path.isfile(os.path.join(DATA_DIR, f)) and not f.startswith(".")
    ]
    log(f"Found {len(files_to_upload)} documents in {DATA_DIR}:", "📂")
    for fname in sorted(files_to_upload):
        log(f"   • {fname}")
        
    # 3. Upload Files
    print("\n------------------------------------------------------------------")
    log("Step 1: Uploading Scenario 1 Documents...", "📤")
    uploaded_jobs = []
    
    for fname in sorted(files_to_upload):
        filepath = os.path.join(DATA_DIR, fname)
        with open(filepath, "rb") as f:
            files = {"file": (fname, f)}
            data = {"source": "e2e_scenario_1_test"}
            up_resp = requests.post(f"{API_BASE}/api/upload", headers=headers, files=files, data=data)
            
        if up_resp.status_code in (200, 202):
            job_info = up_resp.json()
            uploaded_jobs.append(job_info)
            log(f"  ✓ {fname} → Job ID: {job_info.get('job_id')} (status: {job_info.get('status')})", "✅")
        else:
            log(f"  ✗ {fname} upload failed! HTTP {up_resp.status_code}: {up_resp.text}", "❌")
            
    # 4. Monitor Ingestion Jobs
    print("\n------------------------------------------------------------------")
    log("Step 2: Polling Ingestion Pipeline for Completion...", "⏳")
    job_ids = [j.get("job_id") for j in uploaded_jobs if j.get("job_id")]
    
    max_wait = 180  # seconds
    start_time = time.time()
    all_completed = False
    
    while time.time() - start_time < max_wait:
        resp = requests.get(f"{API_BASE}/api/ingest/jobs?limit=100", headers=headers)
        if resp.status_code == 200:
            raw = resp.json()
            jobs_list = raw.get("jobs", raw) if isinstance(raw, dict) else raw
            if isinstance(jobs_list, list):
                our_jobs = [j for j in jobs_list if j.get("id") in job_ids]
                completed_count = sum(1 for j in our_jobs if j.get("status") == "completed")
                failed_count = sum(1 for j in our_jobs if j.get("status") == "failed")
                pending_count = len(our_jobs) - completed_count - failed_count
                
                elapsed = int(time.time() - start_time)
                print(f"\r  ⏳ {elapsed}s elapsed — {completed_count} completed, {pending_count} processing, {failed_count} failed (of {len(job_ids)} uploaded)", end="", flush=True)
                
                if completed_count + failed_count == len(job_ids):
                    print()
                    log(f"Pipeline processing finished in {elapsed} seconds!", "✅")
                    all_completed = True
                    break
        time.sleep(3)
        
    if not all_completed:
        print()
        log(f"Pipeline polling timed out after {max_wait}s", "⚠️")

    # 5. Validate Extracted Documents & Review Queue
    print("\n------------------------------------------------------------------")
    log("Step 3: Validating Extracted Entities & Review Items...", "🔎")
    rev_resp = requests.get(f"{API_BASE}/api/review/items?limit=50", headers=headers)
    if rev_resp.status_code == 200:
        rev_data = rev_resp.json()
        items = rev_data if isinstance(rev_data, list) else rev_data.get("items", rev_data.get("results", []))
        log(f"Total Items in Review Queue: {len(items)}", "📄")
    
    # 6. Validate Shipment Assembly
    print("\n------------------------------------------------------------------")
    log("Step 4: Validating Shipment Auto-Assembly...", "🚢")
    ship_resp = requests.get(f"{API_BASE}/api/shipments?limit=50", headers=headers)
    if ship_resp.status_code == 200:
        ship_data = ship_resp.json()
        shipments = ship_data if isinstance(ship_data, list) else ship_data.get("shipments", ship_data.get("items", []))
        log(f"Total Shipments in System: {len(shipments)}", "⚓")
        for idx, s in enumerate(shipments[:5], 1):
            if isinstance(s, dict):
                log(f"  Shipment #{idx}: ID={s.get('id')} | Ref={s.get('reference_num')} | B/L={s.get('bol_number')} | Status={s.get('status')} | Docs={s.get('document_count')}")

    sug_resp = requests.get(f"{API_BASE}/api/shipments/suggestions", headers=headers)
    if sug_resp.status_code == 200:
        sug_data = sug_resp.json()
        sug_list = sug_data.get("suggestions", sug_data) if isinstance(sug_data, dict) else sug_data
        if isinstance(sug_list, list):
            log(f"Shipment Assembly Suggestions Generated: {len(sug_list)}", "💡")

    # 7. Validate Customs Entries (Form 7501)
    print("\n------------------------------------------------------------------")
    log("Step 5: Validating Customs Entry Summaries (Form 7501)...", "📋")
    ent_resp = requests.get(f"{API_BASE}/api/entries?limit=50", headers=headers)
    if ent_resp.status_code == 200:
        ent_data = ent_resp.json()
        entries = ent_data if isinstance(ent_data, list) else ent_data.get("items", ent_data.get("entries", []))
        log(f"Total Customs Entries: {len(entries)}", "📝")
        for idx, e in enumerate(entries[:5], 1):
            if isinstance(e, dict):
                log(f"  Entry #{idx}: Number={e.get('entry_number')} | Importer={e.get('importer_name')} | Port={e.get('port_of_entry')} | Duty=${e.get('total_duty_amount', 0)}")

    # 8. Final Test Summary
    print("\n==================================================================")
    log("🎉 Scenario 1 E2E Test Execution Finished!", "✅")
    print("==================================================================")

if __name__ == "__main__":
    run_test()

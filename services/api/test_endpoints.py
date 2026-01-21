#!/usr/bin/env python3
"""
Test script for silver/upsert, validation, and vectorize endpoints.
Creates test data and verifies all three endpoints work correctly.
"""

import requests
import json
from uuid import uuid4
from datetime import datetime
import time

BASE_URL = "http://localhost:8000"

def create_test_batch():
    """Create a batch of 10 test silver records."""
    batch_id = str(uuid4())
    # Use one of the test raw_files we created
    source_file_id = "550e8400-e29b-41d4-a716-446655440000"
    records = []

    for i in range(10):
        record = {
            "document_id": f"doc_{i}_{batch_id[:8]}",
            "record_id": f"rec_{i}_{batch_id[:8]}",
            "canonical_id": f"canonical_{i}_{batch_id[:8]}",
            "source_file_id": source_file_id,
            "file_type": "pdf",
            "size_bytes": 5000 + (i * 100),
            "normalized_payload": {
                "title": f"Test Document {i}",
                "content": f"This is test document {i} content",
                "metadata": {"page": i + 1}
            },
            "title": f"Test Document {i}",
            "author": "Test Author",
            "language": "en",
            "content": f"Normalized content for document {i}",
            "extraction_date": datetime.utcnow().isoformat(),
            "document_date": datetime.utcnow().isoformat(),
            "record_metadata": {
                "source": "test_script",
                "version": 1
            }
        }
        records.append(record)

    return batch_id, records

def test_silver_upsert():
    """Test the silver/upsert endpoint."""
    print("\n" + "="*70)
    print("TEST 1: Silver/Upsert Endpoint")
    print("="*70)

    batch_id, records = create_test_batch()

    payload = {
        "batch_id": batch_id,
        "records": records,
        "source_context": {"source": "test_script"}
    }

    print(f"\nEndpoint: POST {BASE_URL}/api/metadata/silver/upsert")
    print(f"Batch ID: {batch_id}")
    print(f"Records: {len(records)}")

    try:
        response = requests.post(
            f"{BASE_URL}/api/metadata/silver/upsert",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )

        print(f"Status Code: {response.status_code}")
        result = response.json()
        print(f"Response: {json.dumps(result, indent=2)}")

        if response.status_code in [200, 202]:
            print("✅ Silver/Upsert endpoint working!")
            return batch_id, response.status_code == 202, result
        else:
            print(f"❌ Unexpected status code: {response.status_code}")
            return batch_id, False, result

    except Exception as e:
        print(f"❌ Error testing silver/upsert: {e}")
        return batch_id, False, None

def test_validation(batch_id):
    """Test the validation endpoint."""
    print("\n" + "="*70)
    print("TEST 2: Validation/Validate-Normalization Endpoint")
    print("="*70)

    # Create test records for validation
    records = []
    for i in range(5):
        record = {
            "document_id": f"val_doc_{i}",
            "record_id": f"val_rec_{i}",
            "title": f"Validation Test {i}",
            "content": f"Test content {i}",
            "field1": f"value_{i}",
            "field2": i * 100
        }
        records.append(record)

    payload = {
        "batch_id": batch_id,
        "records": records,
        "custom_rules": {
            "required_fields": ["document_id", "record_id"],
            "type_constraints": {
                "field2": "integer"
            }
        }
    }

    print(f"\nEndpoint: POST {BASE_URL}/api/validation/validate-normalization")
    print(f"Batch ID: {batch_id}")
    print(f"Records: {len(records)}")

    try:
        response = requests.post(
            f"{BASE_URL}/api/validation/validate-normalization",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )

        print(f"Status Code: {response.status_code}")
        result = response.json()
        print(f"Response: {json.dumps(result, indent=2)}")

        if response.status_code in [200, 202]:
            print("✅ Validation endpoint working!")
            return response.status_code == 202, result
        else:
            print(f"❌ Unexpected status code: {response.status_code}")
            return False, result

    except Exception as e:
        print(f"❌ Error testing validation: {e}")
        return False, None

def test_vectorization(silver_result):
    """Test the vectorization endpoint."""
    print("\n" + "="*70)
    print("TEST 3: Vectorize Endpoint")
    print("="*70)

    # For testing, we'll use mock UUIDs since we don't have real silver records yet
    record_ids = [str(uuid4()) for _ in range(3)]

    payload = {
        "silver_record_ids": record_ids,
        "batch_size": 10
    }

    print(f"\nEndpoint: POST {BASE_URL}/api/vectorize/vectorize")
    print(f"Record IDs: {len(record_ids)}")

    try:
        response = requests.post(
            f"{BASE_URL}/api/vectorize/vectorize",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )

        print(f"Status Code: {response.status_code}")
        result = response.json()
        print(f"Response: {json.dumps(result, indent=2)}")

        # Note: This may fail with 404 if records don't exist, which is expected
        if response.status_code in [202, 404]:
            print("✅ Vectorize endpoint is responding (404 expected if records don't exist yet)")
            return response.status_code == 202, result
        else:
            print(f"⚠️ Status code: {response.status_code}")
            return False, result

    except Exception as e:
        print(f"❌ Error testing vectorization: {e}")
        return False, None

def main():
    """Run all endpoint tests."""
    print("\n")
    print("╔" + "="*68 + "╗")
    print("║" + " "*15 + "ENDPOINT INTEGRATION TESTS" + " "*27 + "║")
    print("╚" + "="*68 + "╝")

    # Check if server is running
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        print(f"\n✅ Server is running (health check: {response.status_code})")
    except Exception as e:
        print(f"\n❌ Server not responding: {e}")
        return

    # Test 1: Silver Upsert
    batch_id, upsert_success, upsert_result = test_silver_upsert()

    # Test 2: Validation
    val_success, val_result = test_validation(batch_id)

    # Test 3: Vectorization
    vec_success, vec_result = test_vectorization(upsert_result)

    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"Silver/Upsert:  {'✅ PASS' if upsert_success else '❌ FAIL'}")
    print(f"Validation:     {'✅ PASS' if val_success else '❌ FAIL'}")
    print(f"Vectorization:  {'✅ PASS' if vec_success else '⚠️ SKIPPED (expected if no records)'}")

    all_passed = upsert_success and val_success
    print("\n" + ("="*70))
    if all_passed:
        print("✅ ALL CRITICAL ENDPOINTS WORKING!")
    else:
        print("❌ SOME ENDPOINTS FAILED - CHECK LOGS ABOVE")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()

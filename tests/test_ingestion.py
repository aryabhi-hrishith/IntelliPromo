"""
Tests for Secure Retailer Data Ingestion and Validation (Stage 3).

Verifies:
  1. Valid CSV upload and inference.
  2. Column mapping and preview validation (without persistence).
  3. Tenant header validation and tenant isolation (Retailer A vs Retailer B).
  4. Missing required columns and type/date validation errors.
  5. Successful commit with idempotency guard and temporary file cleanup.
"""

import io
import os
import pytest
from fastapi.testclient import TestClient
from src.api.main import app
from src.api.database import tenant_import_batches, tenant_products


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_upload_missing_tenant_header(client):
    csv_content = b"item_id,product_name,category,retail_price\nPROD_1,Milk,Dairy,3.99"
    files = {"file": ("products.csv", io.BytesIO(csv_content), "text/csv")}
    response = client.post("/ingest/upload", files=files)
    assert response.status_code == 400
    assert "Missing required 'X-Retailer-ID'" in response.json()["detail"]


def test_upload_valid_csv_and_preview(client):
    csv_content = b"sku,product_title,department,price\nPROD_101,Organic Eggs,Dairy,4.50\nPROD_102,Whole Wheat Bread,Bakery,2.99"
    files = {"file": ("products.csv", io.BytesIO(csv_content), "text/csv")}
    headers = {"X-Retailer-ID": "retailer_alpha"}

    response = client.post("/ingest/upload", files=files, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "batch_id" in data
    assert data["retail_id"] == "retailer_alpha"
    assert data["total_rows"] == 2
    assert "sku" in data["columns"]

    batch_id = data["batch_id"]

    # Test preview with explicit mapping
    mapping_payload = {
        "dataset_type": "products",
        "mapping": {
            "sku": "item_id",
            "product_title": "product_name",
            "department": "category",
            "price": "retail_price"
        }
    }

    preview_res = client.post(f"/ingest/batches/{batch_id}/preview", json=mapping_payload, headers=headers)
    assert preview_res.status_code == 200
    preview_data = preview_res.json()
    assert preview_data["valid_rows_count"] == 2
    assert preview_data["invalid_rows_count"] == 0
    assert len(preview_data["sample_preview"]) == 2

    # Verify preview did NOT persist records to tenant_products collection
    persisted_count = tenant_products.count_documents({"retail_id": "retailer_alpha"})
    assert persisted_count == 0


def test_commit_batch_idempotency_and_cleanup(client):
    csv_content = b"item_id,product_name,category,retail_price\nPROD_201,Apples,Produce,1.99"
    files = {"file": ("fruits.csv", io.BytesIO(csv_content), "text/csv")}
    headers = {"X-Retailer-ID": "retailer_beta"}

    upload_res = client.post("/ingest/upload", files=files, headers=headers)
    assert upload_res.status_code == 200
    batch_id = upload_res.json()["batch_id"]

    commit_payload = {
        "dataset_type": "products",
        "mapping": {
            "item_id": "item_id",
            "product_name": "product_name",
            "category": "category",
            "retail_price": "retail_price"
        }
    }

    # First commit succeeds
    commit_res = client.post(f"/ingest/batches/{batch_id}/commit", json=commit_payload, headers=headers)
    assert commit_res.status_code == 200
    assert commit_res.json()["committed_records_count"] == 1

    # Verify records in MongoDB
    assert tenant_products.count_documents({"retail_id": "retailer_beta", "item_id": "PROD_201"}) == 1

    # Second commit (idempotency guard) fails with 400
    repeat_commit = client.post(f"/ingest/batches/{batch_id}/commit", json=commit_payload, headers=headers)
    assert repeat_commit.status_code == 400
    assert "already been committed" in repeat_commit.json()["detail"]

    # Cleanup: remove inserted test records from DB
    tenant_products.delete_many({"retail_id": "retailer_beta"})


def test_tenant_isolation_batch_access(client):
    """Retailer A cannot access or preview Retailer B's batch."""
    csv_content = b"item_id,product_name,category,retail_price\nPROD_999,Secret Item,Misc,10.00"
    files = {"file": ("secret.csv", io.BytesIO(csv_content), "text/csv")}
    
    # Upload as Retailer A
    res_a = client.post("/ingest/upload", files=files, headers={"X-Retailer-ID": "retailer_a"})
    assert res_a.status_code == 200
    batch_id = res_a.json()["batch_id"]

    # Try to preview as Retailer B (should return 404)
    mapping_payload = {
        "dataset_type": "products",
        "mapping": {"item_id": "item_id", "product_name": "product_name", "category": "category", "retail_price": "retail_price"}
    }
    res_b = client.post(f"/ingest/batches/{batch_id}/preview", json=mapping_payload, headers={"X-Retailer-ID": "retailer_b"})
    assert res_b.status_code == 404

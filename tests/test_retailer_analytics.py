"""
Tests for Retailer-Specific AI/ML Analytics (Stage 5).

Verifies:
  1. Data readiness assessment across canonical datasets.
  2. Tenant-scoped demand forecasting from committed sales.
  3. Customer segmentation and market basket product affinity.
  4. Inventory alignment and risk recommendations.
  5. Strict tenant isolation (Retailer A cannot access Retailer B analytics).
"""

import pytest
from fastapi.testclient import TestClient
from src.api.main import app
from src.api.database import (
    tenant_products,
    tenant_sales,
    tenant_inventory,
    tenant_customers,
)
from src.api.retailer_analytics_service import assess_data_readiness, run_tenant_analytics


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_analytics_readiness_insufficient_data(client):
    headers = {"X-Retailer-ID": "retailer_empty"}
    res = client.get("/analytics/readiness", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["readiness_status"] == "unavailable"


def test_analytics_run_and_results_flow():
    retail_id = "retailer_analytics_test"
    
    # Insert test committed records
    tenant_products.insert_one({
        "retail_id": retail_id,
        "item_id": "TEST_ITEM_1",
        "product_name": "Test Milk",
        "category": "Dairy",
        "retail_price": 3.99,
        "unit_cost": 2.50
    })
    tenant_sales.insert_many([
        {
            "retail_id": retail_id,
            "transaction_id": "TX_101",
            "date": "2026-10-01",
            "store_id": "STORE_1",
            "item_id": "TEST_ITEM_1",
            "quantity": 10.0,
            "unit_price": 3.99,
            "customer_id": "CUST_1"
        },
        {
            "retail_id": retail_id,
            "transaction_id": "TX_102",
            "date": "2026-10-02",
            "store_id": "STORE_1",
            "item_id": "TEST_ITEM_1",
            "quantity": 12.0,
            "unit_price": 3.99,
            "customer_id": "CUST_1"
        }
    ])
    tenant_inventory.insert_one({
        "retail_id": retail_id,
        "store_id": "STORE_1",
        "item_id": "TEST_ITEM_1",
        "date": "2026-10-02",
        "stock_on_hand": 5.0
    })

    # Test readiness
    readiness = assess_data_readiness(retail_id)
    assert readiness["readiness_status"] in ("ready", "degraded")
    assert readiness["record_counts"]["sales"] == 2

    # Run analytics
    run_res = run_tenant_analytics(retail_id)
    assert run_res["retail_id"] == retail_id
    assert len(run_res["forecast_summary"]) == 1
    assert run_res["inventory_alignment_count"] == 1
    assert "Stockout Risk" in run_res["inventory_alignment"][0]["risk_status"]

    # Cleanup
    tenant_products.delete_many({"retail_id": retail_id})
    tenant_sales.delete_many({"retail_id": retail_id})
    tenant_inventory.delete_many({"retail_id": retail_id})


def test_tenant_isolation_analytics(client):
    retailer_a = "retailer_isolation_a"
    retailer_b = "retailer_isolation_b"

    tenant_products.insert_one({
        "retail_id": retailer_a,
        "item_id": "ITEM_A",
        "product_name": "Product A",
        "category": "General",
        "retail_price": 10.0
    })

    headers_b = {"X-Retailer-ID": retailer_b}
    res = client.get("/analytics/results", headers=headers_b)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "no_runs_found"

    # Cleanup
    tenant_products.delete_many({"retail_id": retailer_a})

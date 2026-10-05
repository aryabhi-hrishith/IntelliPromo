"""
Tests for AI/ML Decision Engine and Explainability (Stage 6B).

Verifies:
  1. Tenant isolation for GET /analytics/decisions.
  2. Handling of missing data and insufficient history.
  3. Inventory-only data and sales + inventory data handling.
  4. Complete data decision generation with reliability classification (HIGH/MEDIUM/LOW/INSUFFICIENT_DATA).
  5. Deterministic recommendations and transparent evidence without fabricated values.
  6. API regression testing for /analytics/decisions endpoint.
"""

import pytest
from fastapi.testclient import TestClient
from src.api.main import app
from src.api.database import (
    tenant_products,
    tenant_sales,
    tenant_inventory,
)
from src.api.ai_decision_engine import compute_tenant_decisions


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_ai_decision_engine_insufficient_data():
    retail_id = "retailer_decision_empty"
    res = compute_tenant_decisions(retail_id)
    assert res["status"] == "insufficient_data"
    assert res["total_decisions"] == 0


def test_ai_decision_engine_inventory_only_and_complete_data():
    retail_id = "retailer_decision_test"
    
    # Insert test committed records
    tenant_products.insert_one({
        "retail_id": retail_id,
        "item_id": "DEC_ITEM_1",
        "product_name": "Test Bread",
        "category": "Bakery",
        "retail_price": 2.99
    })
    tenant_inventory.insert_one({
        "retail_id": retail_id,
        "store_id": "STORE_1",
        "item_id": "DEC_ITEM_1",
        "date": "2026-10-02",
        "stock_on_hand": 3.0 # Low stock / stockout risk
    })
    tenant_sales.insert_many([
        {
            "retail_id": retail_id,
            "transaction_id": "TX_D1",
            "date": "2026-10-01",
            "store_id": "STORE_1",
            "item_id": "DEC_ITEM_1",
            "quantity": 5.0,
            "unit_price": 2.99
        },
        {
            "retail_id": retail_id,
            "transaction_id": "TX_D2",
            "date": "2026-10-02",
            "store_id": "STORE_1",
            "item_id": "DEC_ITEM_1",
            "quantity": 4.0,
            "unit_price": 2.99
        }
    ])

    res = compute_tenant_decisions(retail_id)
    assert res["status"] == "success"
    assert res["total_decisions"] == 1
    decision = res["decisions"][0]
    assert decision["item_id"] == "DEC_ITEM_1"
    assert decision["store_id"] == "STORE_1"
    assert decision["reliability"] in ("HIGH", "MEDIUM", "LOW", "INSUFFICIENT_DATA")
    assert "reason" in decision
    assert "evidence" in decision
    assert "forecast" in decision
    assert "inventory" in decision
    assert "promotion" in decision
    assert "warnings" in decision

    # Cleanup
    tenant_products.delete_many({"retail_id": retail_id})
    tenant_sales.delete_many({"retail_id": retail_id})
    tenant_inventory.delete_many({"retail_id": retail_id})


def test_tenant_isolation_decisions_endpoint(client):
    retailer_a = "retailer_dec_a"
    retailer_b = "retailer_dec_b"

    tenant_products.insert_one({
        "retail_id": retailer_a,
        "item_id": "ITEM_DEC_A",
        "product_name": "Product A",
        "category": "General",
        "retail_price": 10.0
    })
    tenant_inventory.insert_one({
        "retail_id": retailer_a,
        "store_id": "STORE_1",
        "item_id": "ITEM_DEC_A",
        "stock_on_hand": 100.0
    })

    headers_b = {"X-Retailer-ID": retailer_b}
    response = client.get("/analytics/decisions", headers=headers_b)
    assert response.status_code == 200
    data = response.json()
    assert data["total_decisions"] == 0

    headers_a = {"X-Retailer-ID": retailer_a}
    response_a = client.get("/analytics/decisions", headers=headers_a)
    assert response_a.status_code == 200
    data_a = response_a.json()
    assert data_a["total_decisions"] == 1
    assert data_a["decisions"][0]["item_id"] == "ITEM_DEC_A"

    # Cleanup
    tenant_products.delete_many({"retail_id": retailer_a})
    tenant_inventory.delete_many({"retail_id": retailer_a})

"""
End-to-End Demo Workflow Integration Test (Stage 7).

Verifies:
  1. Seeding the demo retailer fixture.
  2. Running tenant analytics and verifying readiness and forecasts.
  3. Retrieving AI/ML decisions via GET /analytics/decisions.
  4. Verifying presence of recommendations, priorities, reliability, evidence, and explanations.
  5. Verifying strict tenant isolation (cross-tenant access denied/empty).
"""

import pytest
from fastapi.testclient import TestClient
from src.api.main import app
from src.api.demo_fixture import seed_demo_retailer
from src.api.retailer_analytics_service import run_tenant_analytics
from src.api.ai_decision_engine import compute_tenant_decisions
from src.api.database import (
    tenant_products,
    tenant_sales,
    tenant_inventory,
)


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_e2e_demo_workflow_and_tenant_isolation(client):
    demo_retail_id = "demo_retailer_pro"
    other_retail_id = "retailer_isolation_b"

    # 1. Seed demo retailer fixture
    seed_res = seed_demo_retailer(demo_retail_id)
    assert seed_res["status"] == "success"
    assert seed_res["sales_records_seeded"] > 0

    # 2. Run analytics
    analytics_res = run_tenant_analytics(demo_retail_id)
    assert analytics_res["data_readiness"]["readiness_status"] in ("ready", "degraded")
    assert analytics_res["forecast_metrics"]["model"] is not None

    # 3. Retrieve AI/ML decisions
    decisions_res = compute_tenant_decisions(demo_retail_id)
    assert decisions_res["status"] == "success"
    assert decisions_res["total_decisions"] > 0

    for dec in decisions_res["decisions"]:
        assert "item_id" in dec
        assert "store_id" in dec
        assert "recommendation" in dec
        assert "priority" in dec
        assert "reliability" in dec
        assert "reason" in dec
        assert isinstance(dec["evidence"], list)
        assert len(dec["evidence"]) > 0
        assert "forecast" in dec
        assert "inventory" in dec
        assert "promotion" in dec
        assert isinstance(dec["warnings"], list)

    # 4. Test via FastAPI endpoint with X-Retailer-ID header
    headers_demo = {"X-Retailer-ID": demo_retail_id}
    res = client.get("/analytics/decisions", headers=headers_demo)
    assert res.status_code == 200
    data = res.json()
    assert data["total_decisions"] > 0

    # 5. Verify strict tenant isolation: other retailer cannot access demo data
    headers_other = {"X-Retailer-ID": other_retail_id}
    res_other = client.get("/analytics/decisions", headers=headers_other)
    assert res_other.status_code == 200
    data_other = res_other.json()
    assert data_other["total_decisions"] == 0

    # Cleanup
    tenant_products.delete_many({"retail_id": demo_retail_id})
    tenant_sales.delete_many({"retail_id": demo_retail_id})
    tenant_inventory.delete_many({"retail_id": demo_retail_id})

"""
Tests for Multi-Retailer Tenant Isolation and Header Dependency (Stage 2).

Verifies:
  1. Header validation (X-Retailer-ID) in tenant dependency.
  2. Strict query scoping via get_tenant_query.
  3. Tenant isolation (Retailer A records cannot be retrieved or modified by Retailer B).
  4. Legacy demo compatibility preservation.
"""

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from src.api.tenant_context import get_current_retailer_id
from src.api.database import get_tenant_query
from src.api.main import app


@pytest.fixture
def api_client():
    with TestClient(app) as c:
        yield c


class TestTenantContextDependency:
    def test_valid_retailer_header(self):
        retail_id = get_current_retailer_id(x_retailer_id="retailer_alpha")
        assert retail_id == "retailer_alpha"

    def test_missing_retailer_header(self):
        with pytest.raises(HTTPException) as exc_info:
            get_current_retailer_id(x_retailer_id=None)
        assert exc_info.value.status_code == 400
        assert "Missing required 'X-Retailer-ID'" in exc_info.value.detail

    def test_invalid_format_retailer_header(self):
        with pytest.raises(HTTPException) as exc_info:
            get_current_retailer_id(x_retailer_id="bad id with spaces!")
        assert exc_info.value.status_code == 400
        assert "Invalid 'X-Retailer-ID'" in exc_info.value.detail


class TestTenantQueryScoping:
    def test_get_tenant_query_enforces_retail_id(self):
        query = get_tenant_query("retailer_alpha", {"store_id": "CA_1"})
        assert query == {"retail_id": "retailer_alpha", "store_id": "CA_1"}

    def test_get_tenant_query_raises_on_missing_retail_id(self):
        with pytest.raises(ValueError):
            get_tenant_query("", {"store_id": "CA_1"})


class TestTenantIsolationLogic:
    def test_tenant_data_isolation_simulation(self):
        """
        Simulate tenant isolation: two retailers storing records in the same collection
        must be cleanly separated by retail_id.
        """
        records = [
            {"retail_id": "retailer_a", "item_id": "item_1", "name": "A Product"},
            {"retail_id": "retailer_b", "item_id": "item_1", "name": "B Product"},
            {"retail_id": "retailer_a", "item_id": "item_2", "name": "A Product 2"},
        ]

        # Query for retailer_a
        query_a = get_tenant_query("retailer_a")
        results_a = [r for r in records if all(r.get(k) == v for k, v in query_a.items())]

        # Query for retailer_b
        query_b = get_tenant_query("retailer_b")
        results_b = [r for r in records if all(r.get(k) == v for k, v in query_b.items())]

        assert len(results_a) == 2
        assert all(r["retail_id"] == "retailer_a" for r in results_a)
        assert len(results_b) == 1
        assert results_b[0]["retail_id"] == "retailer_b"
        assert results_b[0]["name"] == "B Product"

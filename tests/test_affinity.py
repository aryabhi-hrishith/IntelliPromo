"""
Tests for Product Affinity / Frequently Bought Together (Stage 2).

Covers:
  1. Affinity calculation logic (support, confidence, lift math).
  2. Threshold filtering (min_support, min_confidence).
  3. Empty input handling.
  4. FastAPI endpoint GET /recommendations/{item_id}/affinity behavior and data-source labeling.
"""

import sys
from pathlib import Path
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.features.compute_affinity import compute_affinity_rules
from src.api.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


class TestAffinityCalculations:
    def test_compute_affinity_basic_rules(self):
        baskets = [
            ["APPLE", "BANANA"],
            ["APPLE", "BANANA", "MILK"],
            ["APPLE", "MILK"],
            ["BANANA", "MILK"]
        ]
        df = compute_affinity_rules(baskets, min_support=0.1, min_confidence=0.1)
        assert not df.empty
        apple_banana = df[((df["item_a"] == "APPLE") & (df["item_b"] == "BANANA")) | 
                          ((df["item_a"] == "BANANA") & (df["item_b"] == "APPLE"))]
        assert not apple_banana.empty
        assert float(apple_banana.iloc[0]["support"]) == 0.5

    def test_compute_affinity_empty_input(self):
        df = compute_affinity_rules([], min_support=0.1, min_confidence=0.1)
        assert df.empty

    def test_threshold_filtering(self):
        baskets = [
            ["A", "B"],
            ["A", "C"]
        ]
        df = compute_affinity_rules(baskets, min_support=0.6, min_confidence=0.1)
        assert df.empty


class TestAffinityApi:
    @patch("src.api.main.product_affinity")
    def test_get_affinity_endpoint_success(self, mock_affinity, client):
        mock_affinity.find.return_value.sort.return_value.limit.return_value = [
            {
                "item_a": "FOODS_1_001",
                "item_b": "FOODS_1_002",
                "co_occurrence_count": 10,
                "support": 0.05,
                "confidence": 0.5,
                "lift": 2.5,
                "data_source": "SYNTHETIC_DEMO_BASKET_AFFINITY"
            }
        ]

        response = client.get("/recommendations/FOODS_1_001/affinity")
        assert response.status_code == 200
        data = response.json()
        assert data["item_id"] == "FOODS_1_001"
        assert data["data_source"] == "SYNTHETIC_DEMO_BASKET_AFFINITY"
        assert len(data["affinity_items"]) == 1
        assert data["affinity_items"][0]["related_item_id"] == "FOODS_1_002"
        assert data["affinity_items"][0]["lift"] == 2.5
        assert data["affinity_items"][0]["data_source"] == "SYNTHETIC_DEMO_BASKET_AFFINITY"

    @patch("src.api.main.product_affinity")
    def test_get_affinity_endpoint_empty(self, mock_affinity, client):
        mock_affinity.find.return_value.sort.return_value.limit.return_value = []

        response = client.get("/recommendations/UNKNOWN_ITEM/affinity")
        assert response.status_code == 200
        data = response.json()
        assert data["affinity_items"] == []
        assert data["data_source"] == "SYNTHETIC_DEMO_BASKET_AFFINITY"

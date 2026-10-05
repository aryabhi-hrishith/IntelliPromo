"""
Tests for Customer Segmentation and Personalized Promotions (Stage 3).

Covers:
  1. Feature computation & segment assignment logic.
  2. Edge cases (empty data).
  3. FastAPI endpoints GET /segments and GET /segments/promotions behavior and data-source labeling.
"""

import sys
from pathlib import Path
from unittest.mock import patch
import pandas as pd
import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.features.compute_segmentation import compute_customer_features, assign_segments
from src.api.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


class TestSegmentationLogic:
    def test_assign_segments_rules(self):
        data = {
            "customer_id": [1, 2, 3, 4],
            "total_spend": [100.0, 5000.0, 50.0, 200.0],
            "purchase_frequency": [2, 5, 25, 1],
            "avg_basket_value": [50.0, 1000.0, 2.0, 200.0],
            "avg_discount_pct": [5.0, 10.0, 35.0, 2.0],
        }
        df = pd.DataFrame(data)
        segmented = assign_segments(df)
        assert "segment" in segmented.columns
        assert len(segmented) == 4
        assert segmented.loc[segmented["customer_id"] == 2, "segment"].values[0] == "High-Value Shopper"
        assert segmented.loc[segmented["customer_id"] == 3, "segment"].values[0] == "Frequent Shopper"

    def test_assign_segments_empty(self):
        df = pd.DataFrame(columns=["customer_id", "total_spend", "purchase_frequency", "avg_basket_value", "avg_discount_pct"])
        segmented = assign_segments(df)
        assert segmented.empty


class TestSegmentationApi:
    @patch("src.api.main.customer_segments")
    def test_get_segments_endpoint(self, mock_seg, client):
        mock_seg.find.return_value.sort.return_value = [
            {
                "segment": "High-Value Shopper",
                "customer_count": 125,
                "avg_spend": 1250.50,
                "data_source": "SYNTHETIC_DEMO_DATA"
            }
        ]

        response = client.get("/segments")
        assert response.status_code == 200
        data = response.json()
        assert data["data_source"] == "SYNTHETIC_DEMO_DATA"
        assert len(data["segments"]) == 1
        assert data["segments"][0]["segment"] == "High-Value Shopper"

    @patch("src.api.main.segment_promotions")
    def test_get_segment_promotions_endpoint(self, mock_promo, client):
        mock_promo.find.return_value = [
            {
                "segment": "High-Value Shopper",
                "campaign_title": "Premium Rewards",
                "suggested_discount_pct": 10,
                "data_source": "SYNTHETIC_DEMO_DATA"
            }
        ]

        response = client.get("/segments/promotions")
        assert response.status_code == 200
        data = response.json()
        assert data["data_source"] == "SYNTHETIC_DEMO_DATA"
        assert len(data["promotions"]) == 1
        assert data["promotions"][0]["campaign_title"] == "Premium Rewards"

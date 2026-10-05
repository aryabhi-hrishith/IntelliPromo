"""
End-to-End System Audit Tests (Step 27).

Covers:
  A. Environment & database connectivity (MongoDB, counts, .gitignore, secret leakage checks)
  B. Data & ML evaluation reproduction (Random Forest MAE/RMSE vs Naive baseline from saved predictions)
  C. Recommendation engine logic (6 representative categories, discount selection, margin math, immutability)
  D. FastAPI endpoints (status, products, recommendations, rule explanation, AI explanation, pagination, filters, 400/404, no NaN/Infinity)
  E. Error responses (missing config, timeout, malformed output, rate limit)
"""

import json
import math
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.api.main import app
from src.api.database import client as mongo_client, DB_NAME, products, recommendations
from src.api.ai_explanation_service import (
    generate_ai_explanation,
    NOT_CONFIGURED,
    TIMEOUT_ERROR,
    MALFORMED_OUTPUT,
    PROVIDER_ERROR,
)


@pytest.fixture(scope="module")
def api_client():
    with TestClient(app) as c:
        yield c


# ===========================================================================
# A. Environment and Database
# ===========================================================================

class TestEnvironmentAndDatabase:
    def test_mongodb_connection_and_correct_database(self):
        """Verify MongoDB is reachable and uses the correct database name."""
        server_info = mongo_client.server_info()
        assert server_info is not None, "MongoDB server_info is None"
        assert DB_NAME == "retail_promotion_planner"

    def test_collections_contain_expected_data(self):
        """Verify products and recommendations collections are populated."""
        prod_count = products.estimated_document_count()
        rec_count = recommendations.estimated_document_count()
        assert prod_count == 30490, f"Expected 30490 products, got {prod_count}"
        assert rec_count == 30490, f"Expected 30490 recommendations, got {rec_count}"

    def test_gitignore_ignores_env(self):
        """Verify .env is explicitly excluded in .gitignore."""
        gitignore_path = PROJECT_ROOT / ".gitignore"
        assert gitignore_path.exists()
        content = gitignore_path.read_text(encoding="utf-8")
        patterns = [line.strip() for line in content.splitlines()]
        assert ".env" in patterns, ".env not found in .gitignore lines"

    def test_env_example_contains_no_real_secrets(self):
        """Verify .env.example contains no real API keys."""
        example_path = PROJECT_ROOT / ".env.example"
        assert example_path.exists()
        content = example_path.read_text(encoding="utf-8")
        assert "AIza" not in content, "Real Google API key pattern found in .env.example!"
        assert "YOUR_KEY_HERE" in content


# ===========================================================================
# B. Data and Machine Learning Evaluation
# ===========================================================================

class TestDataAndMlEvaluation:
    def test_reproduce_rf_and_naive_evaluation_metrics(self):
        """
        Verify the reported Random Forest MAE/RMSE and naive baseline MAE/RMSE
        against the saved predictions artifact (data/processed/forecast_predictions.csv).
        """
        pred_path = PROJECT_ROOT / "data" / "processed" / "forecast_predictions.csv"
        assert pred_path.exists(), f"Predictions artifact not found at {pred_path}"

        df = pd.read_csv(pred_path)
        assert len(df) == 2520, f"Expected 2,520 test predictions, got {len(df)}"

        actual = df["actual_units"]
        naive = df["naive_pred"]
        rf = df["rf_pred"]

        naive_mae = float(np.mean(np.abs(actual - naive)))
        naive_rmse = float(np.sqrt(np.mean((actual - naive) ** 2)))
        rf_mae = float(np.mean(np.abs(actual - rf)))
        rf_rmse = float(np.sqrt(np.mean((actual - rf) ** 2)))

        # Verified against reports/forecast_model_metrics.txt:
        # Naive: MAE 5.6024, RMSE 8.9339
        # RF:    MAE 4.2107, RMSE 6.1291
        assert pytest.approx(5.6024, abs=0.0005) == naive_mae
        assert pytest.approx(8.9339, abs=0.0005) == naive_rmse
        assert pytest.approx(4.2107, abs=0.0005) == rf_mae
        assert pytest.approx(6.1291, abs=0.0005) == rf_rmse

        # RF is superior to naive baseline
        assert rf_mae < naive_mae
        assert rf_rmse < naive_rmse

    def test_forecast_model_metrics_file_consistency(self):
        """Verify the metrics reported in reports/forecast_model_metrics.txt match."""
        metrics_path = PROJECT_ROOT / "reports" / "forecast_model_metrics.txt"
        assert metrics_path.exists()
        text = metrics_path.read_text(encoding="utf-8")
        assert "5.6024" in text
        assert "8.9339" in text
        assert "4.2107" in text
        assert "6.1291" in text
        assert "24.8%" in text
        assert "31.4%" in text


# ===========================================================================
# C. Recommendation Engine Logic and Verification
# ===========================================================================

class TestRecommendationEngine:
    EXPECTED_CATEGORIES = [
        "Review excess inventory - consider promotion",
        "Review demand decline - consider promotion",
        "Review demand decline",
        "Review replenishment - avoid promotion",
        "Review low-demand item (no sales in window)",
        "No action - coverage within range",
    ]

    def test_all_expected_recommendation_categories_present(self):
        """Verify each category exists in MongoDB."""
        distinct_recs = set(recommendations.distinct("recommendation"))
        for cat in self.EXPECTED_CATEGORIES:
            assert cat in distinct_recs, f"Missing category: {cat}"

    def test_representative_excess_inventory_promo(self):
        """Verify excess inventory promo logic and margin math."""
        doc = recommendations.find_one({"recommendation": "Review excess inventory - consider promotion"})
        assert doc is not None
        assert doc["coverage_days"] >= 30.0
        assert doc["selected_candidate_discount_pct"] in (5, 10, 15)
        # Margin math check: (price - cost) / price >= 5%
        disc_price = doc["selected_discounted_price"]
        cost = doc["assumed_unit_cost"]
        disc_margin_pct = doc["selected_discounted_margin_pct"]
        calc_margin = ((disc_price - cost) / disc_price) * 100.0
        assert pytest.approx(disc_margin_pct, abs=0.05) == calc_margin
        assert disc_margin_pct >= 5.0

    def test_representative_replenishment_avoid_promo(self):
        """Verify replenishment review items have low coverage and 0% discount."""
        doc = recommendations.find_one({"recommendation": "Review replenishment - avoid promotion"})
        assert doc is not None
        assert doc["coverage_days"] < 7.0
        assert doc["selected_candidate_discount_pct"] == 0

    def test_representative_low_demand(self):
        """Verify low-demand items have 0 units/day demand and no discount."""
        doc = recommendations.find_one({"recommendation": "Review low-demand item (no sales in window)"})
        assert doc is not None
        assert doc["demand_used_units_per_day"] == 0.0
        assert doc["selected_candidate_discount_pct"] == 0

    def test_representative_no_action(self):
        """Verify no-action items have coverage between 7 and 30 days and 0% discount."""
        doc = recommendations.find_one({"recommendation": "No action - coverage within range"})
        assert doc is not None
        assert 7.0 <= doc["coverage_days"] < 30.0
        assert doc["selected_candidate_discount_pct"] == 0

    def test_recommendation_immutability_on_ai_explanation(self, api_client):
        """
        Verify that generating an AI explanation NEVER mutates the stored
        recommendation, discount, or price in MongoDB.
        """
        doc_before = recommendations.find_one({"store_id": "CA_1"})
        item_id = doc_before["item_id"]
        store_id = doc_before["store_id"]

        # Call AI explanation endpoint
        res = api_client.get(f"/recommendations/{item_id}/ai-explanation?store_id={store_id}")
        assert res.status_code == 200

        doc_after = recommendations.find_one({"item_id": item_id, "store_id": store_id})
        assert doc_before["recommendation"] == doc_after["recommendation"]
        assert doc_before["selected_candidate_discount_pct"] == doc_after["selected_candidate_discount_pct"]
        assert doc_before["latest_sell_price"] == doc_after["latest_sell_price"]


# ===========================================================================
# D. FastAPI Endpoints & JSON Serialization
# ===========================================================================

class TestFastApiEndpoints:
    def test_root_status_endpoint(self, api_client):
        res = api_client.get("/")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert data["database"] == "connected"
        assert data["collection_counts"]["products"] == 30490
        assert data["collection_counts"]["recommendations"] == 30490

    def test_products_pagination_and_store_filter(self, api_client):
        res = api_client.get("/products?limit=15&skip=10&store_id=CA_1")
        assert res.status_code == 200
        data = res.json()
        assert data["limit"] == 15
        assert data["skip"] == 10
        assert data["returned"] == 15
        assert data["total_matching"] == 3049  # 30490 / 10 stores
        for item in data["results"]:
            assert item["store_id"] == "CA_1"

    def test_products_item_endpoint(self, api_client):
        res = api_client.get("/products/FOODS_1_001?store_id=CA_1")
        assert res.status_code == 200
        data = res.json()
        assert data["item_id"] == "FOODS_1_001"
        assert len(data["results"]) == 1
        assert data["results"][0]["store_id"] == "CA_1"

    def test_products_nonexistent_item_404(self, api_client):
        res = api_client.get("/products/NONEXISTENT_ITEM_12345")
        assert res.status_code == 404

    def test_recommendations_pagination_and_store_filter(self, api_client):
        res = api_client.get("/recommendations?limit=10&store_id=TX_1")
        assert res.status_code == 200
        data = res.json()
        assert data["returned"] == 10
        assert data["total_matching"] == 3049
        for item in data["results"]:
            assert item["store_id"] == "TX_1"

    def test_recommendations_item_endpoint(self, api_client):
        res = api_client.get("/recommendations/FOODS_1_001?store_id=WI_1")
        assert res.status_code == 200
        data = res.json()
        assert data["item_id"] == "FOODS_1_001"
        assert len(data["results"]) == 1

    def test_recommendations_nonexistent_item_404(self, api_client):
        res = api_client.get("/recommendations/NONEXISTENT_ITEM_12345")
        assert res.status_code == 404

    def test_rule_explanation_valid(self, api_client):
        res = api_client.get("/recommendations/FOODS_1_001/explanation?store_id=CA_1")
        assert res.status_code == 200
        data = res.json()
        assert data["item_id"] == "FOODS_1_001"
        assert data["store_id"] == "CA_1"
        assert "recommendation" in data
        assert "supporting_factors" in data
        assert "data_limitations" in data
        assert any("rule-based" in lim.lower() for lim in data["data_limitations"])

    def test_rule_explanation_ambiguous_item_400(self, api_client):
        res = api_client.get("/recommendations/FOODS_1_001/explanation")
        assert res.status_code == 400
        assert "store_id" in res.json()["detail"].lower()

    def test_rule_explanation_nonexistent_item_404(self, api_client):
        res = api_client.get("/recommendations/DOES_NOT_EXIST/explanation?store_id=CA_1")
        assert res.status_code == 404

    def test_ai_explanation_ambiguous_item_400(self, api_client):
        res = api_client.get("/recommendations/FOODS_1_001/ai-explanation")
        assert res.status_code == 400
        assert "store_id" in res.json()["detail"].lower()

    def test_ai_explanation_nonexistent_item_404(self, api_client):
        res = api_client.get("/recommendations/DOES_NOT_EXIST/ai-explanation?store_id=CA_1")
        assert res.status_code == 404

    def test_no_nan_or_infinity_in_all_endpoints(self, api_client):
        """
        Verify that clean_document strips NaN and Infinity from JSON responses
        for items where demand or coverage is undefined.
        """
        # FOODS_1_003 in TX_3 has demand = 0, coverage = undefined
        res = api_client.get("/recommendations/FOODS_1_003?store_id=TX_3")
        assert res.status_code == 200
        raw_text = res.text
        assert "NaN" not in raw_text
        assert "Infinity" not in raw_text

        # Check explanation
        res_exp = api_client.get("/recommendations/FOODS_1_003/explanation?store_id=TX_3")
        assert res_exp.status_code == 200
        assert "NaN" not in res_exp.text
        assert "Infinity" not in res_exp.text


# ===========================================================================
# E. Error Handling and Resilience
# ===========================================================================

class TestErrorHandlingAndResilience:
    def test_missing_credentials_handling(self, api_client, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        res = api_client.get("/recommendations/FOODS_1_001/ai-explanation?store_id=CA_1")
        assert res.status_code == 200
        body = res.json()
        assert body["explanation_type"] == "error"
        assert body["error_type"] == NOT_CONFIGURED
        assert "GEMINI_API_KEY" in body["error_message"]

    def test_provider_timeout_handling(self, api_client, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "dummy-key")
        with patch("google.genai.Client") as mock_client_cls:
            fake_client = MagicMock()
            mock_client_cls.return_value = fake_client
            fake_client.models.generate_content.side_effect = Exception("Deadline exceeded: 504 timeout")

            res = api_client.get("/recommendations/FOODS_1_001/ai-explanation?store_id=CA_1")
            assert res.status_code == 200
            body = res.json()
            assert body["explanation_type"] == "error"
            assert body["error_type"] == TIMEOUT_ERROR

    def test_malformed_json_handling(self, api_client, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "dummy-key")
        with patch("google.genai.Client") as mock_client_cls:
            fake_client = MagicMock()
            mock_client_cls.return_value = fake_client
            fake_resp = MagicMock()
            fake_resp.text = "This is definitely not valid json"
            fake_client.models.generate_content.return_value = fake_resp

            res = api_client.get("/recommendations/FOODS_1_001/ai-explanation?store_id=CA_1")
            assert res.status_code == 200
            body = res.json()
            assert body["explanation_type"] == "error"
            assert body["error_type"] == MALFORMED_OUTPUT

    def test_rate_limit_handling(self, api_client, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "dummy-key")
        with patch("google.genai.Client") as mock_client_cls:
            fake_client = MagicMock()
            mock_client_cls.return_value = fake_client
            fake_client.models.generate_content.side_effect = Exception("429 resource_exhausted: quota exceeded")

            res = api_client.get("/recommendations/FOODS_1_001/ai-explanation?store_id=CA_1")
            assert res.status_code == 200
            body = res.json()
            assert body["explanation_type"] == "error"
            assert body["error_type"] == PROVIDER_ERROR

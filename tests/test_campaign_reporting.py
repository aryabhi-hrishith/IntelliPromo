"""
Tests for Campaign Effectiveness & Impact Reporting (Stage 4).

Covers:
  1. Campaign report calculations (decision counts, rates, discount distribution, categories, empty data).
  2. FastAPI GET /campaign-reports endpoint.
  3. FastAPI GET /campaign-reports/outcomes endpoint (including synthetic demo data labeling).
  4. FastAPI POST /campaign-reports/outcomes endpoint (input validation, persistence).
  5. Distinction between proposed/approved vs executed campaigns.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.api.main import app
from src.api.campaign_reporting_service import compute_campaign_report, get_campaign_outcomes_list, save_campaign_outcome


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


class TestCampaignReportingUnit:
    def test_compute_campaign_report_empty(self):
        """Verify behavior with zero recommendations."""
        with patch("src.api.campaign_reporting_service.recommendations") as mock_recs:
            mock_recs.find.return_value = []
            report = compute_campaign_report()
            assert report["total_recommendations"] == 0
            assert report["decision_counts"]["approved"] == 0
            assert report["decision_counts"]["rejected"] == 0
            assert report["decision_counts"]["pending"] == 0
            assert "Proposed or approved campaigns are distinct from executed campaigns" in report["execution_status_note"]

    def test_compute_campaign_report_with_data(self):
        """Verify campaign report summary calculations with mock recommendation data."""
        mock_docs = [
            {"item_id": "I1", "store_id": "CA_1", "decision_status": "approved", "selected_candidate_discount_pct": 10, "recommendation": "Review excess inventory - consider promotion"},
            {"item_id": "I2", "store_id": "CA_1", "decision_status": "rejected", "selected_candidate_discount_pct": 5, "recommendation": "Review demand decline - consider promotion"},
            {"item_id": "I3", "store_id": "CA_2", "decision_status": "pending", "selected_candidate_discount_pct": 0, "recommendation": "No action - coverage within range"},
        ]
        with patch("src.api.campaign_reporting_service.recommendations") as mock_recs:
            mock_recs.find.return_value = mock_docs
            report = compute_campaign_report()
            assert report["total_recommendations"] == 3
            assert report["decision_counts"]["approved"] == 1
            assert report["decision_counts"]["rejected"] == 1
            assert report["decision_counts"]["pending"] == 1
            assert report["decision_rates_pct"]["approved"] == 33.33
            assert report["discount_distribution"]["10% Off"] == 1
            assert report["discount_distribution"]["0% (No Promo)"] == 1
            assert report["store_summaries"]["CA_1"] == 2
            assert report["store_summaries"]["CA_2"] == 1

    @patch("src.api.campaign_reporting_service.campaign_outcomes")
    def test_get_campaign_outcomes_synthetic_fallback(self, mock_outcomes):
        """Verify fallback to synthetic demo data labeled 'SYNTHETIC DEMO DATA' when collection is empty."""
        mock_outcomes.find.return_value.sort.return_value = []
        result = get_campaign_outcomes_list("CA_1")
        assert result["total_outcomes"] > 0
        for out in result["outcomes"]:
            assert out["data_source"] == "SYNTHETIC DEMO DATA"
            assert "actual_redemptions" in out
            assert "actual_sales_lift_pct" in out

    @patch("src.api.campaign_reporting_service.campaign_outcomes")
    def test_save_campaign_outcome(self, mock_outcomes):
        """Verify saving a campaign outcome with validation."""
        payload = {
            "item_id": "FOODS_1_001",
            "store_id": "CA_1",
            "actual_redemptions": 150,
            "actual_sales_lift_pct": 20.0,
            "actual_revenue_gain": 1500.00,
            "measured_period": "2026-10-04",
            "data_source": "REAL_RETAILER_DATA"
        }
        mock_outcomes.find_one.return_value = payload
        saved = save_campaign_outcome(payload)
        assert saved["item_id"] == "FOODS_1_001"
        assert saved["actual_redemptions"] == 150
        assert saved["data_source"] == "REAL_RETAILER_DATA"
        mock_outcomes.insert_one.assert_called_once()


class TestCampaignReportingEndpoints:
    @patch("src.api.main.compute_campaign_report")
    def test_get_campaign_reports_endpoint(self, mock_compute, client):
        mock_compute.return_value = {
            "total_recommendations": 100,
            "decision_counts": {"approved": 40, "rejected": 10, "pending": 50},
            "decision_rates_pct": {"approved": 40.0, "rejected": 10.0, "pending": 50.0}
        }
        response = client.get("/campaign-reports?store_id=CA_1")
        assert response.status_code == 200
        data = response.json()
        assert data["total_recommendations"] == 100
        assert data["decision_counts"]["approved"] == 40

    @patch("src.api.main.get_campaign_outcomes_list")
    def test_get_campaign_outcomes_endpoint(self, mock_get_outcomes, client):
        mock_get_outcomes.return_value = {
            "data_source": "SYNTHETIC DEMO DATA",
            "total_outcomes": 1,
            "outcomes": [{"item_id": "FOODS_1_001", "store_id": "CA_1", "actual_redemptions": 50, "actual_sales_lift_pct": 10.0, "actual_revenue_gain": 500.0, "measured_period": "Test", "data_source": "SYNTHETIC DEMO DATA"}]
        }
        response = client.get("/campaign-reports/outcomes")
        assert response.status_code == 200
        data = response.json()
        assert data["total_outcomes"] == 1
        assert data["outcomes"][0]["data_source"] == "SYNTHETIC DEMO DATA"

    @patch("src.api.main.save_campaign_outcome")
    def test_post_campaign_outcome_endpoint_valid(self, mock_save, client):
        mock_save.return_value = {
            "item_id": "FOODS_1_001",
            "store_id": "CA_1",
            "actual_redemptions": 75,
            "actual_sales_lift_pct": 15.0,
            "actual_revenue_gain": 750.0,
            "measured_period": "Test Period",
            "data_source": "REAL_RETAILER_DATA"
        }
        response = client.post(
            "/campaign-reports/outcomes",
            json={
                "item_id": "FOODS_1_001",
                "store_id": "CA_1",
                "actual_redemptions": 75,
                "actual_sales_lift_pct": 15.0,
                "actual_revenue_gain": 750.0,
                "measured_period": "Test Period",
                "data_source": "REAL_RETAILER_DATA"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["outcome"]["actual_redemptions"] == 75

    def test_post_campaign_outcome_endpoint_invalid(self, client):
        """Verify Pydantic validation rejects negative redemptions or missing required fields."""
        response = client.post(
            "/campaign-reports/outcomes",
            json={
                "item_id": "FOODS_1_001",
                "store_id": "CA_1",
                "actual_redemptions": -10,  # Invalid: must be >= 0
                "actual_sales_lift_pct": 10.0,
                "actual_revenue_gain": 100.0,
                "measured_period": "Test"
            }
        )
        assert response.status_code == 422

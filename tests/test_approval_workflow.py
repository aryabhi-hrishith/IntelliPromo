"""
Tests for the Campaign Recommendation Approval and Rejection Workflow (Stage 1).

Covers:
  1. Valid approval (POST /recommendations/{item_id}/decision)
  2. Valid rejection
  3. Optional notes support
  4. Missing recommendation (HTTP 404)
  5. Invalid decision action (HTTP 400)
  6. Item/store scoping and multi-store ambiguity (HTTP 400 when store_id missing for multi-store item)
  7. Decision-history persistence and changing a decision without losing prior history
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.api.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


class TestApprovalWorkflowUnit:
    @patch("src.api.main.decision_history")
    @patch("src.api.main.recommendations")
    def test_valid_approval_and_persistence(self, mock_recs, mock_history, client):
        mock_recs.find.return_value.sort.return_value.limit.return_value = [
            {"item_id": "FOODS_1_001", "store_id": "CA_1", "recommendation": "Promote"}
        ]
        mock_recs.find_one.return_value = {
            "item_id": "FOODS_1_001",
            "store_id": "CA_1",
            "decision_status": "approved",
            "decision_notes": "Looks good for weekend promo",
            "decided_at": "2026-10-03T00:00:00Z",
            "actor": "Local Demo Manager (Unauthenticated)"
        }
        mock_history.find.return_value.sort.return_value = [
            {
                "item_id": "FOODS_1_001",
                "store_id": "CA_1",
                "action": "approve",
                "decision_status": "approved",
                "notes": "Looks good for weekend promo",
                "decided_at": "2026-10-03T00:00:00Z",
                "actor": "Local Demo Manager (Unauthenticated)"
            }
        ]

        response = client.post(
            "/recommendations/FOODS_1_001/decision?store_id=CA_1",
            json={"action": "approve", "notes": "Looks good for weekend promo"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["decision_status"] == "approved"
        assert data["decision_notes"] == "Looks good for weekend promo"
        assert len(data["history"]) == 1
        mock_history.insert_one.assert_called_once()
        mock_recs.update_one.assert_called_once()

    @patch("src.api.main.decision_history")
    @patch("src.api.main.recommendations")
    def test_valid_rejection(self, mock_recs, mock_history, client):
        mock_recs.find.return_value.sort.return_value.limit.return_value = [
            {"item_id": "FOODS_1_001", "store_id": "CA_1", "recommendation": "Promote"}
        ]
        mock_recs.find_one.return_value = {
            "item_id": "FOODS_1_001",
            "store_id": "CA_1",
            "decision_status": "rejected",
            "decision_notes": "Margin too tight",
        }
        mock_history.find.return_value.sort.return_value = [
            {"action": "reject", "decision_status": "rejected", "notes": "Margin too tight"}
        ]

        response = client.post(
            "/recommendations/FOODS_1_001/decision?store_id=CA_1",
            json={"action": "reject", "notes": "Margin too tight"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["decision_status"] == "rejected"

    @patch("src.api.main.recommendations")
    def test_missing_recommendation_returns_404(self, mock_recs, client):
        mock_recs.find.return_value.sort.return_value.limit.return_value = []

        response = client.post(
            "/recommendations/NONEXISTENT_ITEM/decision?store_id=CA_1",
            json={"action": "approve"}
        )
        assert response.status_code == 404

    @patch("src.api.main.recommendations")
    def test_invalid_action_returns_400(self, mock_recs, client):
        response = client.post(
            "/recommendations/FOODS_1_001/decision?store_id=CA_1",
            json={"action": "maybe"}
        )
        assert response.status_code == 400
        assert "Invalid action" in response.json()["detail"]

    @patch("src.api.main.recommendations")
    def test_multi_store_ambiguity_returns_400(self, mock_recs, client):
        mock_recs.find.return_value.sort.return_value.limit.return_value = [
            {"item_id": "FOODS_1_001", "store_id": "CA_1"},
            {"item_id": "FOODS_1_001", "store_id": "CA_2"}
        ]

        response = client.post(
            "/recommendations/FOODS_1_001/decision",
            json={"action": "approve"}
        )
        assert response.status_code == 400
        assert "exists in 2 stores" in response.json()["detail"]

    @patch("src.api.main.decision_history")
    @patch("src.api.main.recommendations")
    def test_decision_history_retrieval(self, mock_recs, mock_history, client):
        mock_recs.find.return_value.sort.return_value.limit.return_value = [
            {"item_id": "FOODS_1_001", "store_id": "CA_1"}
        ]
        mock_history.find.return_value.sort.return_value = [
            {"action": "reject", "notes": "First reject"},
            {"action": "approve", "notes": "Changed to approve"}
        ]

        response = client.get("/recommendations/FOODS_1_001/decisions?store_id=CA_1")
        assert response.status_code == 200
        data = response.json()
        assert data["total_decisions"] == 2
        assert len(data["history"]) == 2

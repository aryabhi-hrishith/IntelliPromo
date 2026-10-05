"""
Tests for the AI explanation layer (Step 26).

Test separation
---------------
1. Offline unit tests  (class TestAiServiceOffline)
   - Run without a running API server, MongoDB, or API key.
   - Mock the google-genai SDK where needed.
   - Cover: missing config, timeout, malformed JSON, validation, consistency check.

2. API integration tests  (class TestApiIntegration)
   - Require a running FastAPI server (http://127.0.0.1:8000) and MongoDB.
   - Do NOT require GEMINI_API_KEY.
   - Cover: item/store validation (404, 400), existing rule-engine endpoint contract.

3. Live-provider test  (class TestLiveProvider, marked @pytest.mark.live)
   - Runs ONLY when both GEMINI_API_KEY and a reachable model are configured.
   - Skipped automatically when the key is absent; reported as BLOCKED, not PASS.
   - Tests a real round-trip and validates the structured response.

Running tests
-------------
    # Offline only (no server, no API key needed):
    pytest tests/test_ai_explanation.py -v -k "not live and not integration"

    # All offline + integration (server + MongoDB must be running):
    pytest tests/test_ai_explanation.py -v -k "not live"

    # Everything including live provider (GEMINI_API_KEY must be set):
    pytest tests/test_ai_explanation.py -v --run-live

    # Or register the custom marker and run all:
    pytest tests/test_ai_explanation.py -v -m "not live"
    pytest tests/test_ai_explanation.py -v  # live tests auto-skip if key absent

Usage note
----------
The live-provider test is reported SKIPPED (not PASSED) when no API key is
present.  Do not claim it passed without an actual successful round-trip.
"""

import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers — service import path
# ---------------------------------------------------------------------------
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

from src.api.ai_explanation_service import (
    NOT_CONFIGURED,
    MALFORMED_OUTPUT,
    PROVIDER_ERROR,
    TIMEOUT_ERROR,
    VALIDATION_ERROR,
    _build_facts,
    _validate_response,
    _check_consistency,
    _classify_exception,
    generate_ai_explanation,
)

# ---------------------------------------------------------------------------
# Fixtures — minimal MongoDB-like dicts (no MongoDB required for unit tests)
# ---------------------------------------------------------------------------

SAMPLE_PROD = {
    "item_id":                  "FOODS_1_001",
    "store_id":                 "CA_1",
    "cat_id":                   "FOODS",
    "dept_id":                  "FOODS_1",
    "latest_sell_price":        3.98,
    "simulated_inventory_units": 120,
    "simulated_coverage_days":  14.3,
    "average_daily_units":      0.839,
    "previous_28d_units":       25,
    "recent_28d_units":         20,
    "demand_change_pct":        -20.0,
    "inventory_source":         "SIMULATED (seed=42)",
    "cost_source":              "ASSUMED (0.7x sell price)",
}

SAMPLE_REC = {
    "item_id":                       "FOODS_1_001",
    "store_id":                      "CA_1",
    "cat_id":                        "FOODS",
    "dept_id":                       "FOODS_1",
    "recommendation":                "Promote — demand decline",
    "selected_candidate_discount_pct": 5,
    "selected_discounted_price":       3.78,
    "selected_discounted_margin_pct":  5.0,
    "demand_used_units_per_day":       0.714,
    "demand_source":                   "HISTORICAL_PROXY",
    "demand_change_pct":               -20.0,
    "simulated_inventory_units":       120,
    "coverage_days":                   14.3,
    "latest_sell_price":               3.98,
    "assumed_unit_cost":               2.79,
    "current_unit_margin":             1.19,
    "current_margin_pct":              29.9,
    "explanation":                     "Demand declined ≥20% vs prior 28 days.",
}

VALID_AI_RESPONSE = {
    "summary":            "The rule engine recommended a 5% promotion due to a demand decline.",
    "supporting_factors": [
        "Demand fell 20.0% versus the prior 28-day window.",
        "Simulated coverage of 14.3 days is within the normal range.",
    ],
    "inventory_context":  "Coverage of 14.3 days (SIMULATED) did not trigger an excess or low-stock alert.",
    "discount_context":   "A 5% candidate discount was selected as the largest that maintains margin ≥5%.",
    "limitations": [
        "Inventory is SIMULATED and does not represent actual stock.",
        "Unit cost is ASSUMED at 0.7× selling price.",
        "Demand is a HISTORICAL PROXY, not a live forecast.",
        "No promotion-lift estimate is provided.",
        "Thresholds are prototype assumptions.",
    ],
    "human_review_required": True,
}


# ===========================================================================
# 1. OFFLINE UNIT TESTS
# ===========================================================================

class TestAiServiceOffline:
    """Pure unit tests — no network, no server, no API key required."""

    # --- T1: Missing configuration ---
    def test_missing_api_key_returns_not_configured(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        result = generate_ai_explanation(SAMPLE_PROD, SAMPLE_REC)
        assert result["explanation_type"] == "error"
        assert result["error_type"] == NOT_CONFIGURED
        assert "GEMINI_API_KEY" in result["error_message"]
        # Must not expose any key fragment even when the var is absent
        assert "AIza" not in result["error_message"]   # no fake key
        assert "aistudio.google.com" in result["error_message"]

    # --- T2: Timeout simulation ---
    def test_provider_timeout_returns_timeout_error(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key-for-test")

        class FakeTimeoutError(Exception):
            pass

        with patch("google.genai.Client") as mock_client_cls:
            fake_client = MagicMock()
            mock_client_cls.return_value = fake_client
            fake_client.models.generate_content.side_effect = FakeTimeoutError("request timed out after deadline")

            result = generate_ai_explanation(SAMPLE_PROD, SAMPLE_REC)
            assert result["explanation_type"] == "error"
            assert result["error_type"] == TIMEOUT_ERROR
            assert "30s" in result["error_message"] or "30" in result["error_message"]

    # --- T3: Malformed JSON from model ---
    def test_malformed_json_returns_malformed_output_error(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key-for-test")

        with patch("google.genai.Client") as mock_client_cls:
            fake_client = MagicMock()
            mock_client_cls.return_value = fake_client
            fake_response = MagicMock()
            fake_response.text = "Here is my explanation in plain text, not JSON."
            fake_client.models.generate_content.return_value = fake_response

            result = generate_ai_explanation(SAMPLE_PROD, SAMPLE_REC)
            assert result["explanation_type"] == "error"
            assert result["error_type"] == MALFORMED_OUTPUT
            assert "valid JSON" in result["error_message"]

    # --- T4: Validation error — missing fields ---
    def test_validate_response_raises_on_missing_field(self):
        incomplete = {k: v for k, v in VALID_AI_RESPONSE.items() if k != "summary"}
        with pytest.raises(ValueError, match="summary"):
            _validate_response(incomplete)

    # --- T5: Validation error — wrong types ---
    def test_validate_response_raises_on_wrong_type(self):
        bad = dict(VALID_AI_RESPONSE)
        bad["supporting_factors"] = "should be a list"
        with pytest.raises(ValueError, match="array"):
            _validate_response(bad)

    # --- T5b: Validation enforces human_review_required = True ---
    def test_validate_response_enforces_human_review_true(self):
        resp = dict(VALID_AI_RESPONSE)
        resp["human_review_required"] = False
        result = _validate_response(resp)
        assert result["human_review_required"] is True

    # --- T6: Consistency guard does not block valid response ---
    def test_consistency_check_logs_warning_but_does_not_raise(self, caplog):
        import logging
        facts = _build_facts(SAMPLE_PROD, SAMPLE_REC)
        good = dict(VALID_AI_RESPONSE)
        # Should not raise for a matching summary
        _check_consistency(good, facts)

        bad_summary = dict(VALID_AI_RESPONSE)
        bad_summary["summary"] = "Something completely unrelated about the weather."
        with caplog.at_level(logging.WARNING, logger="src.api.ai_explanation_service"):
            _check_consistency(bad_summary, facts)
        # A warning should have been emitted, but no exception
        assert any("review" in r.message.lower() or "summary" in r.message.lower()
                   for r in caplog.records)

    # --- T7: _build_facts extracts correct fields without inventing values ---
    def test_build_facts_extracts_all_fields(self):
        facts = _build_facts(SAMPLE_PROD, SAMPLE_REC)
        assert facts["item_id"]    == "FOODS_1_001"
        assert facts["store_id"]   == "CA_1"
        assert facts["recommendation"] == "Promote — demand decline"
        assert facts["simulated_inventory_units"] == 120
        assert facts["coverage_days"] == pytest.approx(14.3, abs=0.01)
        # Must not invent anything not present in the source docs
        assert "invented_field" not in facts

    # --- T8: classify_exception maps rate-limit exception correctly ---
    def test_classify_rate_limit_exception(self):
        exc = Exception("429 resource_exhausted: quota exceeded")
        result = _classify_exception(exc, 30)
        assert result["error_type"] == PROVIDER_ERROR
        assert "quota" in result["error_message"].lower() or "rate" in result["error_message"].lower()

    # --- T9: classify_exception maps auth exception correctly ---
    def test_classify_auth_exception(self):
        exc = Exception("401 unauthenticated: invalid api_key")
        result = _classify_exception(exc, 30)
        assert result["error_type"] == NOT_CONFIGURED

    # --- T10: _validate_response accepts fully valid response ---
    def test_validate_response_accepts_valid_input(self):
        result = _validate_response(dict(VALID_AI_RESPONSE))
        assert result["human_review_required"] is True
        assert isinstance(result["supporting_factors"], list)
        assert isinstance(result["limitations"], list)


# ===========================================================================
# 2. API INTEGRATION TESTS  (require running FastAPI + MongoDB)
# ===========================================================================

API_BASE = os.environ.get("TEST_API_BASE", "http://127.0.0.1:8000")


def _api_available() -> bool:
    try:
        import httpx
        r = httpx.get(f"{API_BASE}/", timeout=2)
        return r.status_code == 200
    except Exception:
        return False


def _mongo_available() -> bool:
    try:
        from src.api.database import client
        client.admin.command("ping")
        return True
    except Exception:
        return False


@pytest.mark.skipif(
    not (_api_available() or _mongo_available()),
    reason="Neither FastAPI server nor local MongoDB is reachable",
)
class TestApiIntegration:
    """
    Integration tests against a live FastAPI server or in-process TestClient.
    A running MongoDB instance is required.
    GEMINI_API_KEY is NOT required for these tests.
    """

    @pytest.fixture(scope="class")
    @classmethod
    def client(cls):
        if _api_available():
            import httpx
            with httpx.Client(base_url=API_BASE, timeout=10) as c:
                yield c
        else:
            from fastapi.testclient import TestClient
            from src.api.main import app
            with TestClient(app) as c:
                yield c

    @pytest.fixture(scope="class")
    @classmethod
    def first_item(cls, client):
        """Get the first recommendation from CA_1 for use in subsequent tests."""
        r = client.get("/recommendations?limit=1&store_id=CA_1")
        assert r.status_code == 200
        results = r.json().get("results", [])
        assert results, "No recommendations found in CA_1; check MongoDB population."
        return results[0]

    # --- I1: Nonexistent item → 404 ---
    def test_nonexistent_item_returns_404(self, client):
        r = client.get("/recommendations/NONEXISTENT_ITEM_XYZ/ai-explanation?store_id=CA_1")
        assert r.status_code == 404

    # --- I2: Ambiguous item without store_id → 400 ---
    def test_ambiguous_item_without_store_returns_400(self, client, first_item):
        item_id = first_item["item_id"]
        # Call without store_id — item likely exists in multiple stores
        r = client.get(f"/recommendations/{item_id}/ai-explanation")
        # Either 400 (multi-store) or 200 (single store) — both are valid
        assert r.status_code in (200, 400)
        if r.status_code == 400:
            detail = r.json().get("detail", "")
            assert "store_id" in detail.lower() or "stores" in detail.lower()

    # --- I3: Missing GEMINI_API_KEY → graceful error (not a 500) ---
    def test_missing_key_returns_graceful_error(self, client, first_item, monkeypatch):
        # The server's GEMINI_API_KEY may or may not be set.
        # Either way, we check the response is well-formed.
        item_id  = first_item["item_id"]
        store_id = first_item["store_id"]
        r = client.get(f"/recommendations/{item_id}/ai-explanation?store_id={store_id}")
        assert r.status_code == 200
        body = r.json()
        assert "explanation_type" in body
        assert body["explanation_type"] in ("ai_generated", "error")
        if body["explanation_type"] == "error":
            assert "error_type"    in body
            assert "error_message" in body
            # Must not leak any key fragment
            assert "AIza" not in json.dumps(body)

    # --- I4: Existing rule-engine endpoint still works ---
    def test_rule_engine_endpoint_unchanged(self, client, first_item):
        item_id  = first_item["item_id"]
        store_id = first_item["store_id"]
        r = client.get(f"/recommendations/{item_id}/explanation?store_id={store_id}")
        assert r.status_code == 200
        body = r.json()
        # Check original contract fields are present
        for field in ("item_id", "store_id", "recommendation",
                      "supporting_factors", "data_limitations"):
            assert field in body, f"Rule-engine response missing field: {field}"

    # --- I5: /recommendations endpoint paginates correctly ---
    def test_recommendations_list_endpoint(self, client):
        r = client.get("/recommendations?limit=5&store_id=CA_1")
        assert r.status_code == 200
        body = r.json()
        assert "results" in body
        assert len(body["results"]) <= 5

    # --- I6: ai-explanation response shape is consistent with recommendation ---
    def test_ai_explanation_recommendation_consistency(self, client, first_item):
        item_id  = first_item["item_id"]
        store_id = first_item["store_id"]
        r = client.get(f"/recommendations/{item_id}/ai-explanation?store_id={store_id}")
        assert r.status_code == 200
        body = r.json()
        # item_id and store_id in response must match what we requested
        assert body.get("item_id")  == item_id
        assert body.get("store_id") == store_id
        if body.get("explanation_type") == "ai_generated":
            ai_exp = body.get("ai_explanation", {})
            assert ai_exp.get("human_review_required") is True
            # factual_metrics must match stored recommendation
            metrics = body.get("factual_metrics", {})
            assert metrics.get("recommendation") == first_item.get("recommendation")


# ===========================================================================
# 3. LIVE PROVIDER TEST  (optional — requires GEMINI_API_KEY to be set)
# ===========================================================================

_has_api_key = bool(os.environ.get("GEMINI_API_KEY", "").strip())


@pytest.mark.live
@pytest.mark.skipif(not _has_api_key, reason=(
    "LIVE TEST BLOCKED: GEMINI_API_KEY is not set. "
    "Set GEMINI_API_KEY in your .env file to run this test. "
    "This is correctly reported as SKIPPED, not PASSED."
))
class TestLiveProvider:
    """
    Optional end-to-end test against the real Gemini API.
    Skipped automatically when GEMINI_API_KEY is absent.

    To run:
        export GEMINI_API_KEY=your_key
        pytest tests/test_ai_explanation.py -v -m live
    """

    def test_live_round_trip_returns_valid_structured_response(self):
        """
        Calls the real Gemini API with SAMPLE_PROD/SAMPLE_REC and validates
        the full structured response.  Reports BLOCKED (as SKIP) if the key
        is not configured — never as a false PASS.
        """
        result = generate_ai_explanation(SAMPLE_PROD, SAMPLE_REC)

        if result["explanation_type"] == "error":
            if result["error_type"] == NOT_CONFIGURED:
                pytest.skip(
                    f"LIVE TEST BLOCKED (NOT_CONFIGURED): {result['error_message']}"
                )
            pytest.fail(
                f"Live provider returned an error — NOT a PASS.\n"
                f"error_type:    {result['error_type']}\n"
                f"error_message: {result['error_message']}"
            )

        assert result["explanation_type"] == "ai_generated", (
            f"Expected 'ai_generated', got '{result['explanation_type']}'"
        )
        assert result["provider"] == "Google Gemini"
        assert isinstance(result["model"], str) and result["model"]
        assert isinstance(result["latency_ms"], int) and result["latency_ms"] >= 0
        assert isinstance(result["generated_at"], str)

        ai_exp = result["ai_explanation"]
        assert isinstance(ai_exp["summary"], str) and ai_exp["summary"].strip()
        assert isinstance(ai_exp["supporting_factors"], list)
        assert len(ai_exp["supporting_factors"]) >= 1
        assert isinstance(ai_exp["inventory_context"], str)
        assert isinstance(ai_exp["discount_context"], str)
        assert isinstance(ai_exp["limitations"], list)
        assert len(ai_exp["limitations"]) >= 1
        assert ai_exp["human_review_required"] is True

        # Factual grounding: the AI response must not invent a different recommendation
        facts = result["factual_metrics"]
        assert facts["item_id"]    == SAMPLE_PROD["item_id"]
        assert facts["store_id"]   == SAMPLE_PROD["store_id"]
        assert facts["recommendation"] == SAMPLE_REC["recommendation"]

        # The recommendation string should appear (or a distinctive word from it)
        # somewhere in the AI summary — not as a hard requirement, but as a
        # consistency signal. Failure prints a warning, not a test failure.
        summary_lower = ai_exp["summary"].lower()
        rec_words     = [w for w in facts["recommendation"].lower().split() if len(w) > 4]
        if rec_words and not any(w in summary_lower for w in rec_words):
            print(
                f"\nWARNING: AI summary does not clearly reference the recommendation "
                f"'{facts['recommendation']}'. Review manually.\n"
                f"Summary: {ai_exp['summary']}"
            )

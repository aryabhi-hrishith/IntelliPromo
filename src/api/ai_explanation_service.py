"""
AI Explanation Service — google-genai SDK (google-genai<3.0.0).

Generates a structured, grounded, plain-language explanation for one
(item_id, store_id) recommendation pair using the Google Gemini Developer API.

SDK: google-genai  (from google import genai; client = genai.Client(...))
     NOT the legacy google-generativeai package.

HARD CONSTRAINTS (enforced in prompt and validated in code):
  • The LLM does NOT select, modify or question the recommendation or discount.
  • Every number used in the explanation must come from the FACTS block.
  • The LLM does NOT claim a promotion will increase sales or profit.
  • Simulated inventory, assumed cost, and historical-proxy demand are all
    labelled as such in the prompt AND in the output.
  • human_review_required is always True (enforced post-generation).

Configuration (environment variables):
  GEMINI_API_KEY  — required; Gemini Developer API key.
                    Obtain at https://aistudio.google.com/apikey.
                    Check current quota and billing terms at that URL.
  GEMINI_MODEL    — optional; model string recognised by the Gemini Developer
                    API.  Default: gemini-2.0-flash-lite
                    Recommended stable alias: gemini-2.0-flash
                    To list available models check Google AI Studio or the
                    REST API.  Do not assume any specific model is always free
                    or always available; verify with your account settings.

Error handling:
  generate_ai_explanation() never raises.  On any failure it returns a dict
  with explanation_type="error", error_type, and a safe error_message.
  Internal stack traces are logged but never forwarded to the caller.
"""

import json
import logging
import math
import os
import time
from datetime import datetime, timezone
from typing import Any, Optional

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration defaults (all overridable via environment variables)
# ---------------------------------------------------------------------------
_DEFAULT_MODEL   = "gemini-2.0-flash-lite"   # small, fast, cost-efficient default
_PROVIDER_NAME   = "Google Gemini"
_REQUEST_TIMEOUT = 30   # seconds; passed to the SDK's http_options
_MAX_TOKENS      = 1200

# ---------------------------------------------------------------------------
# Validated output field names
# ---------------------------------------------------------------------------
_REQUIRED_FIELDS: frozenset[str] = frozenset({
    "summary",
    "supporting_factors",
    "inventory_context",
    "discount_context",
    "limitations",
    "human_review_required",
})

# ---------------------------------------------------------------------------
# Error-type tokens (returned in the error dict; never expose raw exceptions)
# ---------------------------------------------------------------------------
NOT_CONFIGURED   = "NOT_CONFIGURED"
PROVIDER_ERROR   = "PROVIDER_ERROR"
TIMEOUT_ERROR    = "TIMEOUT_ERROR"
MALFORMED_OUTPUT = "MALFORMED_OUTPUT"
VALIDATION_ERROR = "VALIDATION_ERROR"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_config() -> tuple[Optional[str], str]:
    """
    Read GEMINI_API_KEY and GEMINI_MODEL from the environment.
    Returns (api_key_or_None, model_name).
    """
    key   = os.environ.get("GEMINI_API_KEY", "").strip() or None
    model = os.environ.get("GEMINI_MODEL",   "").strip() or _DEFAULT_MODEL
    return key, model


def _safe_float(v) -> Optional[float]:
    if v is None:
        return None
    try:
        f = float(v)
        return None if (math.isnan(f) or math.isinf(f)) else round(f, 4)
    except (TypeError, ValueError):
        return None


def _safe_int(v) -> Optional[int]:
    f = _safe_float(v)
    return int(round(f)) if f is not None else None


def _build_facts(prod_doc: dict, rec_doc: dict) -> dict:
    """
    Extract a flat dict of facts from MongoDB documents.
    All values are taken verbatim from the documents — nothing is computed or
    invented here.  This dict is serialised to JSON and passed to the LLM.
    """
    return {
        # --- Identity ---
        "item_id":    rec_doc.get("item_id")  or prod_doc.get("item_id"),
        "store_id":   rec_doc.get("store_id") or prod_doc.get("store_id"),
        "category":   rec_doc.get("cat_id")   or prod_doc.get("cat_id"),
        "department": rec_doc.get("dept_id")  or prod_doc.get("dept_id"),
        # --- Authoritative rule-engine output (DO NOT modify) ---
        "recommendation":                  rec_doc.get("recommendation"),
        "selected_candidate_discount_pct": _safe_int(rec_doc.get("selected_candidate_discount_pct")),
        "selected_discounted_price":        _safe_float(rec_doc.get("selected_discounted_price")),
        "selected_discounted_margin_pct":   _safe_float(rec_doc.get("selected_discounted_margin_pct")),
        # --- Demand (HISTORICAL PROXY — not a live forecast) ---
        "demand_used_units_per_day": _safe_float(rec_doc.get("demand_used_units_per_day")),
        "demand_source":             rec_doc.get("demand_source"),
        "previous_28d_units":        _safe_int(prod_doc.get("previous_28d_units")),
        "recent_28d_units":          _safe_int(prod_doc.get("recent_28d_units")),
        "demand_change_pct":         _safe_float(
            rec_doc.get("demand_change_pct")
            if rec_doc.get("demand_change_pct") is not None
            else prod_doc.get("demand_change_pct")
        ),
        # --- Inventory (SIMULATED — not real stock data) ---
        "simulated_inventory_units": _safe_int(rec_doc.get("simulated_inventory_units")),
        "coverage_days":             _safe_float(rec_doc.get("coverage_days")),
        "inventory_source":          prod_doc.get("inventory_source"),
        # --- Price / cost / margin (cost is ASSUMED at 0.7× selling price) ---
        "latest_sell_price":   _safe_float(rec_doc.get("latest_sell_price")),
        "assumed_unit_cost":   _safe_float(rec_doc.get("assumed_unit_cost")),
        "cost_source":         prod_doc.get("cost_source"),
        "current_unit_margin": _safe_float(rec_doc.get("current_unit_margin")),
        "current_margin_pct":  _safe_float(rec_doc.get("current_margin_pct")),
        # --- Rule-engine explanation text (context for the LLM; do not copy verbatim) ---
        "stored_rule_explanation": rec_doc.get("explanation"),
    }


def _build_prompt(facts: dict) -> str:
    facts_json = json.dumps(facts, indent=2, default=str)
    return f"""\
You are a neutral retail analytics assistant helping a store manager understand
why the rule-based promotion engine made a specific recommendation.

=== STRICT RULES — MUST FOLLOW ===
1. Use ONLY the numbers present in the FACTS block. Do not estimate, invent, or
   extrapolate any figure that is not explicitly provided.
2. Do NOT change, question, or contradict the "recommendation" or the
   "selected_candidate_discount_pct" values — they are determined by the
   rule engine and are not yours to modify.
3. Do NOT claim that a promotion will increase sales, revenue, or profit.
   Historical demand trends are correlational observations, NOT forecasts.
4. Clearly label data quality throughout your response:
   - Inventory is SIMULATED (not real stock data).
   - Unit cost is ASSUMED (0.7× selling price, not verified Walmart data).
   - Demand is a HISTORICAL PROXY from the M5 dataset, not a live forecast.
5. Set "human_review_required" to exactly true (JSON boolean).
6. Write concisely in third person ("The item...", "Coverage of X days...").
   Each field should be 1–3 sentences. Keep supporting_factors to 2–4 items
   and limitations to 4–5 items.

=== FACTS (from MongoDB — authoritative, do not alter) ===
{facts_json}

=== REQUIRED RESPONSE FORMAT ===
Return ONLY a valid JSON object — no markdown, no code fences, no extra text.
The object must have exactly these six keys:

{{
  "summary": "<2-3 sentences: what the rule engine decided and why, referencing the recommendation and discount directly>",
  "supporting_factors": [
    "<one sentence per contributing factor: coverage days, demand trend, margin constraint>"
  ],
  "inventory_context": "<one sentence: what the simulated coverage figure triggered or did not trigger>",
  "discount_context": "<one sentence: which discount was selected or why none was chosen, referencing the margin rule>",
  "limitations": [
    "<one sentence per limitation: simulated inventory, assumed cost, historical-proxy demand, no lift estimate, prototype thresholds>"
  ],
  "human_review_required": true
}}"""


def _validate_response(parsed: Any) -> dict:
    """
    Structural and type validation of the model's JSON response.
    Raises ValueError with a descriptive message on failure.
    """
    if not isinstance(parsed, dict):
        raise ValueError(f"Expected JSON object, got {type(parsed).__name__}")

    missing = _REQUIRED_FIELDS - set(parsed.keys())
    if missing:
        raise ValueError(f"Missing required fields: {sorted(missing)}")

    if not isinstance(parsed.get("summary"), str) or not parsed["summary"].strip():
        raise ValueError("'summary' must be a non-empty string")
    if not isinstance(parsed.get("supporting_factors"), list):
        raise ValueError("'supporting_factors' must be a JSON array")
    if not isinstance(parsed.get("inventory_context"), str):
        raise ValueError("'inventory_context' must be a string")
    if not isinstance(parsed.get("discount_context"), str):
        raise ValueError("'discount_context' must be a string")
    if not isinstance(parsed.get("limitations"), list):
        raise ValueError("'limitations' must be a JSON array")

    # Enforce human_review_required=True regardless of what the model returned.
    parsed["human_review_required"] = True

    return parsed


def _check_consistency(validated: dict, facts: dict) -> None:
    """
    Log a warning (not an error) if the AI summary does not appear to mention
    the stored recommendation.  This is a soft guard — the response is still
    returned; the caller can inspect the badge.
    """
    summary_lower = validated.get("summary", "").lower()
    stored_rec    = (facts.get("recommendation") or "").lower()
    # Use keywords from the stored recommendation text
    if stored_rec:
        # Split into words and check if at least one distinctive word appears
        keywords = [w for w in stored_rec.split() if len(w) > 4]
        if keywords and not any(kw in summary_lower for kw in keywords):
            logger.warning(
                "AI summary may not reference the stored recommendation '%s'; "
                "manual review advisable. item_id=%s store_id=%s",
                facts.get("recommendation"),
                facts.get("item_id"),
                facts.get("store_id"),
            )


def _classify_exception(exc: Exception, timeout_secs: int) -> dict:
    """
    Map a provider exception to a safe structured error dict.
    Never includes raw tracebacks or sensitive environment data.
    """
    exc_str = str(exc).lower()
    exc_type = type(exc).__name__

    if "timeout" in exc_str or "deadline" in exc_str or "timed out" in exc_str:
        return {
            "error_type":    TIMEOUT_ERROR,
            "error_message": (
                f"The AI provider did not respond within {timeout_secs}s. "
                "Try again in a moment."
            ),
        }
    if any(tok in exc_str for tok in ("quota", "resource_exhausted", "429")):
        return {
            "error_type":    PROVIDER_ERROR,
            "error_message": (
                "The Gemini API quota or rate limit was reached. "
                "Wait a moment and try again, or check your quota at "
                "https://aistudio.google.com."
            ),
        }
    if any(tok in exc_str for tok in ("api_key", "invalid", "401", "403",
                                       "permission", "unauthenticated")):
        return {
            "error_type":    NOT_CONFIGURED,
            "error_message": (
                "The Gemini API key is invalid or lacks permission. "
                "Check GEMINI_API_KEY in your root .env file."
            ),
        }
    if "model" in exc_str and any(tok in exc_str for tok in ("not found", "404", "invalid")):
        return {
            "error_type":    NOT_CONFIGURED,
            "error_message": (
                "The model name in GEMINI_MODEL is not recognised by the API. "
                "Check the model name or remove GEMINI_MODEL to use the default."
            ),
        }

    # Generic — log internally but do not expose the stack trace
    logger.error(
        "Gemini API call failed (%s): %s",
        exc_type, exc,
        exc_info=False,    # no stack trace in structured logs
    )
    return {
        "error_type":    PROVIDER_ERROR,
        "error_message": (
            "The AI provider returned an unexpected error. "
            "Check the backend server logs for details."
        ),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_ai_explanation(prod_doc: dict, rec_doc: dict) -> dict:
    """
    Generate a structured AI explanation for one (item_id, store_id) pair.

    Uses the google-genai SDK (google.genai.Client) with response_mime_type
    constrained to "application/json" so the model is required to output JSON.

    Returns a dict that is always one of two shapes:

    Success  — explanation_type = "ai_generated"
    {
        "explanation_type": "ai_generated",
        "provider":         "Google Gemini",
        "model":            str,               # actual model used
        "generated_at":     str,               # ISO-8601 UTC
        "latency_ms":       int,
        "ai_explanation":   {
            "summary":               str,
            "supporting_factors":    list[str],
            "inventory_context":     str,
            "discount_context":      str,
            "limitations":           list[str],
            "human_review_required": True,
        },
        "factual_metrics":  dict,              # the exact numbers sent to the LLM
    }

    Error  — explanation_type = "error"
    {
        "explanation_type": "error",
        "error_type":       str,   # NOT_CONFIGURED | PROVIDER_ERROR | TIMEOUT_ERROR
                                   # | MALFORMED_OUTPUT | VALIDATION_ERROR
        "error_message":    str,   # user-safe, no keys / stack traces
        "provider":         str,
        "model":            str,
        "latency_ms":       int,   # may be absent if error occurred before the call
    }

    This function NEVER raises.
    """
    api_key, model_name = _get_config()

    if not api_key:
        return {
            "explanation_type": "error",
            "error_type":       NOT_CONFIGURED,
            "error_message": (
                "GEMINI_API_KEY is not set. "
                "Add GEMINI_API_KEY=<your_key> to the root .env file. "
                "Obtain a key at https://aistudio.google.com/apikey "
                "and check your account's quota and billing terms there."
            ),
            "provider": _PROVIDER_NAME,
            "model":    model_name,
        }

    facts  = _build_facts(prod_doc, rec_doc)
    prompt = _build_prompt(facts)

    t_start    = time.monotonic()
    latency_ms = 0

    try:
        # --- Import lazily so the module loads even without the package ---
        from google import genai                # type: ignore[import]
        from google.genai import types          # type: ignore[import]

        # Per SDK docs: pass http_options for timeout control.
        # Client is created per-call to respect GEMINI_MODEL changes without restart.
        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=_REQUEST_TIMEOUT * 1000),  # ms
        )

        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                max_output_tokens=_MAX_TOKENS,
                temperature=0.15,   # low temperature → deterministic, grounded output
            ),
        )

        latency_ms = int((time.monotonic() - t_start) * 1000)
        raw_text   = response.text.strip()

    except ImportError:
        return {
            "explanation_type": "error",
            "error_type":       NOT_CONFIGURED,
            "error_message": (
                "The google-genai package is not installed. "
                "Run: pip install 'google-genai<3.0.0'"
            ),
            "provider": _PROVIDER_NAME,
            "model":    model_name,
        }
    except Exception as exc:
        latency_ms = int((time.monotonic() - t_start) * 1000)
        err = _classify_exception(exc, _REQUEST_TIMEOUT)
        return {
            "explanation_type": "error",
            "provider":   _PROVIDER_NAME,
            "model":      model_name,
            "latency_ms": latency_ms,
            **err,
        }

    # --- Parse JSON ---
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        logger.warning(
            "Model returned non-JSON (preview): %s",
            raw_text[:300],
        )
        return {
            "explanation_type": "error",
            "error_type":       MALFORMED_OUTPUT,
            "error_message": (
                "The AI model did not return valid JSON. "
                "This is NOT a rule-engine fallback — the request failed. "
                "Try again or switch the model via GEMINI_MODEL."
            ),
            "provider":    _PROVIDER_NAME,
            "model":       model_name,
            "latency_ms":  latency_ms,
            "raw_preview": raw_text[:300],   # safe: no keys, no stack trace
        }

    # --- Validate structure and types ---
    try:
        validated = _validate_response(parsed)
    except ValueError as exc:
        logger.warning("Response validation failed: %s", exc)
        return {
            "explanation_type": "error",
            "error_type":       VALIDATION_ERROR,
            "error_message": (
                f"AI response failed validation: {exc}. "
                "This is NOT an LLM-generated explanation."
            ),
            "provider":   _PROVIDER_NAME,
            "model":      model_name,
            "latency_ms": latency_ms,
        }

    # --- Soft consistency check (logs warning; does not block the response) ---
    _check_consistency(validated, facts)

    return {
        "explanation_type": "ai_generated",
        "provider":         _PROVIDER_NAME,
        "model":            model_name,
        "generated_at":     datetime.now(timezone.utc).isoformat(),
        "latency_ms":       latency_ms,
        "ai_explanation":   validated,
        "factual_metrics":  facts,
    }

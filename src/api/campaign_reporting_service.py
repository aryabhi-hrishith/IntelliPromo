"""
Campaign Effectiveness and Retailer Impact Reporting Service (Stage 4).

Summarizes campaign decision history, discount distributions, recommendation categories,
store summaries, and campaign outcome evaluations.
Maintains strict separation between proposed/approved campaigns and executed campaigns,
and ensures clear labeling of data sources (Real Operational Records vs Synthetic Demo Data).
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pymongo.errors import PyMongoError
from .database import recommendations, decision_history, campaign_outcomes, clean_document

def compute_campaign_report(store_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Computes summary metrics for campaign decisions, approvals, discount distributions,
    and recommendation categories.
    """
    query = {}
    if store_id:
        query["store_id"] = store_id

    try:
        recs = list(recommendations.find(query))
    except PyMongoError:
        recs = []

    total_recommendations = len(recs)
    if total_recommendations == 0:
        return {
            "total_recommendations": 0,
            "decision_counts": {"approved": 0, "rejected": 0, "pending": 0},
            "decision_rates_pct": {"approved": 0.0, "rejected": 0.0, "pending": 0.0},
            "average_discount_pct": 0.0,
            "discount_distribution": {},
            "recommendation_categories": {},
            "store_summaries": {},
            "time_period": "Historical Proxy Period (M5 Dataset) / Decision Log Window",
            "data_source": "M5 Retail Dataset & User Decision History",
            "execution_status_note": (
                "Proposed or approved campaigns are distinct from executed campaigns. "
                "Approval does not imply campaign execution, nor does it infer causal promotion lift "
                "from ordinary sales changes."
            )
        }

    approved = 0
    rejected = 0
    pending = 0
    discount_counts = {}
    category_counts = {}
    store_counts = {}

    for r in recs:
        status = r.get("decision_status")
        if status == "approved":
            approved += 1
        elif status == "rejected":
            rejected += 1
        else:
            pending += 1

        disc = r.get("selected_candidate_discount_pct", 0)
        disc_label = f"{disc}% Off" if disc > 0 else "0% (No Promo)"
        discount_counts[disc_label] = discount_counts.get(disc_label, 0) + 1

        cat = r.get("recommendation", "Unspecified")
        category_counts[cat] = category_counts.get(cat, 0) + 1

        s_id = r.get("store_id", "UNKNOWN")
        store_counts[s_id] = store_counts.get(s_id, 0) + 1

    approved_pct = round((approved / total_recommendations) * 100, 2)
    rejected_pct = round((rejected / total_recommendations) * 100, 2)
    pending_pct = round((pending / total_recommendations) * 100, 2)

    avg_discount = sum(r.get("selected_candidate_discount_pct", 0) for r in recs) / total_recommendations

    return {
        "total_recommendations": total_recommendations,
        "decision_counts": {
            "approved": approved,
            "rejected": rejected,
            "pending": pending
        },
        "decision_rates_pct": {
            "approved": approved_pct,
            "rejected": rejected_pct,
            "pending": pending_pct
        },
        "average_discount_pct": round(avg_discount, 2),
        "discount_distribution": discount_counts,
        "recommendation_categories": category_counts,
        "store_summaries": store_counts,
        "time_period": "Historical Proxy Period (M5 Dataset) / Decision Log Window",
        "data_source": "M5 Retail Dataset & User Decision History (Real Operational Records)",
        "execution_status_note": (
            "Proposed or approved campaigns are distinct from executed campaigns. "
            "Approval does not imply campaign execution, nor does it infer causal promotion lift "
            "from ordinary sales changes."
        )
    }


def get_campaign_outcomes_list(store_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Retrieves recorded campaign outcomes from the database, or returns structured
    demonstration records clearly labeled as SYNTHETIC DEMO DATA if none exist.
    """
    query = {}
    if store_id:
        query["store_id"] = store_id

    try:
        docs = list(campaign_outcomes.find(query).sort("_id", -1))
        outcomes = [clean_document(d) for d in docs]
    except PyMongoError:
        outcomes = []

    if not outcomes:
        # Provide demonstration synthetic data labeled SYNTHETIC DEMO DATA per requirement 5
        outcomes = [
            {
                "item_id": "FOODS_1_001",
                "store_id": store_id or "CA_1",
                "actual_redemptions": 142,
                "actual_sales_lift_pct": 18.5,
                "actual_revenue_gain": 1250.40,
                "measured_period": "2026-Q3 Weekend Promo",
                "data_source": "SYNTHETIC DEMO DATA",
                "recorded_at": datetime.utcnow().isoformat() + "Z"
            },
            {
                "item_id": "FOODS_1_002",
                "store_id": store_id or "CA_1",
                "actual_redemptions": 98,
                "actual_sales_lift_pct": 12.1,
                "actual_revenue_gain": 840.00,
                "measured_period": "2026-Q3 Weekend Promo",
                "data_source": "SYNTHETIC DEMO DATA",
                "recorded_at": datetime.utcnow().isoformat() + "Z"
            }
        ]
        if store_id:
            outcomes = [o for o in outcomes if o["store_id"] == store_id]

    return {
        "data_source": "SYNTHETIC DEMO DATA / REAL RECORDED OUTCOMES",
        "total_outcomes": len(outcomes),
        "outcomes": outcomes,
        "note": "Measured outcomes are kept strictly separate from proposed or approved recommendation counts."
    }


def save_campaign_outcome(outcome_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validates and saves a campaign outcome record.
    """
    data_source = outcome_data.get("data_source", "REAL_RETAILER_DATA").strip().upper()
    if data_source not in ("REAL_RETAILER_DATA", "SYNTHETIC_DEMO_DATA"):
        data_source = "REAL_RETAILER_DATA"

    record = {
        "item_id": str(outcome_data["item_id"]),
        "store_id": str(outcome_data["store_id"]),
        "actual_redemptions": int(outcome_data["actual_redemptions"]),
        "actual_sales_lift_pct": float(outcome_data["actual_sales_lift_pct"]),
        "actual_revenue_gain": float(outcome_data["actual_revenue_gain"]),
        "measured_period": str(outcome_data.get("measured_period", "Current Period")),
        "data_source": data_source,
        "recorded_at": datetime.utcnow().isoformat() + "Z"
    }

    try:
        campaign_outcomes.insert_one(record)
    except PyMongoError as e:
        raise RuntimeError(f"Database error while saving outcome: {e}")

    inserted = campaign_outcomes.find_one({
        "item_id": record["item_id"],
        "store_id": record["store_id"],
        "recorded_at": record["recorded_at"]
    })
    return clean_document(inserted or record)

"""
Step 28 (Stage 2): Synthetic Product Affinity / Frequently Bought Together Pipeline.

IMPORTANT NOTICE & LIMITATION:
- The Walmart M5 dataset contains aggregated daily unit sales per product-store pair, NOT individual customer transactions or baskets.
- Real co-purchase customer data is NOT present in M5.
- This script builds a small, clearly labeled SYNTHETIC demo basket dataset and computes association rule metrics (Support, Confidence, Lift) for item pairs.
- Synthetic affinity results are kept strictly separate from real M5 demand forecasts, rule recommendations, and approval workflows.
- Do not claim these represent actual customer purchasing behavior.
"""

from itertools import combinations
from pathlib import Path
import numpy as np
import pandas as pd
from pymongo import MongoClient

PROJECT_ROOT = Path(__file__).resolve().parents[2]
INPUTS_PATH = PROJECT_ROOT / "data" / "processed" / "promotion_inputs.csv"
OUT_CSV = PROJECT_ROOT / "data" / "processed" / "product_affinity.csv"

MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "retail_promotion_planner"

RANDOM_SEED = 42
NUM_SYNTHETIC_BASKETS = 2500
MIN_SUPPORT = 0.002  # 0.2% minimum basket support
MIN_CONFIDENCE = 0.05


def compute_affinity_rules(baskets, min_support=MIN_SUPPORT, min_confidence=MIN_CONFIDENCE):
    """
    Compute Support, Confidence, and Lift for item pairs from a collection of baskets.
    
    Metrics definitions:
    - Support(A, B) = P(A union B) = fraction of baskets containing both A and B.
    - Confidence(A -> B) = P(B | A) = Support(A, B) / Support(A).
    - Lift(A, B) = P(B | A) / P(B) = Support(A, B) / (Support(A) * Support(B)).
    """
    total_baskets = len(baskets)
    if total_baskets == 0:
        return pd.DataFrame()

    item_counts = {}
    pair_counts = {}

    for basket in baskets:
        unique_items = sorted(list(set(basket)))
        for item in unique_items:
            item_counts[item] = item_counts.get(item, 0) + 1
        for item_a, item_b in combinations(unique_items, 2):
            pair = tuple(sorted([item_a, item_b]))
            pair_counts[pair] = pair_counts.get(pair, 0) + 1

    rules = []
    for (item_a, item_b), co_count in pair_counts.items():
        support_ab = co_count / total_baskets
        if support_ab < min_support:
            continue

        support_a = item_counts[item_a] / total_baskets
        support_b = item_counts[item_b] / total_baskets

        # Direction: A -> B and B -> A
        conf_a_b = support_ab / support_a if support_a > 0 else 0
        lift_a_b = conf_a_b / support_b if support_b > 0 else 0

        if conf_a_b >= min_confidence:
            rules.append({
                "item_a": item_a,
                "item_b": item_b,
                "co_occurrence_count": int(co_count),
                "support": round(float(support_ab), 4),
                "confidence": round(float(conf_a_b), 4),
                "lift": round(float(lift_a_b), 4),
                "data_source": "SYNTHETIC_DEMO_BASKET_AFFINITY",
            })

        conf_b_a = support_ab / support_b if support_b > 0 else 0
        lift_b_a = conf_b_a / support_a if support_a > 0 else 0

        if conf_b_a >= min_confidence:
            rules.append({
                "item_a": item_b,
                "item_b": item_a,
                "co_occurrence_count": int(co_count),
                "support": round(float(support_ab), 4),
                "confidence": round(float(conf_b_a), 4),
                "lift": round(float(lift_b_a), 4),
                "data_source": "SYNTHETIC_DEMO_BASKET_AFFINITY",
            })

    df_rules = pd.DataFrame(rules)
    if not df_rules.empty:
        df_rules = df_rules.sort_values(by=["item_a", "lift", "confidence"], ascending=[True, False, False])
    return df_rules


def main():
    print("=" * 70)
    print("Stage 2: Synthetic Product Affinity / Frequently Bought Together Pipeline")
    print("IMPORTANT: M5 has no transaction baskets. Generating SYNTHETIC demo baskets.")
    print("=" * 70)

    if not INPUTS_PATH.exists():
        raise FileNotFoundError(f"{INPUTS_PATH} not found. Run Step 10/14 first.")

    inputs_df = pd.read_csv(INPUTS_PATH, low_memory=False)
    # Get unique item ids (e.g. top 100 food items)
    item_pool = inputs_df["item_id"].dropna().unique()[:100].tolist()
    print(f"Item pool size for synthetic basket simulation: {len(item_pool):,} items")

    # Generate synthetic baskets with fixed random seed
    rng = np.random.default_rng(RANDOM_SEED)
    baskets = []
    for _ in range(NUM_SYNTHETIC_BASKETS):
        basket_size = rng.integers(2, 6)  # 2 to 5 items per basket
        basket_items = rng.choice(item_pool, size=basket_size, replace=False).tolist()
        baskets.append(basket_items)

    print(f"Generated {NUM_SYNTHETIC_BASKETS:,} synthetic demo baskets.")

    df_affinity = compute_affinity_rules(baskets, min_support=MIN_SUPPORT, min_confidence=MIN_CONFIDENCE)
    print(f"Computed {len(df_affinity):,} affinity rule pairs meeting support >= {MIN_SUPPORT} and confidence >= {MIN_CONFIDENCE}.")

    # Save to CSV
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df_affinity.to_csv(OUT_CSV, index=False)
    print(f"Saved affinity rules to {OUT_CSV.relative_to(PROJECT_ROOT)}")

    # Ingest into MongoDB product_affinity collection
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
        db = client[DB_NAME]
        affinity_col = db["product_affinity"]
        affinity_col.delete_many({})
        records = df_affinity.to_dict("records")
        if records:
            affinity_col.insert_many(records)
        print(f"Inserted {len(records):,} documents into MongoDB collection 'product_affinity'.")
        client.close()
    except Exception as e:
        print(f"MongoDB insertion warning: {e} (CSV successfully generated).")

    print("Synthetic product affinity pipeline completed successfully.")


if __name__ == "__main__":
    main()

"""
Step 29 (Stage 3): Synthetic Customer Segmentation and Personalized Promotions Pipeline.

IMPORTANT NOTICE & LIMITATION:
- M5 contains aggregated store-day sales, not customer-level transaction logs.
- This script processes reproducible SYNTHETIC demo customer data (data/synthetic/customers.csv & sales.csv).
- Derived customer segments (High-Value Shopper, Frequent Shopper, Value-Seeking, Occasional Shopper) are DEMO/SYNTHETIC constructs and do NOT represent real consumer behavior.
- All outputs are explicitly labeled as SYNTHETIC DEMO DATA.
"""

from pathlib import Path
import numpy as np
import pandas as pd
from pymongo import MongoClient

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CUSTOMERS_CSV = PROJECT_ROOT / "data" / "synthetic" / "customers.csv"
SALES_CSV = PROJECT_ROOT / "data" / "synthetic" / "sales.csv"
PRODUCTS_CSV = PROJECT_ROOT / "data" / "synthetic" / "products.csv"

OUT_SEGMENTS_CSV = PROJECT_ROOT / "data" / "processed" / "customer_segments.csv"
OUT_PROMOS_CSV = PROJECT_ROOT / "data" / "processed" / "segment_promotions.csv"

MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "retail_promotion_planner"


def compute_customer_features(customers_df, sales_df, products_df):
    """Compute per-customer behavioral features from synthetic transactions."""
    # Merge sales with products to get category and selling price
    df = sales_df.merge(products_df, on="product_id", how="left")
    df["line_spend"] = df["quantity"] * df["selling_price"]

    # Aggregate per customer
    cust_agg = df.groupby("customer_id").agg(
        purchase_frequency=("transaction_id", "count"),
        total_spend=("line_spend", "sum"),
        avg_basket_value=("line_spend", "mean"),
        avg_discount_pct=("discount_percentage", "mean"),
    ).reset_index()

    # Find preferred category per customer (mode)
    cat_pref = df.groupby(["customer_id", "category"]).size().reset_index(name="cat_count")
    cat_pref = cat_pref.sort_values(["customer_id", "cat_count"], ascending=[True, False])
    preferred_cat = cat_pref.drop_duplicates("customer_id")[["customer_id", "category"]].rename(columns={"category": "preferred_category"})

    cust_features = customers_df.merge(cust_agg, on="customer_id", how="left").merge(preferred_cat, on="customer_id", how="left")
    cust_features = cust_features.fillna({
        "purchase_frequency": 0,
        "total_spend": 0.0,
        "avg_basket_value": 0.0,
        "avg_discount_pct": 0.0,
        "preferred_category": "General",
    })
    return cust_features


def assign_segments(cust_features):
    """Assign interpretable segments using rule thresholds."""
    if cust_features.empty:
        cust_features["segment"] = []
        return cust_features

    spend_75 = cust_features["total_spend"].quantile(0.75)
    freq_75 = cust_features["purchase_frequency"].quantile(0.75)
    discount_75 = cust_features["avg_discount_pct"].quantile(0.75)

    segments = []
    for _, row in cust_features.iterrows():
        if row["total_spend"] >= spend_75:
            segments.append("High-Value Shopper")
        elif row["purchase_frequency"] >= freq_75:
            segments.append("Frequent Shopper")
        elif row["avg_discount_pct"] >= discount_75:
            segments.append("Value-Seeking")
        else:
            segments.append("Occasional Shopper")

    cust_features["segment"] = segments
    return cust_features


def main():
    print("=" * 70)
    print("Stage 3: Synthetic Customer Segmentation & Personalized Promotions")
    print("IMPORTANT: Using synthetic demo customer dataset. Not real shoppers.")
    print("=" * 70)

    if not CUSTOMERS_CSV.exists() or not SALES_CSV.exists() or not PRODUCTS_CSV.exists():
        raise FileNotFoundError("Synthetic customer or sales CSV files not found.")

    customers_df = pd.read_csv(CUSTOMERS_CSV)
    sales_df = pd.read_csv(SALES_CSV)
    products_df = pd.read_csv(PRODUCTS_CSV)

    print(f"Loaded {len(customers_df):,} synthetic customers and {len(sales_df):,} transactions.")

    cust_features = compute_customer_features(customers_df, sales_df, products_df)
    cust_segmented = assign_segments(cust_features)

    # Summarize segments
    segment_summary = cust_segmented.groupby("segment").agg(
        customer_count=("customer_id", "count"),
        avg_spend=("total_spend", "mean"),
        avg_frequency=("purchase_frequency", "mean"),
        avg_basket_value=("avg_basket_value", "mean"),
        avg_discount_pct=("avg_discount_pct", "mean"),
    ).reset_index()

    segment_summary["data_source"] = "SYNTHETIC_DEMO_DATA"
    segment_summary = segment_summary.round(2)

    # Define segment-targeted demo promotion suggestions
    segment_promos = [
        {
            "segment": "High-Value Shopper",
            "campaign_title": "Premium Loyalty Rewards & Early Access",
            "target_category": "Electronics & Luxury",
            "suggested_discount_pct": 10,
            "rationale": "High spenders value exclusive perks and early product releases over steep discounts.",
            "data_source": "SYNTHETIC_DEMO_DATA"
        },
        {
            "segment": "Frequent Shopper",
            "campaign_title": "Repeat Purchase Bundle & Points Booster",
            "target_category": "Home & Kitchen",
            "suggested_discount_pct": 15,
            "rationale": "Frequent buyers respond well to basket-building incentives and loyalty multipliers.",
            "data_source": "SYNTHETIC_DEMO_DATA"
        },
        {
            "segment": "Value-Seeking",
            "campaign_title": "Flash Sale & Clearance Markdown",
            "target_category": "Clothing & Sports",
            "suggested_discount_pct": 25,
            "rationale": "Price-sensitive shoppers have high responsiveness to deep discount promotions.",
            "data_source": "SYNTHETIC_DEMO_DATA"
        },
        {
            "segment": "Occasional Shopper",
            "campaign_title": "Welcome Back & Re-engagement Discount",
            "target_category": "Beauty & Personal Care",
            "suggested_discount_pct": 20,
            "rationale": "Occasional shoppers require targeted incentives to stimulate repeat store visits.",
            "data_source": "SYNTHETIC_DEMO_DATA"
        },
    ]

    df_promos = pd.DataFrame(segment_promos)

    # Save to CSV
    OUT_SEGMENTS_CSV.parent.mkdir(parents=True, exist_ok=True)
    segment_summary.to_csv(OUT_SEGMENTS_CSV, index=False)
    df_promos.to_csv(OUT_PROMOS_CSV, index=False)
    print(f"Saved segment summaries to {OUT_SEGMENTS_CSV.relative_to(PROJECT_ROOT)}")
    print(f"Saved segment promos to {OUT_PROMOS_CSV.relative_to(PROJECT_ROOT)}")

    # Ingest into MongoDB
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
        db = client[DB_NAME]
        
        seg_col = db["customer_segments"]
        seg_col.delete_many({})
        seg_col.insert_many(segment_summary.to_dict("records"))

        promo_col = db["segment_promotions"]
        promo_col.delete_many({})
        promo_col.insert_many(df_promos.to_dict("records"))

        print("Inserted customer segments and segment promotions into MongoDB successfully.")
        client.close()
    except Exception as e:
        print(f"MongoDB warning: {e} (CSVs successfully generated).")

    print("Synthetic customer segmentation pipeline completed successfully.")


if __name__ == "__main__":
    main()

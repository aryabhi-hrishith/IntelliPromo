"""
Step 10: Prepare combined inputs for promotion planning.

Merges the demand summary (Step 8) with the latest selling prices (Step 9),
validates the merge, and adds SIMULATED inventory and ASSUMED unit cost.

IMPORTANT DATA LABELS
- simulated_inventory_units is SYNTHETIC. The M5 dataset has no stock levels.
- assumed_unit_cost is an ASSUMPTION (selling price x COST_RATIO).
  It is NOT actual Walmart cost data.

Reads:  data/processed/m5_demand_summary.csv
        data/processed/m5_latest_prices.csv
Writes: data/processed/promotion_inputs.csv  (the only file this script writes)
"""

from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Configuration (edit these; they are documented in the output file's labels)
# ---------------------------------------------------------------------------
RANDOM_SEED = 42

# Simulated stock = average_daily_units x coverage days, where coverage days
# is drawn uniformly from this range. Low values create stockout-risk cases,
# high values create excess-stock cases for the later recommendation engine.
MIN_COVERAGE_DAYS = 3
MAX_COVERAGE_DAYS = 45

# Every product-store gets at least this many simulated units, so that
# zero-demand items do not end up with exactly zero stock.
MIN_STOCK_UNITS = 1

# Assumed unit cost as a fraction of the selling price (0.70 = 30% gross margin).
COST_RATIO = 0.70

KEYS = ["item_id", "store_id"]
DEMAND_COL = "average_daily_units"

# ---------------------------------------------------------------------------
# Paths (relative to the project root, regardless of where you run the script)
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
DEMAND_PATH = PROCESSED_DIR / "m5_demand_summary.csv"
PRICES_PATH = PROCESSED_DIR / "m5_latest_prices.csv"
OUTPUT_PATH = PROCESSED_DIR / "promotion_inputs.csv"


def load_csv(path: Path, label: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"{label} not found at {path}. Run the earlier step that creates it first."
        )
    return pd.read_csv(path)


def check_columns(df: pd.DataFrame, required: list, label: str) -> None:
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(
            f"{label} is missing required column(s) {missing}. "
            f"Columns found: {list(df.columns)}"
        )


def check_duplicate_keys(df: pd.DataFrame, label: str) -> None:
    dupes = int(df.duplicated(subset=KEYS).sum())
    print(f"  {label}: {len(df):,} rows, duplicate {KEYS} keys: {dupes:,}")
    if dupes:
        raise ValueError(
            f"{label} has {dupes:,} duplicate {KEYS} rows. "
            "Fix the source step before merging."
        )


def main() -> None:
    print("Step 10: preparing promotion inputs...", flush=True)

    # Safety: never write over an input dataset.
    if OUTPUT_PATH in (DEMAND_PATH, PRICES_PATH):
        raise RuntimeError("Output path matches an input path; refusing to continue.")

    # 1. Load -------------------------------------------------------------
    demand = load_csv(DEMAND_PATH, "Demand summary")
    prices = load_csv(PRICES_PATH, "Latest prices")
    check_columns(demand, KEYS + [DEMAND_COL], "Demand summary")
    check_columns(prices, KEYS + ["sell_price"], "Latest prices")

    # Step 9 saved these as wm_yr_wk / sell_price; rename in memory only
    # (the CSV on disk is not modified) so the output columns are explicit.
    prices = prices.rename(
        columns={"sell_price": "latest_sell_price", "wm_yr_wk": "latest_wm_yr_wk"}
    )
    # prices = load_csv(PRICES_PATH, "Latest prices")
    # check_columns(demand, KEYS + [DEMAND_COL], "Demand summary")
    # check_columns(prices, KEYS + ["latest_sell_price"], "Latest prices")

    # 2. Validate keys ----------------------------------------------------
    print("\n[Validation] Duplicate keys")
    check_duplicate_keys(demand, "Demand summary")
    check_duplicate_keys(prices, "Latest prices")

    # 3. Merge (outer, so unmatched records on either side are visible) ----
    merged = demand.merge(
        prices,
        on=KEYS,
        how="outer",
        indicator=True,
        validate="one_to_one",
        suffixes=("", "_price"),
    )
    only_demand = int((merged["_merge"] == "left_only").sum())
    only_prices = int((merged["_merge"] == "right_only").sum())
    both = int((merged["_merge"] == "both").sum())

    print("\n[Validation] Merge on item_id + store_id")
    print(f"  Matched in both files:         {both:,}")
    print(f"  In demand only (no price row): {only_demand:,}")
    print(f"  In prices only (no demand):    {only_prices:,}")

    # Keep every demand record; drop price-only rows (nothing to plan for).
    df = merged[merged["_merge"] != "right_only"].drop(columns="_merge").copy()
    if only_prices:
        print(f"  Dropped {only_prices:,} price-only rows.")

    # 4. Missing prices / demand -----------------------------------------
    df["has_price"] = df["latest_sell_price"].notna()
    missing_price = int((~df["has_price"]).sum())
    missing_demand = int(df[DEMAND_COL].isna().sum())
    print("\n[Validation] Missing values in key fields")
    print(f"  Missing latest_sell_price: {missing_price:,}")
    print(f"  Missing {DEMAND_COL}: {missing_demand:,}")
    if missing_demand:
        raise ValueError(f"{DEMAND_COL} has missing values; cannot simulate inventory.")

    # 5. Reproducible simulated inventory ---------------------------------
    # Sort by keys first so results do not depend on the row order of the CSVs.
    df = df.sort_values(KEYS).reset_index(drop=True)
    rng = np.random.default_rng(RANDOM_SEED)

    df["simulated_coverage_days"] = rng.uniform(
        MIN_COVERAGE_DAYS, MAX_COVERAGE_DAYS, size=len(df)
    ).round(1)
    df["simulated_inventory_units"] = np.maximum(
        MIN_STOCK_UNITS,
        np.ceil(df[DEMAND_COL] * df["simulated_coverage_days"]),
    ).astype(int)
    df["inventory_source"] = (
        f"SIMULATED (seed={RANDOM_SEED}, coverage {MIN_COVERAGE_DAYS}-{MAX_COVERAGE_DAYS} days; not real stock data)"
    )

    # 6. Assumed unit cost -------------------------------------------------
    df["assumed_unit_cost"] = (df["latest_sell_price"] * COST_RATIO).round(2)
    df["cost_source"] = (
        f"ASSUMED (cost ratio={COST_RATIO} x selling price; NOT actual Walmart cost data)"
    )

    # 7. Save --------------------------------------------------------------
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)

    # 8. Report ------------------------------------------------------------
    print(f"\nSaved {len(df):,} records to {OUTPUT_PATH.relative_to(PROJECT_ROOT)}")
    print(f"Columns ({len(df.columns)}): {list(df.columns)}")

    print("\n[Missing values per column]")
    na = df.isna().sum()
    na = na[na > 0]
    print(na.to_string() if len(na) else "  None")

    print("\n[Simulated inventory summary]")
    print(df[["simulated_coverage_days", "simulated_inventory_units"]].describe().round(2).to_string())

    print("\n[Sample rows]")
    sample_cols = KEYS + [
        DEMAND_COL,
        "latest_sell_price",
        "simulated_coverage_days",
        "simulated_inventory_units",
        "assumed_unit_cost",
    ]
    print(df[sample_cols].head(10).to_string(index=False))

    print("\nNOTE: inventory is SIMULATED and unit cost is ASSUMED. Neither is real Walmart data.")


if __name__ == "__main__":
    main()

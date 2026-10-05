"""
Step 11: Exploratory data analysis on data/processed/promotion_inputs.csv.

Reads : data/processed/promotion_inputs.csv       (read only)
Writes: reports/figures/*.png
        data/processed/eda_summary.txt

DATA LABELS
- Sales / demand / price: derived from the Walmart M5 dataset.
- Inventory: SIMULATED (M5 has no stock levels).
- Unit cost: ASSUMED (selling price x a cost ratio), NOT actual Walmart cost.

CAUTION: this is exploratory analysis. Correlations describe patterns in
this data only; they do not show that price or any discount caused a change
in demand.
"""

import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # save files only; no pop-up windows
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
# Leave as None for auto-detection, or type the exact column name to override.
RECENT_SALES_COL = None     # units sold in the most recent 28 days
PREVIOUS_SALES_COL = None   # units sold in the 28 days before that

LOW_STOCK_DAYS = 7          # coverage below this = potential stockout risk
HIGH_STOCK_DAYS = 35        # coverage above this = potential excess stock
MIN_PREV_UNITS = 10         # ignore % changes when previous sales are tiny
TOP_N = 15
SCATTER_SAMPLE = 5000
RANDOM_SEED = 42

PROJECT_ROOT = Path(__file__).resolve().parents[2]
INPUT_PATH = PROJECT_ROOT / "data" / "processed" / "promotion_inputs.csv"
SUMMARY_PATH = PROJECT_ROOT / "data" / "processed" / "eda_summary.txt"
FIG_DIR = PROJECT_ROOT / "reports" / "figures"

DEMAND_COL = "average_daily_units"
PRICE_COL = "latest_sell_price"
INV_COL = "simulated_inventory_units"
COST_COL = "assumed_unit_cost"

SIM_NOTE = "SIMULATED inventory (not real stock data)"
COST_NOTE = "ASSUMED unit cost (not actual Walmart cost)"

summary_lines = []


def log(text=""):
    """Print and remember a line for eda_summary.txt."""
    print(text)
    summary_lines.append(str(text))


def section(title):
    log()
    log("=" * 70)
    log(title)
    log("=" * 70)


def find_col(columns, include, exclude=""):
    """First column whose name matches the `include` regex and not `exclude`."""
    for c in columns:
        name = c.lower()
        if re.search(include, name) and not (exclude and re.search(exclude, name)):
            return c
    return None


def save_fig(fig, filename):
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    path = FIG_DIR / filename
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)
    log(f"  [figure saved] {path.relative_to(PROJECT_ROOT)}")


def fmt(df):
    return df.to_string(index=False)


def main():
    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"{INPUT_PATH} not found. Finish Step 10 first.")

    df = pd.read_csv(INPUT_PATH)
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)

    log("Step 11: Exploratory data analysis")
    log(f"Input file: {INPUT_PATH.relative_to(PROJECT_ROOT)}")
    log(f"Labels: inventory = {SIM_NOTE}; cost = {COST_NOTE}")
    log("Caution: correlations here do not prove causation, and no discount")
    log("effect is measured in this step.")

    # -- check required columns ------------------------------------------
    for col in ["item_id", "store_id", DEMAND_COL, PRICE_COL, INV_COL]:
        if col not in df.columns:
            raise ValueError(f"Missing column '{col}'. Columns found: {list(df.columns)}")

    log(f"\nRows: {len(df):,}   Columns ({len(df.columns)}): {list(df.columns)}")

    # -- detect recent / previous 28-day sales columns -------------------
    recent_col = RECENT_SALES_COL or find_col(
        df.columns, r"28", r"prev|prior|change|pct|growth"
    )
    prev_col = PREVIOUS_SALES_COL or find_col(df.columns, r"prev|prior")

    if recent_col is None:
        df["recent_28d_units"] = df[DEMAND_COL] * 28
        recent_col = "recent_28d_units"
        log(f"\nNo recent 28-day sales column found; using {DEMAND_COL} x 28 instead.")
    if prev_col is not None and prev_col == recent_col:
        prev_col = None
    log(f"\nDetected recent 28-day sales column  : {recent_col}")
    log(f"Detected previous 28-day sales column: {prev_col if prev_col else 'NONE (demand-change analysis will be skipped)'}")

    # -- category / department / state (use existing columns if present) --
    if "cat_id" not in df.columns:
        df["cat_id"] = df["item_id"].str.split("_").str[0]
    if "dept_id" not in df.columns:
        df["dept_id"] = df["item_id"].str.split("_").str[:2].str.join("_")
    if "state_id" not in df.columns:
        df["state_id"] = df["store_id"].str.split("_").str[0]

    # -- safe demand-change columns --------------------------------------
    has_change = prev_col is not None
    if has_change:
        recent = df[recent_col].astype(float)
        prev = df[prev_col].astype(float)
        df["change_units"] = recent - prev
        # Percent change only where previous sales are > 0 (else undefined)
        df["change_pct"] = np.where(prev > 0, (recent - prev) / prev * 100, np.nan)
        df["prev_zero_flag"] = prev == 0

    # ======================================================================
    section("1. DATA QUALITY")
    miss = df.isna().sum()
    miss = miss[miss > 0]
    log("Missing values per column:")
    log(miss.to_string() if len(miss) else "  None")
    log(f"Duplicate item_id + store_id rows: {int(df.duplicated(['item_id', 'store_id']).sum()):,}")
    log(f"Rows with zero average daily demand: {int((df[DEMAND_COL] == 0).sum()):,}")

    # ======================================================================
    section("2. OVERALL RECENT SALES AND DEMAND")
    total_recent = df[recent_col].sum()
    log(f"Total units, recent 28 days (all product-stores): {total_recent:,.0f}")
    log(f"Mean average daily demand per product-store     : {df[DEMAND_COL].mean():.3f} units/day")
    log(f"Median average daily demand per product-store   : {df[DEMAND_COL].median():.3f} units/day")
    log(f"Total average daily units across all rows       : {df[DEMAND_COL].sum():,.1f} units/day")
    log("\nDemand distribution (units/day):")
    log(df[DEMAND_COL].describe(percentiles=[0.25, 0.5, 0.75, 0.9, 0.99]).round(3).to_string())

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(np.log1p(df[DEMAND_COL]), bins=60, color="steelblue")
    ax.set_xlabel("log(1 + average daily units)")
    ax.set_ylabel("Number of product-store rows")
    ax.set_title("Distribution of average daily demand (log scale)")
    save_fig(fig, "01_demand_distribution.png")

    # ======================================================================
    section(f"3. HIGHEST RECENT 28-DAY SALES (top {TOP_N})")
    top_rows = df.nlargest(TOP_N, recent_col)[["item_id", "store_id", recent_col, DEMAND_COL]]
    log("Top product-store combinations:")
    log(fmt(top_rows))

    top_items = (df.groupby("item_id")[recent_col].sum()
                 .sort_values(ascending=False).head(TOP_N).reset_index())
    log("\nTop items summed across all stores:")
    log(fmt(top_items))

    fig, ax = plt.subplots(figsize=(9, 6))
    labels = top_rows["item_id"] + " @ " + top_rows["store_id"]
    ax.barh(labels[::-1], top_rows[recent_col][::-1], color="seagreen")
    ax.set_xlabel("Units sold, recent 28 days")
    ax.set_title(f"Top {TOP_N} product-store combinations by recent sales")
    save_fig(fig, "02_top_product_store_sales.png")

    # ======================================================================
    section("4. DEMAND CHANGE (recent 28 days vs previous 28 days)")
    if has_change:
        log("Percent change is left blank where previous sales were 0.")
        log("Percent-change rankings only include rows with previous sales >= "
            f"{MIN_PREV_UNITS} units, so tiny bases do not dominate.")
        n_prev_zero = int(df["prev_zero_flag"].sum())
        n_new = int((df["prev_zero_flag"] & (df[recent_col] > 0)).sum())
        log(f"\nRows with zero previous sales: {n_prev_zero:,} "
            f"(of which {n_new:,} have sales in the recent period)")

        up = df.nlargest(TOP_N, "change_units")[["item_id", "store_id", prev_col, recent_col, "change_units"]]
        down = df.nsmallest(TOP_N, "change_units")[["item_id", "store_id", prev_col, recent_col, "change_units"]]
        log(f"\nLargest increases in units (top {TOP_N}):")
        log(fmt(up))
        log(f"\nLargest decreases in units (top {TOP_N}):")
        log(fmt(down))

        eligible = df[df[prev_col] >= MIN_PREV_UNITS]
        log(f"\nRows eligible for % ranking: {len(eligible):,}")
        if len(eligible):
            log("\nLargest % increases (eligible rows):")
            log(fmt(eligible.nlargest(TOP_N, "change_pct")[["item_id", "store_id", prev_col, recent_col, "change_pct"]].round(1)))
            log("\nLargest % decreases (eligible rows):")
            log(fmt(eligible.nsmallest(TOP_N, "change_pct")[["item_id", "store_id", prev_col, recent_col, "change_pct"]].round(1)))

        log("\nOverall change in units (all rows):")
        log(df["change_units"].describe().round(2).to_string())
        log(f"Rows up: {int((df['change_units'] > 0).sum()):,}   "
            f"down: {int((df['change_units'] < 0).sum()):,}   "
            f"flat: {int((df['change_units'] == 0).sum()):,}")

        fig, ax = plt.subplots(figsize=(8, 5))
        clipped = df["change_units"].clip(df["change_units"].quantile(0.01),
                                          df["change_units"].quantile(0.99))
        ax.hist(clipped, bins=80, color="darkorange")
        ax.axvline(0, color="black", linewidth=1)
        ax.set_xlabel("Change in units (recent 28d minus previous 28d), 1st-99th percentile")
        ax.set_ylabel("Number of product-store rows")
        ax.set_title("Distribution of demand change")
        save_fig(fig, "03_demand_change_distribution.png")
    else:
        log("Skipped: no previous-period sales column was detected.")
        log("Set PREVIOUS_SALES_COL in the config block if one exists.")

    # ======================================================================
    section("5. PRICE DISTRIBUTION (latest selling price)")
    price = df[PRICE_COL]
    log(f"Missing prices: {int(price.isna().sum()):,}")
    log(price.describe(percentiles=[0.25, 0.5, 0.75, 0.9, 0.99]).round(2).to_string())
    if COST_COL in df.columns:
        log(f"\n{COST_NOTE}:")
        log(df[COST_COL].describe().round(2).to_string())

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    axes[0].hist(price.dropna(), bins=60, color="slateblue")
    axes[0].set_title("Selling price (all rows)")
    axes[0].set_xlabel("Price")
    axes[0].set_ylabel("Number of product-store rows")
    axes[1].hist(np.log1p(price.dropna()), bins=60, color="slateblue")
    axes[1].set_title("Selling price (log scale)")
    axes[1].set_xlabel("log(1 + price)")
    save_fig(fig, "04_price_distribution.png")

    # ======================================================================
    section("6. DEMAND BY CATEGORY AND DEPARTMENT")
    by_cat = df.groupby("cat_id").agg(
        rows=("item_id", "size"),
        recent_28d_units=(recent_col, "sum"),
        mean_daily_demand=(DEMAND_COL, "mean"),
        mean_price=(PRICE_COL, "mean"),
    ).round(2).reset_index()
    by_dept = df.groupby("dept_id").agg(
        rows=("item_id", "size"),
        recent_28d_units=(recent_col, "sum"),
        mean_daily_demand=(DEMAND_COL, "mean"),
        mean_price=(PRICE_COL, "mean"),
    ).round(2).reset_index().sort_values("recent_28d_units", ascending=False)
    by_state = df.groupby("state_id")[recent_col].sum().reset_index()

    log("By category:")
    log(fmt(by_cat))
    log("\nBy department:")
    log(fmt(by_dept))
    log("\nBy state (recent 28-day units):")
    log(fmt(by_state))

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    axes[0].bar(by_cat["cat_id"], by_cat["recent_28d_units"], color="teal")
    axes[0].set_title("Recent 28-day units by category")
    axes[0].set_ylabel("Units")
    d = by_dept.sort_values("recent_28d_units")
    axes[1].barh(d["dept_id"], d["recent_28d_units"], color="teal")
    axes[1].set_title("Recent 28-day units by department")
    save_fig(fig, "05_demand_by_category_department.png")

    # ======================================================================
    section(f"7. {SIM_NOTE.upper()}: COVERAGE, LOW STOCK, HIGH STOCK")
    log("Inventory below is SIMULATED in Step 10. Findings here describe the")
    log("simulation settings, not real Walmart stock.")
    demand = df[DEMAND_COL]
    df["coverage_days"] = np.where(demand > 0, df[INV_COL] / demand, np.nan)
    cov = df["coverage_days"]

    n_zero_demand = int((demand == 0).sum())
    n_low = int((cov < LOW_STOCK_DAYS).sum())
    n_high = int((cov > HIGH_STOCK_DAYS).sum())
    n_mid = int(cov.between(LOW_STOCK_DAYS, HIGH_STOCK_DAYS).sum())
    log(f"\nCoverage days = simulated inventory / average daily units (rows with demand > 0).")
    log(f"Potential low stock  (< {LOW_STOCK_DAYS} days) : {n_low:,}")
    log(f"Within range ({LOW_STOCK_DAYS}-{HIGH_STOCK_DAYS} days)      : {n_mid:,}")
    log(f"Potential high stock (> {HIGH_STOCK_DAYS} days): {n_high:,}")
    log(f"Zero recent demand but simulated stock > 0 : {int(((demand == 0) & (df[INV_COL] > 0)).sum()):,}"
        f"  (coverage undefined; counted of {n_zero_demand:,} zero-demand rows)")
    log("\nCoverage-day distribution:")
    log(cov.describe().round(2).to_string())

    log("\nPotential low / high stock share by category:")
    stock_by_cat = df.assign(
        low=(cov < LOW_STOCK_DAYS), high=(cov > HIGH_STOCK_DAYS)
    ).groupby("cat_id")[["low", "high"]].mean().mul(100).round(1)
    stock_by_cat.columns = ["pct_low_stock", "pct_high_stock"]
    log(stock_by_cat.reset_index().to_string(index=False))

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(cov.dropna().clip(upper=cov.quantile(0.99)), bins=60, color="firebrick")
    ax.axvline(LOW_STOCK_DAYS, color="black", linestyle="--", label=f"low < {LOW_STOCK_DAYS}d")
    ax.axvline(HIGH_STOCK_DAYS, color="black", linestyle=":", label=f"high > {HIGH_STOCK_DAYS}d")
    ax.set_xlabel("Coverage days (SIMULATED inventory / average daily units)")
    ax.set_ylabel("Number of product-store rows")
    ax.set_title("SIMULATED inventory coverage (not real stock data)")
    ax.legend()
    save_fig(fig, "06_simulated_inventory_coverage.png")

    # ======================================================================
    section("8. RELATIONSHIPS (association only, not causation)")
    rel_cols = [DEMAND_COL, PRICE_COL, recent_col]
    if has_change:
        rel_cols += ["change_units", "change_pct"]
    corr = df[rel_cols].corr(method="spearman").round(3)
    log("Spearman rank correlation (robust to skewed data):")
    log(corr.to_string())
    log("\nReading this table: a value near +1 or -1 means the two columns move")
    log("together in this dataset. It does NOT show that price changes cause")
    log("demand changes, and it says nothing about the effect of discounts.")
    log("Other factors (item type, store, season, events) are not controlled for.")

    rng = np.random.default_rng(RANDOM_SEED)
    sample = df.sample(n=min(SCATTER_SAMPLE, len(df)), random_state=RANDOM_SEED)

    n_plots = 2 if has_change else 1
    fig, axes = plt.subplots(1, n_plots, figsize=(6 * n_plots, 5), squeeze=False)
    axes[0][0].scatter(sample[PRICE_COL], sample[DEMAND_COL], s=6, alpha=0.4)
    axes[0][0].set_xscale("log")
    axes[0][0].set_yscale("symlog")
    axes[0][0].set_xlabel("Latest selling price (log scale)")
    axes[0][0].set_ylabel("Average daily units (symlog scale)")
    axes[0][0].set_title("Demand vs price (sample)")
    if has_change:
        axes[0][1].scatter(sample[PRICE_COL], sample["change_units"], s=6, alpha=0.4, color="darkorange")
        axes[0][1].axhline(0, color="black", linewidth=1)
        axes[0][1].set_xscale("log")
        axes[0][1].set_yscale("symlog")
        axes[0][1].set_xlabel("Latest selling price (log scale)")
        axes[0][1].set_ylabel("Change in units (symlog scale)")
        axes[0][1].set_title("Demand change vs price (sample)")
    save_fig(fig, "07_demand_price_relationships.png")

    if has_change:
        fig, ax = plt.subplots(figsize=(7, 5))
        ax.scatter(sample[DEMAND_COL], sample["change_units"], s=6, alpha=0.4, color="purple")
        ax.axhline(0, color="black", linewidth=1)
        ax.set_xscale("symlog")
        ax.set_yscale("symlog")
        ax.set_xlabel("Average daily units (symlog scale)")
        ax.set_ylabel("Change in units (symlog scale)")
        ax.set_title("Demand change vs demand level (sample)")
        save_fig(fig, "08_demand_change_vs_demand.png")

    # ======================================================================
    section("9. NOTES FOR LATER STEPS")
    log("- Inventory and unit cost are simulated/assumed; label them in any report.")
    log("- Price and demand patterns above are descriptive; no discount effect is estimated.")
    log("- No forecasting was done in this step.")

    SUMMARY_PATH.write_text("\n".join(summary_lines), encoding="utf-8")
    print(f"\nSummary saved to {SUMMARY_PATH.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
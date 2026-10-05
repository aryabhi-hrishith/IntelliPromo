"""
Step 14 (roadmap Steps 19-25): Rule-based promotion and inventory recommendations.

Reads (read only):
    data/processed/promotion_inputs.csv
    data/processed/forecast_predictions.csv   (schema/key check only by default)
Writes (only this file):
    data/processed/promotion_recommendations.csv

IMPORTANT LABELS
- Demand: default is average_daily_units, a HISTORICAL PROXY. It is NOT an ML forecast.
- Inventory: SIMULATED in Step 10 (M5 has no stock data).
- Unit cost: ASSUMED in Step 10 (not actual Walmart cost).
- No promotion lift is estimated. A "candidate discount" is a suggestion for
  human review, not a claim that demand or profit will rise.
- All thresholds below are PROTOTYPE ASSUMPTIONS, not tuned or validated.
"""

import re
import textwrap
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# CONFIGURATION  (prototype assumptions; change freely)
# ---------------------------------------------------------------------------
# "historical_proxy"   : demand = average_daily_units  (default, recommended)
# "backtest_prototype" : for the ~90 series with Step 13 test predictions, demand =
#                        mean of rf_pred over the 28 test days. Labeled as a
#                        BACKTEST average, NOT a live forecast.
DEMAND_MODE = "historical_proxy"

CANDIDATE_DISCOUNTS = [0, 5, 10, 15]     # percent

LOW_COVERAGE_DAYS = 7                    # below this: possible stockout
HIGH_COVERAGE_DAYS = 30                  # at/above this: possible excess stock
PROMO_MIN_COVERAGE_DAYS = 14             # decline-driven promotion needs this much stock

# Excess-stock discount tiers: (coverage days at or above, candidate discount %)
EXCESS_DISCOUNT_TIERS = [(30, 5), (35, 10), (40, 15)]
DECLINE_CANDIDATE_DISCOUNT = 5

MIN_MARGIN_PCT = 5.0                     # discounted margin must be at least this %
DECLINE_PCT_THRESHOLD = 20.0             # % drop vs previous 28 days
MIN_PREV_UNITS = 10                      # ignore % change when previous sales are tiny

# Leave None for auto-detection of the 28-day sales columns, or type the exact name.
RECENT_SALES_COL = None
PREVIOUS_SALES_COL = None

KEYS = ["item_id", "store_id"]
DEMAND_COL = "average_daily_units"
PRICE_COL = "latest_sell_price"
COST_COL = "assumed_unit_cost"
STOCK_COL = "simulated_inventory_units"

PROJECT_ROOT = Path(__file__).resolve().parents[2]
INPUTS_PATH = PROJECT_ROOT / "data" / "processed" / "promotion_inputs.csv"
PRED_PATH = PROJECT_ROOT / "data" / "processed" / "forecast_predictions.csv"
OUT_PATH = PROJECT_ROOT / "data" / "processed" / "promotion_recommendations.csv"

PROXY_LABEL = "HISTORICAL_PROXY (average_daily_units; not an ML forecast)"
BACKTEST_LABEL = "BACKTEST_RF_MEAN_PROTOTYPE (28-day test-window average; not a live forecast)"
DATA_LABELS = "demand: proxy/prototype, not a live forecast; stock: SIMULATED; cost: ASSUMED; no promotion lift estimated"


def find_col(columns, include, exclude=""):
    """First column whose lower-case name matches `include` and not `exclude` (regex)."""
    for c in columns:
        name = c.lower()
        if re.search(include, name) and not (exclude and re.search(exclude, name)):
            return c
    return None


def show_schema(df, label):
    print(f"\n[{label}] {df.shape[0]:,} rows x {df.shape[1]} columns")
    for c in df.columns:
        print(f"  {c:<32}{str(df[c].dtype)}")


def main():
    print("Step 14: generating rule-based recommendations")
    print(f"Demand mode: {DEMAND_MODE}")
    if DEMAND_MODE not in ("historical_proxy", "backtest_prototype"):
        raise ValueError("DEMAND_MODE must be 'historical_proxy' or 'backtest_prototype'.")
    if OUT_PATH in (INPUTS_PATH, PRED_PATH):
        raise RuntimeError("Output path matches an input path; refusing to continue.")
    if not INPUTS_PATH.exists():
        raise FileNotFoundError(f"{INPUTS_PATH} not found. Finish Step 10 first.")

    # ------------------------------------------------------------------
    # 1. Load and inspect inputs
    # ------------------------------------------------------------------
    df = pd.read_csv(INPUTS_PATH, low_memory=False)
    show_schema(df, "promotion_inputs.csv")
    for col in KEYS + [DEMAND_COL, PRICE_COL, COST_COL, STOCK_COL]:
        if col not in df.columns:
            raise ValueError(f"Missing column '{col}'. Columns found: {list(df.columns)}")

    pred = None
    if PRED_PATH.exists():
        pred = pd.read_csv(PRED_PATH, low_memory=False)
        show_schema(pred, "forecast_predictions.csv")
    else:
        print("\nforecast_predictions.csv not found (fine in historical_proxy mode).")
        if DEMAND_MODE == "backtest_prototype":
            raise FileNotFoundError("backtest_prototype mode needs forecast_predictions.csv")

    # ------------------------------------------------------------------
    # 2. Key checks
    # ------------------------------------------------------------------
    dup_inputs = int(df.duplicated(KEYS).sum())
    print("\n[Key checks]")
    print(f"  promotion_inputs duplicate {KEYS}: {dup_inputs:,}")
    if dup_inputs:
        raise ValueError("Duplicate item_id + store_id rows in promotion_inputs.csv.")

    rf_by_series = None
    if pred is not None:
        for col in KEYS + ["target_date", "rf_pred"]:
            if col not in pred.columns:
                raise ValueError(f"forecast_predictions.csv missing column '{col}'.")
        dup_pred = int(pred.duplicated(KEYS + ["target_date"]).sum())
        print(f"  predictions duplicate {KEYS + ['target_date']}: {dup_pred:,}")
        if dup_pred:
            raise ValueError("Duplicate prediction rows; cannot aggregate safely.")
        rf_by_series = pred.groupby(KEYS, as_index=False).agg(
            backtest_rf_mean=("rf_pred", "mean"),
            backtest_days=("rf_pred", "size"),
        )
        check = rf_by_series.merge(df[KEYS], on=KEYS, how="left", indicator=True)
        unmatched = int((check["_merge"] == "left_only").sum())
        print(f"  prediction series: {len(rf_by_series):,}   "
              f"matched to inputs: {len(rf_by_series) - unmatched:,}   unmatched: {unmatched:,}")
        print(f"  input rows WITHOUT test predictions: {len(df) - (len(rf_by_series) - unmatched):,} "
              "(these always use the historical proxy)")
        print("  Test predictions cover past dates only; they are NOT used as tomorrow's forecast.")

    # ------------------------------------------------------------------
    # 3. Choose the demand figure
    # ------------------------------------------------------------------
    df["demand_proxy"] = df[DEMAND_COL].astype(float)
    df["demand_used"] = df["demand_proxy"]
    df["demand_source"] = PROXY_LABEL
    if DEMAND_MODE == "backtest_prototype":
        df = df.merge(rf_by_series[KEYS + ["backtest_rf_mean"]], on=KEYS, how="left")
        has_bt = df["backtest_rf_mean"].notna()
        df.loc[has_bt, "demand_used"] = df.loc[has_bt, "backtest_rf_mean"].clip(lower=0)
        df.loc[has_bt, "demand_source"] = BACKTEST_LABEL
        print(f"\nPROTOTYPE MODE: {int(has_bt.sum()):,} rows use the backtest RF average. "
              "This is not a live forecast.")

    if "cat_id" not in df.columns:
        df["cat_id"] = df["item_id"].str.split("_").str[0]
    if "dept_id" not in df.columns:
        df["dept_id"] = df["item_id"].str.split("_").str[:2].str.join("_")

    n = len(df)
    price = pd.to_numeric(df[PRICE_COL], errors="coerce").to_numpy(dtype=float)
    cost = pd.to_numeric(df[COST_COL], errors="coerce").to_numpy(dtype=float)
    demand = pd.to_numeric(df["demand_used"], errors="coerce").to_numpy(dtype=float)
    stock = pd.to_numeric(df[STOCK_COL], errors="coerce").to_numpy(dtype=float)

    # ------------------------------------------------------------------
    # 4. Validity checks
    # ------------------------------------------------------------------
    bad_price = np.isnan(price) | (price <= 0)
    bad_cost = np.isnan(cost) | (cost < 0)
    bad_demand = np.isnan(demand) | (demand < 0)
    bad_stock = np.isnan(stock) | (stock < 0)
    if "has_price" in df.columns:
        bad_price = bad_price | ~df["has_price"].astype(bool).to_numpy()
    valid_input = ~(bad_price | bad_cost | bad_demand | bad_stock)

    print("\n[Input validity checks]")
    print(f"  Missing or non-positive price : {int(bad_price.sum()):,}")
    print(f"  Missing or negative cost      : {int(bad_cost.sum()):,}")
    print(f"  Missing or negative demand    : {int(bad_demand.sum()):,}")
    print(f"  Missing or negative stock     : {int(bad_stock.sum()):,}")
    print(f"  Rows with zero demand         : {int((demand == 0).sum()):,}")
    print(f"  Rows usable for evaluation    : {int(valid_input.sum()):,} of {n:,}")

    # ------------------------------------------------------------------
    # 5. Coverage and current margin
    # ------------------------------------------------------------------
    with np.errstate(divide="ignore", invalid="ignore"):
        coverage = np.where(demand > 0, stock / demand, np.nan)  # NaN when demand is 0
        cur_margin = price - cost
        cur_margin_pct = np.where(price > 0, cur_margin / price * 100, np.nan)

    # ------------------------------------------------------------------
    # 6. Discount scenarios (margin % = (price - cost) / price x 100)
    # ------------------------------------------------------------------
    scen_price, scen_margin, scen_pct, scen_valid = {}, {}, {}, {}
    rejected_parts = []
    for d in CANDIDATE_DISCOUNTS:
        p_d = np.round(price * (1 - d / 100.0), 2)
        with np.errstate(divide="ignore", invalid="ignore"):
            m_d = p_d - cost
            pct_d = np.where(p_d > 0, m_d / p_d * 100, np.nan)
        below_cost = p_d < cost
        below_min = pct_d < MIN_MARGIN_PCT
        ok = valid_input & ~below_cost & ~below_min
        scen_price[d], scen_margin[d], scen_pct[d], scen_valid[d] = p_d, m_d, pct_d, ok
        if d > 0:
            rejected_parts.append(np.where(
                ~valid_input, "",
                np.where(below_cost, f"{d}%: below assumed cost; ",
                         np.where(below_min, f"{d}%: margin under {MIN_MARGIN_PCT:g}%; ", ""))
            ))
    rejected_text = np.array(["".join(parts).strip() for parts in zip(*rejected_parts)])

    # ------------------------------------------------------------------
    # 7. Demand-decline flag (needs recent and previous 28-day sales columns)
    # ------------------------------------------------------------------
    skip_cols = r"chang|pct|growth|avg|average|daily|mean|per_day"
    recent_col = RECENT_SALES_COL or find_col(df.columns, r"28", r"prev|prior|" + skip_cols)
    prev_col = PREVIOUS_SALES_COL or find_col(df.columns, r"prev|prior", skip_cols)
    decline_pct = np.full(n, np.nan)
    if recent_col and prev_col and recent_col != prev_col:
        rec = pd.to_numeric(df[recent_col], errors="coerce").to_numpy(dtype=float)
        prv = pd.to_numeric(df[prev_col], errors="coerce").to_numpy(dtype=float)
        with np.errstate(divide="ignore", invalid="ignore"):
            decline_pct = np.where(prv >= MIN_PREV_UNITS, (rec - prv) / prv * 100, np.nan)
        print(f"\n[Demand change] recent column: {recent_col}; previous column: {prev_col}")
    else:
        print("\n[Demand change] recent/previous 28-day columns not found; decline rule skipped.")
        print("  Set RECENT_SALES_COL / PREVIOUS_SALES_COL at the top if they exist.")
    decline_flag = np.where(np.isnan(decline_pct), False, decline_pct <= -DECLINE_PCT_THRESHOLD)

    # ------------------------------------------------------------------
    # 8. Candidate discount choices (largest discount that passes margin rules
    #    and does not exceed the rule's tier)
    # ------------------------------------------------------------------
    def best_valid(max_discount):
        chosen = np.zeros(n)
        for d in sorted(x for x in CANDIDATE_DISCOUNTS if x > 0):
            chosen = np.where((d <= max_discount) & scen_valid[d], d, chosen)
        return chosen

    excess_tier = np.zeros(n)
    for threshold, disc in sorted(EXCESS_DISCOUNT_TIERS):
        excess_tier = np.where(coverage >= threshold, disc, excess_tier)
    excess_choice = best_valid(excess_tier)
    decline_tier = np.where(decline_flag & (coverage >= PROMO_MIN_COVERAGE_DAYS),
                            DECLINE_CANDIDATE_DISCOUNT, 0)
    decline_choice = best_valid(decline_tier)

    # ------------------------------------------------------------------
    # 9. Rules -> recommendation + explanation (first matching rule wins)
    # ------------------------------------------------------------------
    recs, explanations, selected = [], [], np.zeros(n)
    src = df["demand_source"].to_numpy()
    for i in range(n):
        if not valid_input[i]:
            problems = [name for name, bad in (("price", bad_price[i]), ("cost", bad_cost[i]),
                                               ("demand", bad_demand[i]), ("stock", bad_stock[i])) if bad]
            recs.append("Cannot evaluate (missing/invalid inputs)")
            explanations.append(f"Invalid or missing: {', '.join(problems)}. No rule was applied.")
            continue

        facts = (f"Demand {demand[i]:.2f} units/day ({'prototype backtest average' if 'BACKTEST' in src[i] else 'historical proxy, not a forecast'}); "
                 f"SIMULATED stock {int(stock[i]):,} units; price {price[i]:.2f}, "
                 f"ASSUMED cost {cost[i]:.2f} (current margin {cur_margin_pct[i]:.1f}%).")
        note = ""
        if decline_flag[i]:
            note = (f" Recent 28-day units fell {abs(decline_pct[i]):.0f}% versus the previous 28 days "
                    f"(threshold {DECLINE_PCT_THRESHOLD:g}%).")

        if demand[i] == 0:
            recs.append("Review low-demand item (no sales in window)")
            explanations.append(facts + " No recent demand, so coverage days are undefined and no discount "
                                "is evaluated. Review whether the item is still active.")
        elif coverage[i] < LOW_COVERAGE_DAYS:
            recs.append("Review replenishment - avoid promotion")
            explanations.append(facts + f" Coverage is {coverage[i]:.1f} days, below {LOW_COVERAGE_DAYS} days, "
                                "so a stockout is possible. Avoid promoting until stock is confirmed." + note)
        elif coverage[i] >= HIGH_COVERAGE_DAYS:
            if excess_choice[i] > 0:
                d = int(excess_choice[i])
                selected[i] = d
                recs.append("Review excess inventory - consider promotion")
                explanations.append(
                    facts + f" Coverage is {coverage[i]:.1f} days (at or above {HIGH_COVERAGE_DAYS}), a possible excess. "
                    f"A {d}% candidate discount gives price {scen_price[d][i]:.2f} and margin "
                    f"{scen_pct[d][i]:.1f}% under the assumed cost, so it passes the margin checks. "
                    "This is a candidate for human review only; no demand lift is estimated." + note)
            else:
                recs.append("Review excess inventory - promotion blocked by margin rules")
                why = rejected_text[i] if rejected_text[i] else "no tier discount applies"
                explanations.append(
                    facts + f" Coverage is {coverage[i]:.1f} days (possible excess), but no discount passes the "
                    f"margin checks ({why}). Consider non-price actions." + note)
        elif decline_flag[i]:
            if decline_choice[i] > 0:
                d = int(decline_choice[i])
                selected[i] = d
                recs.append("Review demand decline - consider promotion")
                explanations.append(
                    facts + note + f" Coverage is {coverage[i]:.1f} days, enough stock to consider a {d}% "
                    f"candidate discount (price {scen_price[d][i]:.2f}, margin {scen_pct[d][i]:.1f}%, "
                    "passes margin checks). Review the cause of the decline first; no demand lift is estimated.")
            else:
                recs.append("Review demand decline")
                explanations.append(facts + note + f" Coverage is {coverage[i]:.1f} days; no promotion is "
                                    "suggested (insufficient stock or margin rules). Review the cause of the decline.")
        else:
            recs.append("No action - coverage within range")
            explanations.append(facts + f" Coverage is {coverage[i]:.1f} days, between {LOW_COVERAGE_DAYS} "
                                f"and {HIGH_COVERAGE_DAYS}; no rule triggered.")

    # ------------------------------------------------------------------
    # 10. Build and save the output table
    # ------------------------------------------------------------------
    out = pd.DataFrame({
        "item_id": df["item_id"], "store_id": df["store_id"],
        "cat_id": df["cat_id"], "dept_id": df["dept_id"],
        "latest_sell_price": price,
        "assumed_unit_cost": cost,
        "demand_used_units_per_day": demand,
        "demand_source": df["demand_source"],
        "simulated_inventory_units": stock,
        "coverage_days": coverage,
        "current_unit_margin": cur_margin,
        "current_margin_pct": cur_margin_pct,
        "demand_change_pct": decline_pct,
    })
    for d in CANDIDATE_DISCOUNTS:
        out[f"price_disc_{d}"] = scen_price[d]
        out[f"unit_margin_disc_{d}"] = scen_margin[d]
        out[f"margin_pct_disc_{d}"] = scen_pct[d]
        out[f"valid_disc_{d}"] = scen_valid[d]
    out["rejected_scenarios"] = rejected_text
    out["selected_candidate_discount_pct"] = selected
    sel_price = np.full(n, np.nan)
    sel_pct = np.full(n, np.nan)
    for d in CANDIDATE_DISCOUNTS:
        if d > 0:
            m = selected == d
            sel_price[m] = scen_price[d][m]
            sel_pct[m] = scen_pct[d][m]
    out["selected_discounted_price"] = sel_price
    out["selected_discounted_margin_pct"] = sel_pct
    out["recommendation"] = recs
    out["explanation"] = explanations
    out["data_labels"] = DATA_LABELS

    num_cols = out.select_dtypes(include="float").columns
    out[num_cols] = out[num_cols].round(3)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_PATH, index=False)

    # ------------------------------------------------------------------
    # 11. Report
    # ------------------------------------------------------------------
    print(f"\nSaved {len(out):,} rows to {OUT_PATH.relative_to(PROJECT_ROOT)}")
    print(f"Columns ({len(out.columns)}): {list(out.columns)}")

    print("\n[Recommendation counts]")
    print(out["recommendation"].value_counts().to_string())

    print("\n[Selected candidate discount counts] (0 = none)")
    print(out["selected_candidate_discount_pct"].value_counts().sort_index().to_string())

    print("\n[Scenario validity: rows passing the margin rules]")
    for d in CANDIDATE_DISCOUNTS:
        print(f"  {d:>2}% discount: {int(scen_valid[d].sum()):,} of {n:,}")

    print("\n[Missing values in key output columns]")
    check_cols = ["latest_sell_price", "assumed_unit_cost", "demand_used_units_per_day",
                  "simulated_inventory_units", "coverage_days", "recommendation", "explanation"]
    na = out[check_cols].isna().sum()
    print(na.to_string())
    print("  (coverage_days is blank only where demand is 0 or inputs are invalid)")

    print("\n[Sample recommendations: first example of each type]")
    for rec_name, grp in out.groupby("recommendation"):
        r = grp.iloc[0]
        print(f"\n- {rec_name}  ({r['item_id']} @ {r['store_id']})")
        print(f"  price {r['latest_sell_price']}, assumed cost {r['assumed_unit_cost']}, "
              f"coverage {r['coverage_days']}, candidate discount {r['selected_candidate_discount_pct']}%")
        print(textwrap.fill(r["explanation"], width=100, initial_indent="  ", subsequent_indent="  "))

    print("\nREMINDERS: demand is a historical proxy (not a forecast); stock is SIMULATED; "
          "cost is ASSUMED; thresholds are prototype assumptions; no promotion lift is estimated.")


if __name__ == "__main__":
    main()
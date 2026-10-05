"""
Step 12 (roadmap Step 13): Prepare time-series forecasting data.

Reads (read only):
    data/external/sales_train_validation.csv
    data/external/calendar.csv
Writes (only this file):
    data/processed/forecasting_dataset.csv

Each output row means:
    "It is the end of day t (the FEATURE DATE). Everything up to and including
     day t is known. Predict the units sold on day t+1 (the TARGET DATE)."

No model is trained here.
"""

from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
STORES = ["CA_1", "TX_1", "WI_1"]   # one store per state
ITEMS_PER_CATEGORY = 10             # top items per category, by TRAINING-period sales
TEST_DAYS = 28                      # last 28 target dates are the test set
LAGS = [1, 2, 6, 13, 27]            # lag_0 (today) is always added
ROLL_MEAN_WINDOWS = [7, 14, 28]
ROLL_STD_WINDOW = 7
KEEP_FROM_FIRST_SALE = True         # drop days before an item's first sale in a store

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SALES_PATH = PROJECT_ROOT / "data" / "external" / "sales_train_validation.csv"
CAL_PATH = PROJECT_ROOT / "data" / "external" / "calendar.csv"
OUT_PATH = PROJECT_ROOT / "data" / "processed" / "forecasting_dataset.csv"

KEYS = ["item_id", "store_id"]


def main():
    print("Step 12: preparing forecasting dataset...", flush=True)

    for p in (SALES_PATH, CAL_PATH):
        if not p.exists():
            raise FileNotFoundError(f"Missing input file: {p}")

    # ------------------------------------------------------------------
    # 1. Calendar: map d_1, d_2, ... to real dates
    # ------------------------------------------------------------------
    cal = pd.read_csv(CAL_PATH, parse_dates=["date"])
    needed = {"d", "date", "wday", "month"}
    if not needed <= set(cal.columns):
        raise ValueError(f"calendar.csv is missing columns: {needed - set(cal.columns)}")

    cal["day_num"] = cal["d"].str[2:].astype(int)
    cal = cal.sort_values("day_num").reset_index(drop=True)
    gaps = cal["date"].diff().dropna().dt.days
    if not (gaps == 1).all():
        raise ValueError("Calendar dates are not consecutive; cannot align d_N safely.")
    date_of = dict(zip(cal["d"], cal["date"]))

    # ------------------------------------------------------------------
    # 2. Sales: read compactly, keep only the chosen stores
    # ------------------------------------------------------------------
    header = pd.read_csv(SALES_PATH, nrows=0).columns
    day_cols = sorted([c for c in header if c.startswith("d_")], key=lambda c: int(c[2:]))
    missing_days = [c for c in day_cols if c not in date_of]
    if missing_days:
        raise ValueError(f"{len(missing_days)} sales columns have no calendar date, e.g. {missing_days[:3]}")

    dtypes = {c: "int16" for c in day_cols}   # saves memory
    sales = pd.read_csv(SALES_PATH, dtype=dtypes)
    print(f"Sales file: {len(sales):,} rows, {len(day_cols)} day columns "
          f"({day_cols[0]} to {day_cols[-1]})")
    sales = sales[sales["store_id"].isin(STORES)].copy()
    if sales.empty:
        raise ValueError(f"No rows found for stores {STORES}")

    all_dates = [date_of[c] for c in day_cols]
    test_target_start = all_dates[-TEST_DAYS]          # first test target date
    train_cols = [c for c in day_cols if date_of[c] < test_target_start]
    print(f"Date range in sales: {all_dates[0].date()} to {all_dates[-1].date()}")
    print(f"Test target dates start: {test_target_start.date()} (last {TEST_DAYS} days)")

    # ------------------------------------------------------------------
    # 3. Choose a reproducible subset using TRAINING-period sales only
    # ------------------------------------------------------------------
    sales["train_units"] = sales[train_cols].sum(axis=1)
    ranking = (
        sales.groupby(["cat_id", "item_id"], as_index=False)["train_units"].sum()
        .sort_values(["cat_id", "train_units", "item_id"], ascending=[True, False, True])
    )
    chosen = ranking.groupby("cat_id").head(ITEMS_PER_CATEGORY)
    chosen_items = set(chosen["item_id"])
    sales = sales[sales["item_id"].isin(chosen_items)].copy()
    print(f"Selected {len(chosen_items)} items x {len(STORES)} stores = "
          f"{len(sales)} series (top {ITEMS_PER_CATEGORY} per category by training-period units)")

    # ------------------------------------------------------------------
    # 4. Wide -> long format (one row per series per day)
    # ------------------------------------------------------------------
    long = sales.melt(
        id_vars=["item_id", "dept_id", "cat_id", "store_id"],
        value_vars=day_cols,
        var_name="d",
        value_name="units",
    )
    long["units"] = long["units"].astype("int32")
    long["date"] = long["d"].map(date_of)
    long["day_num"] = long["d"].str[2:].astype(int)
    long = long.sort_values(KEYS + ["day_num"]).reset_index(drop=True)

    counts = long.groupby(KEYS).size()
    if not (counts == len(day_cols)).all():
        raise ValueError("Some series do not have one row per day.")
    print(f"Long format: {len(long):,} rows")
        # Untouched copy of actual sales, used later to verify the lag/target alignment
    all_days = long[KEYS + ["date", "units"]].copy()

    # ------------------------------------------------------------------
    # 5. Features (use only information up to and including day t)
    # ------------------------------------------------------------------
    g = long.groupby(KEYS)["units"]
    long["lag_0"] = long["units"]                       # sales on day t
    for k in LAGS:
        long[f"lag_{k}"] = g.shift(k)                   # sales on day t-k
    for w in ROLL_MEAN_WINDOWS:
        long[f"rolling_mean_{w}"] = g.transform(lambda s, w=w: s.rolling(w, min_periods=w).mean())
    long[f"rolling_std_{ROLL_STD_WINDOW}"] = g.transform(
        lambda s: s.rolling(ROLL_STD_WINDOW, min_periods=ROLL_STD_WINDOW).std()
    )

    # ------------------------------------------------------------------
    # 6. Target = next-day sales; calendar facts about the target day
    # ------------------------------------------------------------------
    long["target_units"] = g.shift(-1)
    long["target_date"] = long.groupby(KEYS)["date"].shift(-1)

    long["target_dayofweek"] = long["target_date"].dt.dayofweek
    long["target_month"] = long["target_date"].dt.month
    long["target_is_weekend"] = (long["target_dayofweek"] >= 5).astype("float")

    cal_idx = cal.set_index("date")
    event_cols = [c for c in ("event_name_1", "event_name_2") if c in cal_idx.columns]
    if event_cols:
        has_event = cal_idx[event_cols].notna().any(axis=1).astype(int)
        long["target_has_event"] = long["target_date"].map(has_event)
    else:
        long["target_has_event"] = 0.0

    long["target_snap"] = np.nan                         # SNAP food-benefit day for the store's state
    for state in ["CA", "TX", "WI"]:
        col = f"snap_{state}"
        if col in cal_idx.columns:
            mask = long["store_id"].str.startswith(state)
            long.loc[mask, "target_snap"] = long.loc[mask, "target_date"].map(cal_idx[col])

    # ------------------------------------------------------------------
    # 7. Clean up: drop warm-up rows, pre-launch rows and the last day
    # ------------------------------------------------------------------
    first_sale = (long[long["units"] > 0].groupby(KEYS)["date"].min()
                  .rename("first_sale_date").reset_index())
    n_series_before = long[KEYS].drop_duplicates().shape[0]
    long = long.merge(first_sale, on=KEYS, how="inner")
    n_no_sales = n_series_before - len(first_sale)
    if n_no_sales:
        print(f"Dropped {n_no_sales} series with no sales at all.")

    feature_cols = (
        ["lag_0"] + [f"lag_{k}" for k in LAGS]
        + [f"rolling_mean_{w}" for w in ROLL_MEAN_WINDOWS]
        + [f"rolling_std_{ROLL_STD_WINDOW}"]
        + ["target_dayofweek", "target_month", "target_is_weekend",
           "target_has_event", "target_snap"]
    )
    if KEEP_FROM_FIRST_SALE:
        long = long[long["date"] >= long["first_sale_date"]]

    before = len(long)
    out = long.dropna(subset=feature_cols + ["target_units", "target_date"]).copy()
    print(f"Rows dropped for missing lags/windows/target: {before - len(out):,}")

    # ------------------------------------------------------------------
    # 8. Chronological split on the TARGET date
    # ------------------------------------------------------------------
    out["split"] = np.where(out["target_date"] >= test_target_start, "test", "train")

    train_max = out.loc[out["split"] == "train", "target_date"].max()
    test_min = out.loc[out["split"] == "test", "target_date"].min()
    if not train_max < test_min:
        raise RuntimeError("Leakage: training targets overlap the test period.")

    # Tidy column order / types
    int_cols = ["lag_0", "target_units", "target_dayofweek", "target_month",
                "target_is_weekend", "target_has_event", "target_snap"] + [f"lag_{k}" for k in LAGS]
    for c in int_cols:
        out[c] = out[c].astype("int32")
    for c in [f"rolling_mean_{w}" for w in ROLL_MEAN_WINDOWS] + [f"rolling_std_{ROLL_STD_WINDOW}"]:
        out[c] = out[c].round(4)

    id_cols = ["item_id", "store_id", "cat_id", "dept_id", "date", "target_date"]
    out = out[id_cols + feature_cols + ["target_units", "split"]].reset_index(drop=True)

    # ------------------------------------------------------------------
    # 9. Alignment checks against the original sales values
    # ------------------------------------------------------------------
    base = all_days   # full, unfiltered history, so lags that reach before first sale can be verified

    def mismatches(date_series, value_series):
        chk = out[KEYS].copy()
        chk["date"] = date_series
        chk["value"] = value_series
        chk = chk.merge(base, on=KEYS + ["date"], how="left")
        return int((chk["value"] != chk["units"]).sum()), int(chk["units"].isna().sum())

    # target_units must equal the real sales on target_date
    bad_target, _ = mismatches(out["target_date"], out["target_units"])
    # lag_6 must equal the real sales 6 days before the feature date
    bad_l6, _ = mismatches(out["date"] - pd.Timedelta(days=6), out["lag_6"])
    # lag_27 likewise
    bad_l27, _ = mismatches(out["date"] - pd.Timedelta(days=27), out["lag_27"])
    # target_date must be exactly one day after date
    bad_gap = int(((out["target_date"] - out["date"]).dt.days != 1).sum())

    print("\n[Alignment checks] (all should be 0)")
    print(f"  target_units != actual sales on target_date : {bad_target}")
    print(f"  lag_6 != actual sales 6 days earlier        : {bad_l6}")
    print(f"  lag_27 != actual sales 27 days earlier      : {bad_l27}")
    print(f"  rows where target_date - date != 1 day      : {bad_gap}")
    if bad_target or bad_l6 or bad_l27 or bad_gap:
        raise RuntimeError("Alignment check failed; not saving.")

    # ------------------------------------------------------------------
    # 10. Save and report
    # ------------------------------------------------------------------
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_PATH, index=False)

    train = out[out["split"] == "train"]
    test = out[out["split"] == "test"]

    print(f"\nSaved {len(out):,} rows to {OUT_PATH.relative_to(PROJECT_ROOT)}")
    print("\n[Row counts]")
    print(f"  Series (item x store): {out[KEYS].drop_duplicates().shape[0]}")
    print(f"  Train rows: {len(train):,}")
    print(f"  Test rows : {len(test):,}")

    print("\n[Date ranges]")
    print(f"  Train feature dates: {train['date'].min().date()} to {train['date'].max().date()}")
    print(f"  Train target dates : {train['target_date'].min().date()} to {train['target_date'].max().date()}")
    print(f"  Test feature dates : {test['date'].min().date()} to {test['date'].max().date()}")
    print(f"  Test target dates  : {test['target_date'].min().date()} to {test['target_date'].max().date()}")

    print("\n[Selected stores]", STORES)
    print("[Selected items by category]")
    for cat, grp in out.groupby("cat_id"):
        print(f"  {cat}: {sorted(grp['item_id'].unique())}")

    print("\n[Feature columns]")
    for c in feature_cols:
        print(f"  {c}")
    print("[Target column]  target_units  (units sold on target_date = feature date + 1 day)")

    print("\n[Missing values per column]")
    na = out.isna().sum()
    print(na[na > 0].to_string() if (na > 0).any() else "  None")

    print("\n[Target statistics (units/day)]")
    print(out.groupby("split")["target_units"].describe().round(2).to_string())
    zero_share = (out["target_units"] == 0).mean() * 100
    print(f"  Share of rows with target = 0: {zero_share:.1f}%")

    # Visual boundary check for one series
    first = out[KEYS].iloc[0]
    one = out[(out["item_id"] == first["item_id"]) & (out["store_id"] == first["store_id"])]
    boundary = pd.concat([one[one["split"] == "train"].tail(2), one[one["split"] == "test"].head(2)])
    show = ["item_id", "store_id", "date", "target_date", "lag_0", "lag_6",
            "rolling_mean_7", "target_units", "split"]
    print("\n[Boundary check: last 2 train rows and first 2 test rows of one series]")
    print(boundary[show].to_string(index=False))

    print("\n[Sample rows]")
    print(out.head(5)[show].to_string(index=False))

    print("\nNo model was trained. Inputs were not modified.")


if __name__ == "__main__":
    main()
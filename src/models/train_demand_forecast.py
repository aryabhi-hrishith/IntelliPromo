"""
Step 13 (roadmap Steps 14-17): Train and evaluate demand forecasts.

Reads (read only): data/processed/forecasting_dataset.csv
Writes:
    data/processed/forecast_predictions.csv
    reports/forecast_model_metrics.txt
    reports/figures/forecast_comparison.png

Models compared on the SAME test rows:
    1. Naive baseline : tomorrow's sales = today's sales (lag_0)
    2. Random Forest  : scikit-learn RandomForestRegressor

The split is chronological (made in Step 12). Nothing is shuffled.
Results describe this one test window only; they do not measure any
promotion or discount effect.
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # save the picture to a file; no pop-up window
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
RANDOM_SEED = 42
TARGET_COL = "target_units"
NAIVE_COL = "lag_0"             # units sold on the last known day (feature date t)
TEST_DAYS_FALLBACK = 28         # only used if the file has no 'split' column

# Moderate size so it trains in about a minute on a laptop.
RF_PARAMS = dict(
    n_estimators=100,
    max_depth=12,
    min_samples_leaf=10,
    n_jobs=-1,                  # use all CPU cores; set to 2 for a lighter load
    random_state=RANDOM_SEED,
)

# Columns that must never be used as features
ID_COLS = ["item_id", "store_id", "cat_id", "dept_id", "state_id", "id"]
DATE_COLS = ["date", "target_date", "first_sale_date"]
OTHER_EXCLUDED = ["split", "d", "day_num"]

PROJECT_ROOT = Path(__file__).resolve().parents[2]
INPUT_PATH = PROJECT_ROOT / "data" / "processed" / "forecasting_dataset.csv"
PRED_PATH = PROJECT_ROOT / "data" / "processed" / "forecast_predictions.csv"
METRICS_PATH = PROJECT_ROOT / "reports" / "forecast_model_metrics.txt"
FIG_PATH = PROJECT_ROOT / "reports" / "figures" / "forecast_comparison.png"

report_lines = []


def log(text=""):
    """Print a line and remember it for the metrics text file."""
    print(text)
    report_lines.append(str(text))


def get_metrics(y_true, y_pred):
    """MAE and RMSE (both in 'units sold per day')."""
    mae = float(mean_absolute_error(y_true, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    return {"mae": mae, "rmse": rmse}


def main():
    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"{INPUT_PATH} not found. Finish Step 12 first.")

    # ------------------------------------------------------------------
    # 1. Load and inspect the actual schema
    # ------------------------------------------------------------------
    df = pd.read_csv(INPUT_PATH, parse_dates=["date", "target_date"], low_memory=False)
    log("Step 13: training and evaluating demand forecasts")
    log(f"Input: {INPUT_PATH.relative_to(PROJECT_ROOT)}")
    log(f"Dataset shape: {df.shape[0]:,} rows x {df.shape[1]} columns")
    log(f"Columns found: {list(df.columns)}")

    for col in (TARGET_COL, NAIVE_COL, "target_date"):
        if col not in df.columns:
            raise ValueError(
                f"Required column '{col}' not found. Columns are: {list(df.columns)}. "
                "Tell me the actual names and I will adjust the script."
            )

    # ------------------------------------------------------------------
    # 2. Chronological split (use the Step 12 'split' column if present)
    # ------------------------------------------------------------------
    if "split" in df.columns and {"train", "test"} <= set(df["split"].unique()):
        split_source = "'split' column from Step 12"
    else:
        cutoff = np.sort(df["target_date"].unique())[-TEST_DAYS_FALLBACK]
        df["split"] = np.where(df["target_date"] >= cutoff, "test", "train")
        split_source = f"fallback: last {TEST_DAYS_FALLBACK} target dates are the test set"
    log(f"Split taken from: {split_source}")

    train_max = df.loc[df["split"] == "train", "target_date"].max()
    test_min = df.loc[df["split"] == "test", "target_date"].min()
    if not train_max < test_min:
        raise RuntimeError("Training targets overlap the test period (time leakage). Stopping.")

    # ------------------------------------------------------------------
    # 3. Choose feature columns (numeric; no identifiers, dates, target, split)
    # ------------------------------------------------------------------
    excluded = set(ID_COLS + DATE_COLS + OTHER_EXCLUDED + [TARGET_COL])
    feature_cols = [
        c for c in df.columns
        if c not in excluded
        and pd.api.types.is_numeric_dtype(df[c])
        and not c.lower().startswith("target_units")
    ]
    # Safety check: no feature may simply be a copy of the target
    for c in feature_cols:
        if df[c].equals(df[TARGET_COL]):
            raise RuntimeError(f"Feature '{c}' is identical to the target (leakage). Stopping.")
    if NAIVE_COL not in feature_cols:
        raise RuntimeError(f"{NAIVE_COL} is not among the usable features: {feature_cols}")

    # Drop any rows with missing feature/target values (Step 12 should leave none)
    before = len(df)
    df = df.dropna(subset=feature_cols + [TARGET_COL])
    log(f"Rows dropped for missing values: {before - len(df):,}")

    train = df[df["split"] == "train"]
    test = df[df["split"] == "test"].copy()
    log(f"\nFeatures used ({len(feature_cols)}): {feature_cols}")
    log("Excluded: identifiers, dates, split flag and the target.")
    log(f"Train rows: {len(train):,}   Test rows: {len(test):,}")
    log(f"Train target dates: {train['target_date'].min().date()} to {train['target_date'].max().date()}")
    log(f"Test target dates : {test['target_date'].min().date()} to {test['target_date'].max().date()}")
    log(f"Series (item x store) in test: {test[['item_id', 'store_id']].drop_duplicates().shape[0]}")

    X_train, y_train = train[feature_cols], train[TARGET_COL]
    X_test, y_test = test[feature_cols], test[TARGET_COL]

    # ------------------------------------------------------------------
    # 4. Model 1: naive baseline (no training; copy the last known sales)
    # ------------------------------------------------------------------
    naive_pred = test[NAIVE_COL].astype(float).to_numpy()

    # ------------------------------------------------------------------
    # 5. Model 2: Random Forest (fitted on training rows only)
    # ------------------------------------------------------------------
    log("\nTraining RandomForestRegressor (this can take a minute)...")
    rf = RandomForestRegressor(**RF_PARAMS)
    rf.fit(X_train, y_train)
    rf_pred = rf.predict(X_test)

    # ------------------------------------------------------------------
    # 6. Evaluate both models on the SAME test rows
    # ------------------------------------------------------------------
    naive_m = get_metrics(y_test, naive_pred)
    rf_m = get_metrics(y_test, rf_pred)
    mean_actual = float(y_test.mean())
    zero_share = float((y_test == 0).mean() * 100)

    log("\n" + "=" * 60)
    log("TEST-SET RESULTS (same rows for both models; units per day)")
    log("=" * 60)
    log(f"Test rows: {len(test):,}   Mean actual demand: {mean_actual:.3f}   "
        f"Rows with zero sales: {zero_share:.1f}%")
    log(f"{'Model':<34}{'MAE':>10}{'RMSE':>10}")
    log(f"{'Naive baseline (' + NAIVE_COL + ')':<34}{naive_m['mae']:>10.4f}{naive_m['rmse']:>10.4f}")
    log(f"{'Random Forest':<34}{rf_m['mae']:>10.4f}{rf_m['rmse']:>10.4f}")

    mae_change = (naive_m["mae"] - rf_m["mae"]) / naive_m["mae"] * 100
    rmse_change = (naive_m["rmse"] - rf_m["rmse"]) / naive_m["rmse"] * 100
    log(f"\nRandom Forest vs naive: MAE {mae_change:+.1f}% , RMSE {rmse_change:+.1f}% "
        "(positive = Random Forest error is lower)")

    rf_better_mae = rf_m["mae"] < naive_m["mae"]
    rf_better_rmse = rf_m["rmse"] < naive_m["rmse"]
    if rf_better_mae and rf_better_rmse:
        verdict = "On this test set, Random Forest had lower MAE and lower RMSE than the naive baseline."
    elif not rf_better_mae and not rf_better_rmse:
        verdict = ("On this test set, the naive baseline had lower or equal MAE and RMSE; "
                   "Random Forest did not beat it.")
    else:
        better_on = "MAE" if rf_better_mae else "RMSE"
        worse_on = "RMSE" if rf_better_mae else "MAE"
        verdict = (f"Mixed result: Random Forest was better on {better_on} but not on {worse_on}, "
                   "so neither model is clearly better on this test set.")
    log(f"Verdict: {verdict}")

    # Per-category breakdown (helps see where errors come from)
    if "cat_id" in test.columns:
        test["naive_pred"] = naive_pred
        test["rf_pred"] = rf_pred
        log("\nPer-category test errors:")
        log(f"{'Category':<12}{'Rows':>8}{'Naive MAE':>12}{'RF MAE':>10}{'Naive RMSE':>12}{'RF RMSE':>10}")
        for cat, grp in test.groupby("cat_id"):
            n = get_metrics(grp[TARGET_COL], grp["naive_pred"])
            r = get_metrics(grp[TARGET_COL], grp["rf_pred"])
            log(f"{cat:<12}{len(grp):>8,}{n['mae']:>12.4f}{r['mae']:>10.4f}{n['rmse']:>12.4f}{r['rmse']:>10.4f}")

    # Feature importance (how much the forest relied on each input; not causation)
    imp = pd.Series(rf.feature_importances_, index=feature_cols).sort_values(ascending=False)
    log("\nRandom Forest feature importances (top 10):")
    for name, val in imp.head(10).items():
        log(f"  {name:<20}{val:.3f}")

    # ------------------------------------------------------------------
    # 7. Save predictions
    # ------------------------------------------------------------------
    pred_df = test[["item_id", "store_id"]].copy()
    for c in ("cat_id", "dept_id"):
        if c in test.columns:
            pred_df[c] = test[c]
    pred_df["date"] = test["date"]
    pred_df["target_date"] = test["target_date"]
    pred_df["actual_units"] = y_test.to_numpy()
    pred_df["naive_pred"] = naive_pred
    pred_df["rf_pred"] = np.round(rf_pred, 4)
    pred_df["naive_abs_error"] = (pred_df["actual_units"] - pred_df["naive_pred"]).abs()
    pred_df["rf_abs_error"] = (pred_df["actual_units"] - pred_df["rf_pred"]).abs()
    pred_df = pred_df.sort_values(["item_id", "store_id", "target_date"])

    PRED_PATH.parent.mkdir(parents=True, exist_ok=True)
    pred_df.to_csv(PRED_PATH, index=False)
    log(f"\nSaved predictions: {PRED_PATH.relative_to(PROJECT_ROOT)} ({len(pred_df):,} rows)")

    # ------------------------------------------------------------------
    # 8. Graph: actual vs both models
    # ------------------------------------------------------------------
    FIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(2, 1, figsize=(11, 9))

    daily = pred_df.groupby("target_date")[["actual_units", "naive_pred", "rf_pred"]].sum()
    axes[0].plot(daily.index, daily["actual_units"], label="Actual", color="black", linewidth=2)
    axes[0].plot(daily.index, daily["naive_pred"], label="Naive (lag_0)", linestyle="--", color="tab:orange")
    axes[0].plot(daily.index, daily["rf_pred"], label="Random Forest", linestyle="-.", color="tab:blue")
    axes[0].set_title("Test period: total daily units across all selected product-stores")
    axes[0].set_ylabel("Units per day (sum)")
    axes[0].legend()
    axes[0].tick_params(axis="x", rotation=30)

    top = pred_df.groupby(["item_id", "store_id"])["actual_units"].sum().idxmax()
    one = pred_df[(pred_df["item_id"] == top[0]) & (pred_df["store_id"] == top[1])]
    axes[1].plot(one["target_date"], one["actual_units"], label="Actual", color="black", linewidth=2, marker="o", markersize=3)
    axes[1].plot(one["target_date"], one["naive_pred"], label="Naive (lag_0)", linestyle="--", color="tab:orange")
    axes[1].plot(one["target_date"], one["rf_pred"], label="Random Forest", linestyle="-.", color="tab:blue")
    axes[1].set_title(f"Highest-selling single series in test: {top[0]} @ {top[1]}")
    axes[1].set_ylabel("Units per day")
    axes[1].legend()
    axes[1].tick_params(axis="x", rotation=30)

    fig.suptitle("Next-day demand: actual vs predictions (one-step-ahead, chronological test set)", y=1.0)
    fig.tight_layout()
    fig.savefig(FIG_PATH, dpi=130)
    plt.close(fig)
    log(f"Saved graph: {FIG_PATH.relative_to(PROJECT_ROOT)}")

    # ------------------------------------------------------------------
    # 9. Interpretation and limitations (written to the metrics file)
    # ------------------------------------------------------------------
    log("\n" + "=" * 60)
    log("HOW TO READ THESE RESULTS")
    log("=" * 60)
    log("- MAE: average size of the miss, in units per day. RMSE: similar, but")
    log("  large misses count more, so spikes in demand raise it.")
    log("- The naive baseline copies today's sales. A model is only useful if it")
    log("  beats this simple rule; the verdict above says whether it did here.")
    log("\nLIMITATIONS")
    log("- One-step-ahead (next day) forecasts only; not a multi-week forecast.")
    log("- One test window of 28 days, 90 product-store series, one random seed,")
    log("  no cross-validation and no hyperparameter tuning. A different window")
    log("  could rank the models differently.")
    log("- Many rows have zero sales (intermittent demand), which makes daily")
    log("  errors noisy for any model.")
    log("- Prices, discounts and inventory are not model inputs, so these results")
    log("  say nothing about promotion effects. Feature importance is not causation.")
    log("- Identifiers were excluded, so the model cannot learn item-specific")
    log("  behaviour beyond what recent sales and calendar features reveal.")

    METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    METRICS_PATH.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"\nSaved metrics summary: {METRICS_PATH.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
"""
Reproducible Demand Forecasting Benchmark and Model Selection Service (Stage 6A).

Implements strict chronological train/validation/test splitting, feature engineering with zero future-data leakage,
baseline models (Naive, Moving Average), Random Forest regression, validation-based model selection,
and robust out-of-sample MAE/RMSE evaluation metrics.
"""

from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any, Tuple
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error


def prepare_time_series_features(df_sales: pd.DataFrame) -> pd.DataFrame:
    """
    Prepare demand forecasting features (lag-1, rolling 7-day moving average)
    per (store_id, item_id) series in strict chronological order without future-data leakage.
    """
    if df_sales.empty or not all(c in df_sales.columns for c in ["date", "item_id", "quantity"]):
        return pd.DataFrame()

    df = df_sales.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date", "item_id", "quantity"])
    
    # Ensure store_id exists
    if "store_id" not in df.columns:
        df["store_id"] = "DEFAULT_STORE"

    # Sort chronologically by date per store and item
    df = df.sort_values(by=["store_id", "item_id", "date"]).reset_index(drop=True)

    # Aggregate by date, store_id, item_id in case of duplicate transaction lines on same day
    grouped = df.groupby(["store_id", "item_id", "date"], as_index=False)["quantity"].sum()
    grouped = grouped.rename(columns={"quantity": "target_units"})

    # Compute lag and rolling features per group
    feature_rows = []
    for (store_id, item_id), group in grouped.groupby(["store_id", "item_id"]):
        group = group.sort_values("date").reset_index(drop=True)
        # Shift target by 1 day to create lag_1 (previous day's sales)
        group["lag_1"] = group["target_units"].shift(1)
        # 7-day rolling mean of past sales (excluding current day)
        group["rolling_mean_7"] = group["target_units"].shift(1).rolling(window=7, min_periods=1).mean()
        
        feature_rows.append(group)

    if not feature_rows:
        return pd.DataFrame()

    combined = pd.concat(feature_rows, ignore_index=True)
    # Drop rows where lag_1 is NaN (first day of series)
    combined = combined.dropna(subset=["lag_1", "rolling_mean_7"])
    return combined


def evaluate_forecasting_benchmark(df_sales: pd.DataFrame) -> Dict[str, Any]:
    """
    Run chronological train/validation/test benchmark across models:
      1. Naive Baseline (lag_1)
      2. Moving Average Baseline (rolling_mean_7)
      3. Random Forest Regressor
    Uses validation set for model selection, and evaluates selected model on held-out test set.
    """
    df_feat = prepare_time_series_features(df_sales)
    if df_feat.empty or len(df_feat) < 10:
        return {
            "status": "insufficient_history",
            "message": "Insufficient sales history or series length for rigorous forecasting benchmark (minimum 10 valid feature rows required).",
            "evaluated_observations": len(df_feat),
            "eligible_series": 0,
        }

    # Chronological split by date quantiles
    all_dates = np.sort(df_feat["date"].unique())
    if len(all_dates) < 5:
        return {
            "status": "insufficient_history",
            "message": "Too few unique dates for chronological train/validation/test splitting.",
            "evaluated_observations": len(df_feat),
            "eligible_series": df_feat[["store_id", "item_id"]].drop_duplicates().shape[0],
        }

    train_end_idx = int(len(all_dates) * 0.70)
    val_end_idx = int(len(all_dates) * 0.85)

    train_cutoff = all_dates[max(0, train_end_idx - 1)]
    val_cutoff = all_dates[max(0, val_end_idx - 1)]

    df_train = df_feat[df_feat["date"] <= train_cutoff]
    df_val = df_feat[(df_feat["date"] > train_cutoff) & (df_feat["date"] <= val_cutoff)]
    df_test = df_feat[df_feat["date"] > val_cutoff]

    # Fallback if validation or test is empty
    if df_val.empty or df_test.empty:
        # Split simply by row index chronologically
        n = len(df_feat)
        train_end = int(n * 0.70)
        val_end = int(n * 0.85)
        df_train = df_feat.iloc[:train_end]
        df_val = df_feat.iloc[train_end:val_end]
        df_test = df_feat.iloc[val_end:]

    features = ["lag_1", "rolling_mean_7"]
    target = "target_units"

    # Evaluate models on Validation Set (for Model Selection)
    val_metrics = {}
    
    # 1. Naive Validation
    if not df_val.empty:
        y_val_true = df_val[target].to_numpy()
        y_val_naive = df_val["lag_1"].to_numpy()
        val_metrics["naive"] = {
            "mae": float(mean_absolute_error(y_val_true, y_val_naive)),
            "rmse": float(np.sqrt(mean_squared_error(y_val_true, y_val_naive))),
        }

        # 2. Moving Average Validation
        y_val_ma = df_val["rolling_mean_7"].to_numpy()
        val_metrics["moving_average"] = {
            "mae": float(mean_absolute_error(y_val_true, y_val_ma)),
            "rmse": float(np.sqrt(mean_squared_error(y_val_true, y_val_ma))),
        }

        # 3. Random Forest Validation
        rf_model = None
        if len(df_train) >= 15:
            try:
                rf = RandomForestRegressor(n_estimators=50, max_depth=10, random_state=42, n_jobs=-1)
                rf.fit(df_train[features], df_train[target])
                y_val_rf = rf.predict(df_val[features])
                val_metrics["random_forest"] = {
                    "mae": float(mean_absolute_error(y_val_true, y_val_rf)),
                    "rmse": float(np.sqrt(mean_squared_error(y_val_true, y_val_rf))),
                }
                rf_model = rf
            except Exception:
                pass

    # Model Selection using Validation MAE
    selected_model_name = "moving_average"
    best_val_mae = float("inf")
    for mname, metrics in val_metrics.items():
        if metrics["mae"] < best_val_mae:
          best_val_mae = metrics["mae"]
          selected_model_name = mname

    # Fit final model on Train + Validation, evaluate on Test Set (held-out)
    df_train_val = pd.concat([df_train, df_val], ignore_index=True)
    
    test_metrics = {}
    if not df_test.empty:
        y_test_true = df_test[target].to_numpy()
        
        # Naive Test
        y_test_naive = df_test["lag_1"].to_numpy()
        test_metrics["naive"] = {
            "mae": float(mean_absolute_error(y_test_true, y_test_naive)),
            "rmse": float(np.sqrt(mean_squared_error(y_test_true, y_test_naive))),
        }

        # Moving Average Test
        y_test_ma = df_test["rolling_mean_7"].to_numpy()
        test_metrics["moving_average"] = {
            "mae": float(mean_absolute_error(y_test_true, y_test_ma)),
            "rmse": float(np.sqrt(mean_squared_error(y_test_true, y_test_ma))),
        }

        # Random Forest Test
        if len(df_train_val) >= 15:
            try:
                rf_final = RandomForestRegressor(n_estimators=50, max_depth=10, random_state=42, n_jobs=-1)
                rf_final.fit(df_train_val[features], df_train_val[target])
                y_test_rf = rf_final.predict(df_test[features])
                test_metrics["random_forest"] = {
                    "mae": float(mean_absolute_error(y_test_true, y_test_rf)),
                    "rmse": float(np.sqrt(mean_squared_error(y_test_true, y_test_rf))),
                }
            except Exception:
                pass

    selected_test_metrics = test_metrics.get(selected_model_name, test_metrics.get("moving_average", {"mae": 0.0, "rmse": 0.0}))
    baseline_test_metrics = test_metrics.get("naive", {"mae": 0.0, "rmse": 0.0})

    mae_improvement_pct = 0.0
    if baseline_test_metrics["mae"] > 0:
        mae_improvement_pct = round(((baseline_test_metrics["mae"] - selected_test_metrics["mae"]) / baseline_test_metrics["mae"]) * 100.0, 2)

    eligible_series_count = df_feat[["store_id", "item_id"]].drop_duplicates().shape[0]

    return {
        "status": "success",
        "selected_model": selected_model_name,
        "validation_metrics": val_metrics,
        "test_metrics": test_metrics,
        "selected_test_metrics": {
            "mae": round(selected_test_metrics["mae"], 4),
            "rmse": round(selected_test_metrics["rmse"], 4),
        },
        "baseline_test_metrics": {
            "mae": round(baseline_test_metrics["mae"], 4),
            "rmse": round(baseline_test_metrics["rmse"], 4),
        },
        "mae_improvement_pct": mae_improvement_pct,
        "eligible_series": eligible_series_count,
        "evaluated_observations": len(df_test),
        "train_observations": len(df_train),
        "validation_observations": len(df_val),
        "test_observations": len(df_test),
        "evaluation_window": {
            "start_date": str(df_test["date"].min().date()) if not df_test.empty else None,
            "end_date": str(df_test["date"].max().date()) if not df_test.empty else None,
        },
        "forecast_horizon_days": 1,
    }

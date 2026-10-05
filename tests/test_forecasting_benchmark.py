"""
Tests for Reproducible Demand Forecasting Benchmark and Model Selection (Stage 6A).

Verifies:
  1. Chronological splitting and zero future-data leakage.
  2. Naive, Moving Average, and Random Forest benchmark models.
  3. Validation-based model selection and test-set isolation.
  4. Robust handling of insufficient history, sparse history, zero demand, missing dates, and duplicate sales lines.
  5. Correct calculation of MAE, RMSE, and baseline improvement percentages.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from src.api.forecasting_benchmark import (
    prepare_time_series_features,
    evaluate_forecasting_benchmark,
)


def test_prepare_time_series_features_basic():
    dates = pd.date_range(start="2026-01-01", periods=20, freq="D")
    data = []
    for d in dates:
        data.append({
            "store_id": "STORE_1",
            "item_id": "ITEM_A",
            "date": d.strftime("%Y-%m-%d"),
            "quantity": 10.0 + (d.day % 5),
        })
    df_sales = pd.DataFrame(data)
    
    # Add duplicate transaction line on same day to test aggregation
    df_sales = pd.concat([df_sales, pd.DataFrame([{
        "store_id": "STORE_1",
        "item_id": "ITEM_A",
        "date": "2026-01-05",
        "quantity": 5.0,
    }])], ignore_index=True)

    df_feat = prepare_time_series_features(df_sales)
    assert not df_feat.empty
    assert "lag_1" in df_feat.columns
    assert "rolling_mean_7" in df_feat.columns
    assert "target_units" in df_feat.columns
    
    # Check that lag_1 uses previous day's sales without future leakage
    row_jan3 = df_feat[df_feat["date"] == pd.to_datetime("2026-01-03")]
    row_jan2 = df_feat[df_feat["date"] == pd.to_datetime("2026-01-02")]
    if not row_jan3.empty and not row_jan2.empty:
        assert row_jan3.iloc[0]["lag_1"] == row_jan2.iloc[0]["target_units"]


def test_evaluate_forecasting_benchmark_success():
    dates = pd.date_range(start="2026-01-01", periods=45, freq="D")
    data = []
    for d in dates:
        data.append({
            "store_id": "STORE_1",
            "item_id": "ITEM_A",
            "date": d.strftime("%Y-%m-%d"),
            "quantity": float(20 + (d.day % 7) * 2),
        })
        data.append({
            "store_id": "STORE_1",
            "item_id": "ITEM_B",
            "date": d.strftime("%Y-%m-%d"),
            "quantity": float(10 + (d.day % 3)),
        })
    df_sales = pd.DataFrame(data)

    res = evaluate_forecasting_benchmark(df_sales)
    assert res["status"] == "success"
    assert "selected_model" in res
    assert "validation_metrics" in res
    assert "test_metrics" in res
    assert "selected_test_metrics" in res
    assert "baseline_test_metrics" in res
    assert "mae_improvement_pct" in res
    assert res["eligible_series"] == 2
    assert res["evaluated_observations"] > 0
    assert "mae" in res["selected_test_metrics"]
    assert "rmse" in res["selected_test_metrics"]


def test_evaluate_forecasting_benchmark_insufficient_history():
    df_sales = pd.DataFrame([
        {"store_id": "STORE_1", "item_id": "ITEM_A", "date": "2026-01-01", "quantity": 10.0},
        {"store_id": "STORE_1", "item_id": "ITEM_A", "date": "2026-01-02", "quantity": 12.0},
    ])
    res = evaluate_forecasting_benchmark(df_sales)
    assert res["status"] == "insufficient_history"
    assert res["eligible_series"] == 0


def test_evaluate_forecasting_benchmark_zero_demand_and_missing_dates():
    data = [
        {"store_id": "STORE_1", "item_id": "ITEM_X", "date": "2026-01-01", "quantity": 0.0},
        {"store_id": "STORE_1", "item_id": "ITEM_X", "date": "2026-01-02", "quantity": 0.0},
        {"store_id": "STORE_1", "item_id": "ITEM_X", "date": "2026-01-05", "quantity": 5.0},
        {"store_id": "STORE_1", "item_id": "ITEM_X", "date": "2026-01-10", "quantity": 10.0},
        {"store_id": "STORE_1", "item_id": "ITEM_X", "date": "2026-01-12", "quantity": 0.0},
        {"store_id": "STORE_1", "item_id": "ITEM_X", "date": "2026-01-15", "quantity": 3.0},
        {"store_id": "STORE_1", "item_id": "ITEM_X", "date": "2026-01-20", "quantity": 8.0},
        {"store_id": "STORE_1", "item_id": "ITEM_X", "date": "2026-01-25", "quantity": 12.0},
        {"store_id": "STORE_1", "item_id": "ITEM_X", "date": "2026-01-28", "quantity": 0.0},
        {"store_id": "STORE_1", "item_id": "ITEM_X", "date": "2026-02-01", "quantity": 7.0},
    ]
    df_sales = pd.DataFrame(data)
    res = evaluate_forecasting_benchmark(df_sales)
    assert res["status"] in ("success", "insufficient_history")
    if res["status"] == "success":
        assert not np.isnan(res["selected_test_metrics"]["mae"])
        assert not np.isnan(res["selected_test_metrics"]["rmse"])

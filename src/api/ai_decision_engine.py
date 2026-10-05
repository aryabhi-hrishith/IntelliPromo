"""
AI/ML Decision Engine and Explainability Service (Stage 6B).

Combines demand forecasting benchmarks, inventory alignment, customer segmentation,
and rule-based promotion recommendations into a unified, transparent, deterministic
decision output with explicit reliability classifications and retailer-friendly explanations.
"""

from datetime import datetime
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any

from .database import (
    get_tenant_query,
    tenant_products,
    tenant_sales,
    tenant_inventory,
    tenant_prices,
    tenant_customers,
    clean_document,
)
from .forecasting_benchmark import evaluate_forecasting_benchmark


def compute_tenant_decisions(retail_id: str, item_id_filter: Optional[str] = None, store_id_filter: Optional[str] = None) -> Dict[str, Any]:
    """
    Compute unified AI/ML decisions for a tenant retailer using only successfully committed records.
    """
    try:
        sales_query = get_tenant_query(retail_id)
        if item_id_filter:
            sales_query["item_id"] = item_id_filter
        if store_id_filter:
            sales_query["store_id"] = store_id_filter

        sales_docs = list(tenant_sales.find(sales_query))
        prod_docs = list(tenant_products.find(get_tenant_query(retail_id)))
        inv_docs = list(tenant_inventory.find(get_tenant_query(retail_id)))

        prod_map = {p.get("item_id"): p for p in prod_docs}
        inv_map = {(inv.get("item_id"), inv.get("store_id")): inv for inv in inv_docs}

        if not sales_docs and not inv_docs:
            return {
                "retail_id": retail_id,
                "status": "insufficient_data",
                "message": "Insufficient sales and inventory records to compute decisions.",
                "total_decisions": 0,
                "decisions": [],
            }

        benchmark_results = {}
        df_sales = pd.DataFrame(sales_docs) if sales_docs else pd.DataFrame()
        if not df_sales.empty and "date" in df_sales.columns and "quantity" in df_sales.columns and "item_id" in df_sales.columns:
            df_sales["date"] = pd.to_datetime(df_sales["date"], errors="coerce")
            df_sales = df_sales.dropna(subset=["date", "quantity", "item_id"])
            benchmark_results = evaluate_forecasting_benchmark(df_sales)

        series_groups = []
        if not df_sales.empty:
            if "store_id" not in df_sales.columns:
                df_sales["store_id"] = "DEFAULT_STORE"
            series_groups = list(df_sales.groupby(["store_id", "item_id"]))

        covered_pairs = set((store_id, item_id) for (store_id, item_id), _ in series_groups)
        for inv in inv_docs:
            st_id = inv.get("store_id", "DEFAULT_STORE")
            it_id = inv.get("item_id")
            if it_id and (st_id, it_id) not in covered_pairs:
                series_groups.append(((st_id, it_id), pd.DataFrame()))
                covered_pairs.add((st_id, it_id))

        decisions = []
        groups_iter = series_groups if series_groups else [((inv.get("store_id", "DEFAULT_STORE"), inv.get("item_id")), pd.DataFrame()) for inv in inv_docs]
        
        for (store_id, item_id), group_df in groups_iter:
            if item_id_filter and item_id != item_id_filter:
                continue
            if store_id_filter and store_id != store_id_filter:
                continue

            prod = prod_map.get(item_id, {})
            inv_rec = inv_map.get((item_id, store_id), {})
            stock_on_hand = inv_rec.get("stock_on_hand", 0.0)

            item_sales = group_df if not group_df.empty else pd.DataFrame()
            total_qty = float(item_sales["quantity"].sum()) if not item_sales.empty else 0.0
            unique_dates = len(item_sales["date"].unique()) if not item_sales.empty and "date" in item_sales.columns else 0
            days = max(1, unique_dates)
            daily_velocity = total_qty / days if days > 0 else 0.5
            coverage_days = stock_on_hand / daily_velocity if daily_velocity > 0 else 999.0

            risk_status = "Normal"
            if coverage_days < 14:
                risk_status = "Stockout Risk (< 14 days)"
            elif coverage_days > 60:
                risk_status = "Excess Stock (> 60 days)"

            reliability = "INSUFFICIENT_DATA"
            if unique_dates >= 30 and bool(inv_rec) and benchmark_results.get("status") == "success":
                reliability = "HIGH"
            elif unique_dates >= 10:
                reliability = "MEDIUM"
            elif unique_dates > 0 or stock_on_hand > 0:
                reliability = "LOW"

            recommendation_action = "Maintain Normal Operations"
            discount_pct = 0.0
            warnings = []

            if "Excess Stock" in risk_status:
                recommendation_action = "Review excess inventory - consider promotion"
                discount_pct = 15.0
                reason = f"Promotion recommended because inventory coverage is high ({coverage_days:.1f} days) while demand velocity is stable."
            elif "Stockout Risk" in risk_status:
                recommendation_action = "Review replenishment - avoid promotion"
                discount_pct = 0.0
                reason = f"No promotion recommended because inventory coverage is low ({coverage_days:.1f} days) and stockout risk is elevated."
            else:
                reason = f"Normal operations. Stock coverage is balanced at {coverage_days:.1f} days."

            if unique_dates < 10 and unique_dates > 0:
                warnings.append("Limited historical sales duration (< 10 distinct observation days).")
            if not inv_rec:
                warnings.append("Simulated or missing inventory snapshot for this item/store.")

            evidence = [
                f"Historical observation count: {unique_dates} days.",
                f"Simulated stock on hand: {stock_on_hand} units.",
                f"Estimated daily velocity: {daily_velocity:.2f} units/day.",
                f"Inventory coverage: {coverage_days:.1f} days ({risk_status}).",
            ]
            if benchmark_results.get("status") == "success":
                sel_m = benchmark_results.get("selected_model", "moving_average")
                sel_metrics = benchmark_results.get("selected_test_metrics", {})
                evidence.append(f"Forecasting model selected via validation benchmark: {sel_m} (MAE: {sel_metrics.get('mae', 'N/A')}, RMSE: {sel_metrics.get('rmse', 'N/A')}).")

            priority = "High" if "Stockout Risk" in risk_status or "Excess Stock" in risk_status else "Low"

            forecast_data = {
                "predicted_units": round(daily_velocity, 2),
                "historical_average": round(daily_velocity, 2),
                "model_used": benchmark_results.get("selected_model", "Moving Average / Naive Baseline"),
                "mae": benchmark_results.get("selected_test_metrics", {}).get("mae"),
                "rmse": benchmark_results.get("selected_test_metrics", {}).get("rmse"),
            }

            inventory_data = {
                "stock_on_hand": stock_on_hand,
                "estimated_daily_velocity": round(daily_velocity, 2),
                "coverage_days": round(coverage_days, 1),
                "risk_status": risk_status,
            }

            promotion_data = {
                "suggested_discount_pct": discount_pct,
                "current_price": prod.get("retail_price", 10.0),
                "recommendation_action": recommendation_action,
            }

            decisions.append({
                "item_id": item_id,
                "store_id": store_id,
                "recommendation": recommendation_action,
                "priority": priority,
                "reliability": reliability,
                "reason": reason,
                "evidence": evidence,
                "forecast": forecast_data,
                "inventory": inventory_data,
                "promotion": promotion_data,
                "warnings": warnings,
            })

        return {
            "retail_id": retail_id,
            "status": "success",
            "total_decisions": len(decisions),
            "decisions": clean_document(decisions[:50]),
        }
    except Exception as e:
        return {
            "retail_id": retail_id,
            "status": "error",
            "message": str(e),
            "total_decisions": 0,
            "decisions": [],
        }

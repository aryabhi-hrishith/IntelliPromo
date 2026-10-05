"""
Retailer-Specific AI/ML Analytics Service.

Provides tenant-scoped data-readiness assessment, demand forecasting, customer segmentation,
product affinity (basket analysis), inventory alignment, and promotion recommendations
using only successfully committed retailer records.
"""

from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any
from pymongo.errors import PyMongoError

from .database import (
    db,
    get_tenant_query,
    tenant_products,
    tenant_sales,
    tenant_inventory,
    tenant_prices,
    tenant_customers,
    tenant_stores,
    tenant_campaign_outcomes,
    tenant_import_batches,
    clean_document,
)
from .forecasting_benchmark import evaluate_forecasting_benchmark

tenant_analytics_runs = db["tenant_analytics_runs"]


def assess_data_readiness(retail_id: str) -> Dict[str, Any]:
    """
    Assess data readiness across all required canonical datasets for the given tenant retailer.
    """
    try:
        prod_count = tenant_products.count_documents(get_tenant_query(retail_id))
        sales_count = tenant_sales.count_documents(get_tenant_query(retail_id))
        inv_count = tenant_inventory.count_documents(get_tenant_query(retail_id))
        prices_count = tenant_prices.count_documents(get_tenant_query(retail_id))
        cust_count = tenant_customers.count_documents(get_tenant_query(retail_id))
        stores_count = tenant_stores.count_documents(get_tenant_query(retail_id))
        outcomes_count = tenant_campaign_outcomes.count_documents(get_tenant_query(retail_id))

        # Check date coverage for sales
        sales_cursor = tenant_sales.find(get_tenant_query(retail_id), {"date": 1}).sort("date", 1)
        sales_dates = [doc.get("date") for doc in sales_cursor if doc.get("date")]
        min_date = sales_dates[0] if sales_dates else None
        max_date = sales_dates[-1] if sales_dates else None

        # Check if customer_ids are present in sales
        sales_with_cust = tenant_sales.count_documents(get_tenant_query(retail_id, {"customer_id": {"$ne": None}}))
        
        # Check if transaction_ids are present
        sales_with_tx = tenant_sales.count_documents(get_tenant_query(retail_id, {"transaction_id": {"$ne": None}}))

        datasets_found = {
            "products": prod_count > 0,
            "sales": sales_count > 0,
            "inventory": inv_count > 0,
            "prices": prices_count > 0,
            "customers": cust_count > 0 or sales_with_cust > 0,
            "stores": stores_count > 0,
            "campaign_outcomes": outcomes_count > 0,
        }

        readiness_status = "ready"
        if not sales_count and not prod_count:
            readiness_status = "unavailable"
        elif not inv_count or not cust_count:
            readiness_status = "degraded"

        return {
            "retail_id": retail_id,
            "readiness_status": readiness_status,
            "record_counts": {
                "products": prod_count,
                "sales": sales_count,
                "inventory": inv_count,
                "prices": prices_count,
                "customers": cust_count,
                "stores": stores_count,
                "campaign_outcomes": outcomes_count,
            },
            "date_coverage": {
                "start_date": min_date,
                "end_date": max_date,
                "total_sales_records": sales_count,
            },
            "capabilities": {
                "forecasting_ready": sales_count >= 10,
                "inventory_alignment_ready": inv_count > 0 and sales_count > 0,
                "customer_segmentation_ready": cust_count > 0 or sales_with_cust > 0,
                "product_affinity_ready": sales_with_tx > 0,
                "promotion_recommendations_ready": prod_count > 0 and sales_count > 0,
            },
            "missing_fields_notes": [
                "Inventory snapshots missing" if not inv_count else None,
                "Customer records missing" if not cust_count and not sales_with_cust else None,
                "Unit cost missing (margin calculations unavailable)" if prices_count == 0 else None,
            ],
            "assessed_at": datetime.utcnow().isoformat() + "Z",
        }
    except Exception as e:
        return {
            "retail_id": retail_id,
            "readiness_status": "error",
            "error": str(e),
        }


def run_tenant_analytics(retail_id: str) -> Dict[str, Any]:
    """
    Run tenant-scoped analytics (Forecasting, Segmentation, Affinity, Inventory, Recommendations)
    using only successfully committed records for this retailer.
    """
    readiness = assess_data_readiness(retail_id)
    if readiness.get("readiness_status") == "unavailable":
        raise ValueError("Insufficient data to run analytics. Please upload product and sales datasets first.")

    run_id = f"run_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

    # 1. Demand Forecasting
    forecast_results = []
    forecast_metrics = {"mae": None, "rmse": None, "model": "Moving Average / Naive Baseline"}
    try:
        sales_docs = list(tenant_sales.find(get_tenant_query(retail_id)))
        if sales_docs:
            df_sales = pd.DataFrame(sales_docs)
            if "date" in df_sales.columns and "quantity" in df_sales.columns and "item_id" in df_sales.columns:
                df_sales["date"] = pd.to_datetime(df_sales["date"], errors="coerce")
                df_sales = df_sales.dropna(subset=["date", "quantity", "item_id"])
                
                # Group by item_id and date
                grouped = df_sales.groupby(["item_id", "date"])["quantity"].sum().reset_index()
                
                for item_id, group in grouped.groupby("item_id"):
                    group = group.sort_values("date")
                    if len(group) >= 2:
                        avg_qty = float(group["quantity"].mean())
                        last_date = group["date"].max()
                        forecast_date = (last_date + timedelta(days=1)).strftime("%Y-%m-%d")
                        forecast_results.append({
                            "item_id": item_id,
                            "last_recorded_date": last_date.strftime("%Y-%m-%d"),
                            "forecast_date": forecast_date,
                            "predicted_units": round(avg_qty, 2),
                            "historical_average": round(avg_qty, 2),
                        })

                # Run robust forecasting benchmark & validation model selection
                benchmark_res = evaluate_forecasting_benchmark(df_sales)
                if benchmark_res.get("status") == "success":
                    selected_model = benchmark_res.get("selected_model", "moving_average")
                    sel_metrics = benchmark_res.get("selected_test_metrics", {})
                    forecast_metrics = {
                        "model": selected_model,
                        "mae": sel_metrics.get("mae"),
                        "rmse": sel_metrics.get("rmse"),
                        "benchmark_details": benchmark_res,
                    }
                else:
                    forecast_metrics = {
                        "model": "moving_average",
                        "mae": None,
                        "rmse": None,
                        "benchmark_details": benchmark_res,
                        "note": benchmark_res.get("message", "Insufficient history for rigorous benchmark evaluation."),
                    }
    except Exception as e:
        forecast_metrics["error"] = str(e)

    # 2. Customer Segmentation (RFM or attribute grouping)
    segment_results = []
    try:
        sales_docs = list(tenant_sales.find(get_tenant_query(retail_id)))
        cust_docs = list(tenant_customers.find(get_tenant_query(retail_id)))
        
        if cust_docs:
            for c in cust_docs:
                segment_results.append({
                    "customer_id": c.get("customer_id"),
                    "segment": c.get("segment", "Standard"),
                    "lifetime_spend": c.get("lifetime_spend", 0.0),
                })
        elif sales_docs:
            df_sales = pd.DataFrame(sales_docs)
            if "customer_id" in df_sales.columns:
                df_sales = df_sales.dropna(subset=["customer_id"])
                if not df_sales.empty:
                    rfm = df_sales.groupby("customer_id").agg(
                        frequency=("transaction_id", "count"),
                        monetary=("quantity", lambda x: float((x * df_sales.loc[x.index, "unit_price"]).sum()))
                    ).reset_index()
                    for _, row in rfm.iterrows():
                        spend = row["monetary"]
                        seg = "VIP" if spend > 500 else ("Regular" if spend > 100 else "Occasional")
                        segment_results.append({
                            "customer_id": row["customer_id"],
                            "segment": seg,
                            "frequency": int(row["frequency"]),
                            "lifetime_spend": round(spend, 2),
                        })
    except Exception as e:
        pass

    # 3. Product Affinity (Market Basket Co-occurrence)
    affinity_results = []
    try:
        sales_docs = list(tenant_sales.find(get_tenant_query(retail_id)))
        if sales_docs:
            df_sales = pd.DataFrame(sales_docs)
            if "transaction_id" in df_sales.columns and "item_id" in df_sales.columns:
                baskets = df_sales.groupby("transaction_id")["item_id"].unique().tolist()
                co_occur = {}
                item_counts = {}
                total_baskets = len(baskets)
                
                for basket in baskets:
                    basket = list(set(basket))
                    for item in basket:
                        item_counts[item] = item_counts.get(item, 0) + 1
                    for i in range(len(basket)):
                        for j in range(i + 1, len(basket)):
                            pair = tuple(sorted([basket[i], basket[j]]))
                            co_occur[pair] = co_occur.get(pair, 0) + 1
                
                for (item_a, item_b), count in co_occur.items():
                    if count >= 2: # support threshold
                        support = count / total_baskets if total_baskets > 0 else 0
                        conf = count / item_counts.get(item_a, 1)
                        affinity_results.append({
                            "item_a": item_a,
                            "item_b": item_b,
                            "co_occurrence_count": count,
                            "support": round(support, 4),
                            "confidence": round(conf, 4),
                            "lift": round(conf / (item_counts.get(item_b, 1) / total_baskets), 2) if total_baskets > 0 else 1.0
                        })
                affinity_results = sorted(affinity_results, key=lambda x: x["lift"], reverse=True)[:10]
    except Exception as e:
        pass

    # 4. Inventory Alignment
    inventory_results = []
    try:
        inv_docs = list(tenant_inventory.find(get_tenant_query(retail_id)))
        prod_docs = list(tenant_products.find(get_tenant_query(retail_id)))
        prod_prices = {p.get("item_id"): p.get("retail_price", 0.0) for p in prod_docs}
        
        for inv in inv_docs:
            item_id = inv.get("item_id")
            stock = inv.get("stock_on_hand", 0.0)
            store_id = inv.get("store_id")
            
            # Find sales velocity for this item/store
            sales_for_item = list(tenant_sales.find(get_tenant_query(retail_id, {"item_id": item_id, "store_id": store_id})))
            total_qty = sum(s.get("quantity", 0) for s in sales_for_item)
            days = max(1, len(set(s.get("date") for s in sales_for_item if s.get("date"))))
            daily_velocity = total_qty / days if days > 0 else 0.5
            
            coverage_days = stock / daily_velocity if daily_velocity > 0 else 999.0
            risk_status = "Normal"
            if coverage_days < 14:
                risk_status = "Stockout Risk (< 14 days)"
            elif coverage_days > 60:
                risk_status = "Excess Stock (> 60 days)"

            inventory_results.append({
                "store_id": store_id,
                "item_id": item_id,
                "stock_on_hand": stock,
                "estimated_daily_velocity": round(daily_velocity, 2),
                "coverage_days": round(coverage_days, 1),
                "risk_status": risk_status,
            })
    except Exception as e:
        pass

    # 5. Promotion Recommendations
    recommendation_results = []
    try:
        for inv in inventory_results:
            if "Stockout Risk" in inv["risk_status"] or "Excess Stock" in inv["risk_status"]:
                item_id = inv["item_id"]
                store_id = inv["store_id"]
                prod = tenant_products.find_one(get_tenant_query(retail_id, {"item_id": item_id}))
                price = prod.get("retail_price", 10.0) if prod else 10.0
                has_cost = prod and prod.get("unit_cost") is not None
                
                rec_action = "Review excess inventory - consider promotion" if "Excess Stock" in inv["risk_status"] else "Review replenishment - avoid promotion"
                disc_pct = 15.0 if "Excess Stock" in inv["risk_status"] else 0.0
                
                recommendation_results.append({
                    "store_id": store_id,
                    "item_id": item_id,
                    "recommendation": rec_action,
                    "suggested_discount_pct": disc_pct,
                    "current_price": price,
                    "unit_cost_available": has_cost,
                    "reason": f"Coverage is {inv['coverage_days']} days ({inv['risk_status']}).",
                })
    except Exception as e:
        pass

    run_document = {
        "run_id": run_id,
        "retail_id": retail_id,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "data_readiness": readiness,
        "forecast_metrics": forecast_metrics,
        "forecast_summary": forecast_results[:20],
        "customer_segments_count": len(segment_results),
        "customer_segments": segment_results[:20],
        "product_affinity_rules": affinity_results,
        "inventory_alignment_count": len(inventory_results),
        "inventory_alignment": inventory_results[:20],
        "recommendations_count": len(recommendation_results),
        "recommendations": recommendation_results[:20],
    }

    try:
        tenant_analytics_runs.insert_one(run_document)
    except Exception:
        pass

    return clean_document(run_document)


def get_latest_analytics_run(retail_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve the most recent analytics run for the retailer.
    """
    try:
        doc = tenant_analytics_runs.find_one(get_tenant_query(retail_id), sort=[("created_at", -1)])
        return clean_document(doc) if doc else None
    except Exception:
        return None

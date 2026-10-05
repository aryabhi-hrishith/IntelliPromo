"""
Demo Retailer Fixture for Demonstration and End-to-End Testing (Stage 7).

Provides a deterministic synthetic retailer dataset with:
- Multiple products and stores (CA_1, TX_1)
- 45+ days of sales history (sufficient for forecasting benchmark and ML models)
- Low-stock scenario (Stockout Risk < 14 days)
- Excess-stock scenario (Excess Stock > 60 days)
- Demand-decline scenario
- Retail prices and inventory snapshots
"""

from datetime import datetime, timedelta
from .database import (
    tenant_products,
    tenant_sales,
    tenant_inventory,
    tenant_prices,
    tenant_stores,
)


def seed_demo_retailer(retail_id: str = "demo_retailer_pro") -> dict:
    """
    Seed MongoDB tenant collections with a deterministic demo retailer dataset.
    Idempotent: clears existing data for this retail_id first.
    """
    tenant_products.delete_many({"retail_id": retail_id})
    tenant_sales.delete_many({"retail_id": retail_id})
    tenant_inventory.delete_many({"retail_id": retail_id})
    tenant_prices.delete_many({"retail_id": retail_id})
    tenant_stores.delete_many({"retail_id": retail_id})

    stores = [
        {"retail_id": retail_id, "store_id": "CA_1", "store_name": "California Flagship Store", "state": "CA"},
        {"retail_id": retail_id, "store_id": "TX_1", "store_name": "Texas Metro Store", "state": "TX"},
    ]
    tenant_stores.insert_many(stores)

    products = [
        {"retail_id": retail_id, "item_id": "PRO_BREAD_01", "product_name": "Artisan Sourdough Bread", "category": "Bakery", "retail_price": 4.99, "unit_cost": 2.00},
        {"retail_id": retail_id, "item_id": "PRO_MILK_02", "product_name": "Organic Whole Milk 1gal", "category": "Dairy", "retail_price": 3.89, "unit_cost": 2.20},
        {"retail_id": retail_id, "item_id": "PRO_CHIPS_03", "product_name": "Sea Salt Potato Chips", "category": "Snacks", "retail_price": 2.49, "unit_cost": 1.10},
    ]
    tenant_products.insert_many(products)

    prices = []
    for p in products:
        for st in ["CA_1", "TX_1"]:
            prices.append({
                "retail_id": retail_id,
                "store_id": st,
                "item_id": p["item_id"],
                "retail_price": p["retail_price"],
                "unit_cost": p["unit_cost"],
                "effective_date": "2026-01-01"
            })
    tenant_prices.insert_many(prices)

    start_date = datetime.strptime("2026-01-01", "%Y-%m-%d")
    sales = []
    tx_counter = 1000

    for day_offset in range(45):
        current_date = start_date + timedelta(days=day_offset)
        date_str = current_date.strftime("%Y-%m-%d")

        # Item 1: Declining demand scenario (excess stock)
        qty_1 = max(1.0, 15.0 - (day_offset * 0.2))
        sales.append({
            "retail_id": retail_id,
            "transaction_id": f"TX_{tx_counter}",
            "date": date_str,
            "store_id": "CA_1",
            "item_id": "PRO_BREAD_01",
            "quantity": float(round(qty_1, 1)),
            "unit_price": 4.99,
            "customer_id": f"CUST_{day_offset % 10}"
        })
        tx_counter += 1

        # Item 2: High demand scenario (low stock / stockout risk)
        qty_2 = 25.0 + (day_offset % 5)
        sales.append({
            "retail_id": retail_id,
            "transaction_id": f"TX_{tx_counter}",
            "date": date_str,
            "store_id": "CA_1",
            "item_id": "PRO_MILK_02",
            "quantity": float(qty_2),
            "unit_price": 3.89,
            "customer_id": f"CUST_{(day_offset + 3) % 10}"
        })
        tx_counter += 1

        # Item 3: Normal demand scenario
        qty_3 = 8.0 + (day_offset % 3)
        sales.append({
            "retail_id": retail_id,
            "transaction_id": f"TX_{tx_counter}",
            "date": date_str,
            "store_id": "TX_1",
            "item_id": "PRO_CHIPS_03",
            "quantity": float(qty_3),
            "unit_price": 2.49,
            "customer_id": f"CUST_{(day_offset + 5) % 10}"
        })
        tx_counter += 1

    tenant_sales.insert_many(sales)

    inventory = [
        {"retail_id": retail_id, "store_id": "CA_1", "item_id": "PRO_MILK_02", "stock_on_hand": 30.0, "date": "2026-02-15"},
        {"retail_id": retail_id, "store_id": "CA_1", "item_id": "PRO_BREAD_01", "stock_on_hand": 500.0, "date": "2026-02-15"},
        {"retail_id": retail_id, "store_id": "TX_1", "item_id": "PRO_CHIPS_03", "stock_on_hand": 150.0, "date": "2026-02-15"},
    ]
    tenant_inventory.insert_many(inventory)

    return {
        "status": "success",
        "retail_id": retail_id,
        "stores_seeded": len(stores),
        "products_seeded": len(products),
        "sales_records_seeded": len(sales),
        "inventory_records_seeded": len(inventory),
    }

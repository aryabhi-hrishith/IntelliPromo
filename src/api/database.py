"""
MongoDB connection for the API.

Handles reading data, recording campaign decision history, and multi-tenant isolation.
"""

import math
import os
from typing import Optional

from bson import ObjectId
from pymongo import MongoClient


MONGO_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
DB_NAME = "retail_promotion_planner"

# One client is created when the API starts and reused for every request.
# (MongoClient connects lazily, so importing this file works even if MongoDB is off.)
client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
db = client[DB_NAME]

products = db["products"]
recommendations = db["recommendations"]
decision_history = db["decision_history"]
product_affinity = db["product_affinity"]
customer_segments = db["customer_segments"]
segment_promotions = db["segment_promotions"]
campaign_outcomes = db["campaign_outcomes"]

# Tenant-scoped collections
tenant_import_batches = db["tenant_import_batches"]
tenant_products = db["tenant_products"]
tenant_sales = db["tenant_sales"]
tenant_inventory = db["tenant_inventory"]
tenant_prices = db["tenant_prices"]
tenant_customers = db["tenant_customers"]
tenant_stores = db["tenant_stores"]
tenant_campaign_outcomes = db["tenant_campaign_outcomes"]


def clean_document(value):
    """
    Make a MongoDB document safe to send as JSON:
    - ObjectId (the _id field) becomes a plain string
    - NaN / infinity numbers become None (shown as null), because JSON cannot hold them
    Works on dictionaries, lists and single values.
    """
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if isinstance(value, dict):
        return {key: clean_document(item) for key, item in value.items()}
    if isinstance(value, list):
        return [clean_document(item) for item in value]
    return value


def get_tenant_query(retail_id: str, base_query: Optional[dict] = None) -> dict:
    """
    Build a MongoDB query strictly scoped to the given retail_id.
    CRITICAL: Never rely on store_id alone for tenant isolation. Every query must include retail_id.
    """
    if not retail_id:
        raise ValueError("retail_id is mandatory for tenant-scoped database queries.")
    query = {"retail_id": retail_id}
    if base_query:
        query.update(base_query)
    return query


def create_tenant_indexes():
    """
    Create compound indexes ensuring tenant isolation and efficient querying.
    """
    try:
        tenant_products.create_index([("retail_id", 1), ("store_id", 1), ("item_id", 1)], unique=False)
        tenant_sales.create_index([("retail_id", 1), ("store_id", 1), ("date", 1)], unique=False)
        tenant_inventory.create_index([("retail_id", 1), ("store_id", 1), ("item_id", 1), ("date", 1)], unique=False)
        tenant_prices.create_index([("retail_id", 1), ("store_id", 1), ("item_id", 1)], unique=False)
        tenant_customers.create_index([("retail_id", 1), ("customer_id", 1)], unique=False)
        tenant_campaign_outcomes.create_index([("retail_id", 1), ("campaign_id", 1)], unique=False)
    except Exception:
        pass  # Non-blocking if MongoDB is offline during unit testing without live server
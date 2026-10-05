"""
Tests for Canonical Data Schemas (Stage 2).

Verifies validation, required fields, optional fields, invalid data types,
date formats, and retail_id rules.
"""

import pytest
from pydantic import ValidationError
from src.models.canonical_schemas import (
    RetailerMetadata,
    StoreMetadata,
    ProductCatalogSchema,
    SalesTransactionSchema,
    InventorySnapshotSchema,
    PriceHistorySchema,
    CustomerSchema,
    CampaignOutcomeSchema,
    ImportBatchSchema,
)


def test_retailer_metadata_valid():
    model = RetailerMetadata(retail_id="retailer_alpha", retailer_name="Alpha Foods")
    assert model.retail_id == "retailer_alpha"
    assert model.country_code == "US"
    assert model.default_currency == "USD"


def test_retailer_metadata_invalid_retail_id():
    with pytest.raises(ValidationError):
        RetailerMetadata(retail_id="invalid id!", retailer_name="Bad ID")


def test_product_catalog_valid_with_optional_cost():
    # unit_cost is optional (honest missing data)
    model = ProductCatalogSchema(
        retail_id="store_one",
        item_id="PROD_123",
        product_name="Organic Milk",
        category="Dairy",
        retail_price=4.99,
    )
    assert model.unit_cost is None
    assert model.brand is None


def test_product_catalog_invalid_negative_price():
    with pytest.raises(ValidationError):
        ProductCatalogSchema(
            retail_id="store_one",
            item_id="PROD_123",
            product_name="Bad Price",
            category="Dairy",
            retail_price=-1.0,
        )


def test_sales_transaction_valid():
    tx = SalesTransactionSchema(
        retail_id="retailer_beta",
        transaction_id="TX_999",
        date="2026-10-04",
        store_id="CA_1",
        item_id="ITEM_1",
        quantity=3.0,
        unit_price=10.50,
    )
    assert tx.customer_id is None
    assert tx.discount_amount == 0.0


def test_sales_transaction_invalid_date_format():
    with pytest.raises(ValidationError):
        SalesTransactionSchema(
            retail_id="retailer_beta",
            transaction_id="TX_999",
            date="10-04-2026",  # Invalid format (not YYYY-MM-DD)
            store_id="CA_1",
            item_id="ITEM_1",
            quantity=1.0,
            unit_price=5.00,
        )


def test_inventory_snapshot_valid():
    inv = InventorySnapshotSchema(
        retail_id="retailer_gamma",
        store_id="TX_1",
        item_id="ITEM_2",
        date="2026-10-04",
        stock_on_hand=150.0,
    )
    assert inv.reorder_point is None


def test_campaign_outcome_valid():
    outcome = CampaignOutcomeSchema(
        retail_id="retailer_alpha",
        campaign_id="CAMP_01",
        item_id="ITEM_1",
        store_id="CA_1",
        start_date="2026-10-01",
        end_date="2026-10-07",
        discount_pct=15.0,
    )
    assert outcome.actual_lift_pct is None
    assert outcome.approval_status == "pending"

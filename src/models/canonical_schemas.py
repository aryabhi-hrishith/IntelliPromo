"""
Canonical Data Schemas for Multi-Retailer Retail Intelligence Platform.

Defines Pydantic v2 validated schemas for all ingested retail entities,
ensuring strict data types, consistent identifiers, currency handling, date formats,
and honest representation of optional fields (without forcing synthetic defaults).
"""

from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
import re

RETAIL_ID_REGEX = re.compile(r"^[a-zA-Z0-9_-]{2,64}$")


def validate_retail_id(v: str) -> str:
    if not isinstance(v, str) or not RETAIL_ID_REGEX.match(v):
        raise ValueError("retail_id must be 2-64 characters alphanumeric, hyphen, or underscore.")
    return v


class RetailerMetadata(BaseModel):
    retail_id: str = Field(..., description="Unique tenant identifier for the retailer")
    retailer_name: str = Field(..., description="Display name of the retailer")
    country_code: str = Field(default="US", description="ISO country code")
    default_currency: str = Field(default="USD", description="Currency code (e.g. USD, EUR)")
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)

    @field_validator("retail_id")
    @classmethod
    def check_retail_id(cls, v: str) -> str:
        return validate_retail_id(v)


class StoreMetadata(BaseModel):
    retail_id: str = Field(..., description="Tenant retailer identifier")
    store_id: str = Field(..., description="Unique store identifier within retailer")
    store_name: str = Field(..., description="Display name of the store location")
    region: Optional[str] = Field(default=None, description="Geographic region or district")
    format_type: Optional[str] = Field(default=None, description="Store format (e.g., Supermarket, Express)")

    @field_validator("retail_id")
    @classmethod
    def check_retail_id(cls, v: str) -> str:
        return validate_retail_id(v)


class ProductCatalogSchema(BaseModel):
    retail_id: str = Field(..., description="Tenant retailer identifier")
    item_id: str = Field(..., description="Unique product SKU or item identifier")
    product_name: str = Field(..., description="Name or description of the product")
    category: str = Field(..., description="Product category (e.g. Foods, Electronics)")
    department: Optional[str] = Field(default=None, description="Department name")
    retail_price: float = Field(..., ge=0.0, description="Current selling price")
    unit_cost: Optional[float] = Field(default=None, ge=0.0, description="Unit cost (optional if unknown)")
    brand: Optional[str] = Field(default=None, description="Product brand")

    @field_validator("retail_id")
    @classmethod
    def check_retail_id(cls, v: str) -> str:
        return validate_retail_id(v)


class SalesTransactionSchema(BaseModel):
    retail_id: str = Field(..., description="Tenant retailer identifier")
    transaction_id: str = Field(..., description="Unique transaction receipt identifier")
    date: str = Field(..., description="Transaction date in YYYY-MM-DD format")
    store_id: str = Field(..., description="Store location identifier")
    item_id: str = Field(..., description="Product item identifier")
    quantity: float = Field(..., gt=0, description="Quantity sold")
    unit_price: float = Field(..., ge=0.0, description="Price charged per unit")
    customer_id: Optional[str] = Field(default=None, description="Customer identifier if tracked (optional)")
    discount_amount: Optional[float] = Field(default=0.0, ge=0.0, description="Discount applied")

    @field_validator("retail_id")
    @classmethod
    def check_retail_id(cls, v: str) -> str:
        return validate_retail_id(v)

    @field_validator("date")
    @classmethod
    def validate_date(cls, v: str) -> str:
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError("date must be in YYYY-MM-DD format")
        return v


class InventorySnapshotSchema(BaseModel):
    retail_id: str = Field(..., description="Tenant retailer identifier")
    store_id: str = Field(..., description="Store location identifier")
    item_id: str = Field(..., description="Product item identifier")
    date: str = Field(..., description="Snapshot date in YYYY-MM-DD format")
    stock_on_hand: float = Field(..., ge=0.0, description="Current stock units available")
    reorder_point: Optional[float] = Field(default=None, ge=0.0, description="Reorder threshold")
    safety_stock: Optional[float] = Field(default=None, ge=0.0, description="Safety stock level")

    @field_validator("retail_id")
    @classmethod
    def check_retail_id(cls, v: str) -> str:
        return validate_retail_id(v)

    @field_validator("date")
    @classmethod
    def validate_date(cls, v: str) -> str:
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError("date must be in YYYY-MM-DD format")
        return v


class PriceHistorySchema(BaseModel):
    retail_id: str = Field(..., description="Tenant retailer identifier")
    store_id: str = Field(..., description="Store location identifier")
    item_id: str = Field(..., description="Product item identifier")
    effective_date: str = Field(..., description="Price effective date in YYYY-MM-DD format")
    unit_price: float = Field(..., ge=0.0, description="Selling price")
    unit_cost: Optional[float] = Field(default=None, ge=0.0, description="Unit cost at this price point")

    @field_validator("retail_id")
    @classmethod
    def check_retail_id(cls, v: str) -> str:
        return validate_retail_id(v)

    @field_validator("effective_date")
    @classmethod
    def validate_date(cls, v: str) -> str:
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError("effective_date must be in YYYY-MM-DD format")
        return v


class CustomerSchema(BaseModel):
    retail_id: str = Field(..., description="Tenant retailer identifier")
    customer_id: str = Field(..., description="Unique customer identifier")
    segment: Optional[str] = Field(default=None, description="Customer segment or tier")
    signup_date: Optional[str] = Field(default=None, description="Registration date YYYY-MM-DD")
    lifetime_spend: Optional[float] = Field(default=None, ge=0.0, description="Total historical spend")

    @field_validator("retail_id")
    @classmethod
    def check_retail_id(cls, v: str) -> str:
        return validate_retail_id(v)


class CampaignOutcomeSchema(BaseModel):
    retail_id: str = Field(..., description="Tenant retailer identifier")
    campaign_id: str = Field(..., description="Campaign identifier")
    item_id: str = Field(..., description="Product item identifier")
    store_id: str = Field(..., description="Store location identifier")
    start_date: str = Field(..., description="Campaign start date YYYY-MM-DD")
    end_date: str = Field(..., description="Campaign end date YYYY-MM-DD")
    discount_pct: float = Field(..., ge=0.0, le=100.0, description="Discount percentage")
    actual_lift_pct: Optional[float] = Field(default=None, description="Measured sales lift percentage")
    actual_revenue: Optional[float] = Field(default=None, ge=0.0, description="Measured revenue")
    approval_status: str = Field(default="pending", description="Status: approved, rejected, pending")

    @field_validator("retail_id")
    @classmethod
    def check_retail_id(cls, v: str) -> str:
        return validate_retail_id(v)


class ImportBatchSchema(BaseModel):
    retail_id: str = Field(..., description="Tenant retailer identifier")
    batch_id: str = Field(..., description="Unique ingestion batch identifier")
    filename: str = Field(..., description="Original filename uploaded")
    record_count: int = Field(..., ge=0, description="Number of records ingested")
    status: str = Field(..., description="Status: success, partial, failed")
    error_summary: Optional[str] = Field(default=None, description="Summary of validation errors if any")
    imported_at: Optional[datetime] = Field(default_factory=datetime.utcnow)

    @field_validator("retail_id")
    @classmethod
    def check_retail_id(cls, v: str) -> str:
        return validate_retail_id(v)

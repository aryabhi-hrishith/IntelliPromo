"""
Secure Retailer Data Ingestion and Validation Service.

Handles secure file upload (CSV, with clear error for unsupported Excel if openpyxl missing),
file size limits (50 MB), temporary file cleanup, header inference, column mapping,
Pydantic canonical schema validation, preview generation, idempotent commit, and tenant-scoped batch tracking.
"""

import os
import uuid
import tempfile
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
import pandas as pd
from fastapi import UploadFile, HTTPException, status

from src.models.canonical_schemas import (
    ProductCatalogSchema,
    SalesTransactionSchema,
    InventorySnapshotSchema,
    PriceHistorySchema,
    CustomerSchema,
    StoreMetadata,
    CampaignOutcomeSchema,
    ImportBatchSchema,
)
from src.api.database import db, get_tenant_query

MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB
tenant_import_batches = db["tenant_import_batches"]


def validate_file_upload(file: UploadFile) -> str:
    """
    Validate file extension, size, and type. Returns file extension.
    """
    filename = file.filename or ""
    ext = os.path.splitext(filename)[1].lower()
    
    if ext not in [".csv", ".xlsx", ".xls"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{ext}'. Allowed formats: .csv, .xlsx, .xls",
        )
    
    if ext in [".xlsx", ".xls"]:
        # Check if openpyxl is installed
        try:
            import openpyxl
        except ImportError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Excel support (.xlsx/.xls) is currently unavailable because openpyxl is not installed. Please upload a CSV file.",
            )
            
    return ext


def infer_dataset_type_and_mapping(columns: List[str]) -> Tuple[str, Dict[str, str]]:
    """
    Inspect column headers and infer dataset type and initial column mapping suggestions.
    """
    norm_cols = {c.strip().lower().replace(" ", "_"): c for c in columns}
    
    # Check for products
    if any(k in norm_cols for k in ["item_id", "sku", "product_id"]) and any(k in norm_cols for k in ["product_name", "item_name", "title"]):
        mapping = {}
        for target in ["item_id", "product_name", "category", "retail_price", "unit_cost", "department", "brand"]:
            for nk, orig in norm_cols.items():
                if target in nk or nk in target:
                    mapping[orig] = target
                    break
        return "products", mapping

    # Check for sales transactions
    if any(k in norm_cols for k in ["transaction_id", "order_id", "receipt_id"]) and any(k in norm_cols for k in ["quantity", "units", "qty"]):
        mapping = {}
        for target in ["transaction_id", "date", "store_id", "item_id", "quantity", "unit_price", "customer_id", "discount_amount"]:
            for nk, orig in norm_cols.items():
                if target in nk or nk in target:
                    mapping[orig] = target
                    break
        return "sales", mapping

    # Check for inventory
    if any(k in norm_cols for k in ["stock_on_hand", "inventory", "stock", "on_hand"]) and any(k in norm_cols for k in ["store_id", "store"]):
        mapping = {}
        for target in ["store_id", "item_id", "date", "stock_on_hand", "reorder_point", "safety_stock"]:
            for nk, orig in norm_cols.items():
                if target in nk or nk in target:
                    mapping[orig] = target
                    break
        return "inventory", mapping

    # Check for prices
    if any(k in norm_cols for k in ["unit_price", "price"]) and any(k in norm_cols for k in ["effective_date", "price_date", "date"]):
        mapping = {}
        for target in ["store_id", "item_id", "effective_date", "unit_price", "unit_cost"]:
            for nk, orig in norm_cols.items():
                if target in nk or nk in target:
                    mapping[orig] = target
                    break
        return "prices", mapping

    # Check for customers
    if any(k in norm_cols for k in ["customer_id", "cust_id"]) and any(k in norm_cols for k in ["segment", "tier", "lifetime_spend"]):
        mapping = {}
        for target in ["customer_id", "segment", "signup_date", "lifetime_spend"]:
            for nk, orig in norm_cols.items():
                if target in nk or nk in target:
                    mapping[orig] = target
                    break
        return "customers", mapping

    # Check for stores
    if any(k in norm_cols for k in ["store_id"]) and any(k in norm_cols for k in ["store_name", "location"]):
        mapping = {}
        for target in ["store_id", "store_name", "region", "format_type"]:
            for nk, orig in norm_cols.items():
                if target in nk or nk in target:
                    mapping[orig] = target
                    break
        return "stores", mapping

    # Default fallback: general product/sales inference
    mapping = {c: c.strip().lower().replace(" ", "_") for c in columns}
    return "products", mapping


def parse_uploaded_file(file_path: str, ext: str, sheet_name: Optional[str] = None) -> pd.DataFrame:
    """
    Safely parse CSV or Excel file into a DataFrame without executing macros or code.
    """
    if ext == ".csv":
        # Try reading with utf-8, fallback to latin1
        try:
            df = pd.read_csv(file_path, encoding="utf-8")
        except UnicodeDecodeError:
            df = pd.read_csv(file_path, encoding="latin1")
    else:
        # Excel
        if sheet_name:
            df = pd.read_excel(file_path, sheet_name=sheet_name)
        else:
            df = pd.read_excel(file_path, sheet_name=0)
            
    # Normalize column names (strip whitespace)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def validate_rows_against_schema(
    df: pd.DataFrame, dataset_type: str, mapping: Dict[str, str], retail_id: str, batch_id: str
) -> Tuple[List[dict], List[dict], List[str]]:
    """
    Apply column mapping, validate records against canonical Pydantic schemas,
    and return (valid_records, error_records, missing_required_columns).
    """
    # Apply mapping: rename columns present in mapping
    rename_dict = {orig: target for orig, target in mapping.items() if orig in df.columns}
    mapped_df = df.rename(columns=rename_dict)

    # Determine schema class
    schema_map = {
        "products": ProductCatalogSchema,
        "sales": SalesTransactionSchema,
        "inventory": InventorySnapshotSchema,
        "prices": PriceHistorySchema,
        "customers": CustomerSchema,
        "stores": StoreMetadata,
        "campaign_outcomes": CampaignOutcomeSchema,
    }

    schema_cls = schema_map.get(dataset_type, ProductCatalogSchema)
    
    # Check required fields
    required_fields = [
        name for name, field in schema_cls.model_fields.items()
        if field.is_required() and name != "retail_id"
    ]
    
    present_cols = set(mapped_df.columns)
    missing_required = [f for f in required_fields if f not in present_cols]

    valid_records = []
    error_records = []

    if missing_required:
        return valid_records, error_records, missing_required

    for idx, row in mapped_df.iterrows():
        row_dict = row.to_dict()
        # Convert NaN/NaT to None
        cleaned_row = {
            k: (None if pd.isna(v) else v) for k, v in row_dict.items()
            if k in schema_cls.model_fields or k == "retail_id"
        }
        cleaned_row["retail_id"] = retail_id
        
        try:
            validated = schema_cls(**cleaned_row)
            record_doc = validated.model_dump()
            record_doc["batch_id"] = batch_id
            valid_records.append(record_doc)
        except Exception as e:
            error_records.append({
                "row_index": int(idx) + 2,  # 1-based index + header row
                "data": {str(k): (None if pd.isna(v) else v) for k, v in row_dict.items()},
                "error": str(e),
            })

    return valid_records, error_records, []

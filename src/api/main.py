"""
FastAPI backend for the AI-Driven Personalized Promotion and Inventory Alignment Planner.

Read-only: every endpoint is a GET request that reads from MongoDB.
Data labels: demand figures are a historical proxy (not an ML forecast),
inventory is SIMULATED and unit cost is ASSUMED, as documented in earlier steps.
"""

from datetime import datetime
from typing import Optional, Dict, List, Any
import uuid
import tempfile
import os

from fastapi import FastAPI, HTTPException, Query, Depends, UploadFile, File, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pymongo.errors import PyMongoError

from .database import (
    clean_document,
    client,
    products,
    recommendations,
    decision_history,
    product_affinity,
    customer_segments,
    segment_promotions,
    campaign_outcomes,
    tenant_import_batches,
    tenant_products,
    tenant_sales,
    tenant_inventory,
    tenant_prices,
    tenant_customers,
    tenant_stores,
    tenant_campaign_outcomes,
    get_tenant_query,
)
from .explanation_service import build_explanation
from .ai_explanation_service import generate_ai_explanation
from .campaign_reporting_service import compute_campaign_report, get_campaign_outcomes_list, save_campaign_outcome
from .tenant_context import get_current_retailer_id
from .ingestion_service import (
    validate_file_upload,
    infer_dataset_type_and_mapping,
    parse_uploaded_file,
    validate_rows_against_schema,
    MAX_UPLOAD_SIZE,
)
from .retailer_analytics_service import assess_data_readiness, run_tenant_analytics, get_latest_analytics_run
from .ai_decision_engine import compute_tenant_decisions

app = FastAPI(
    title="Promotion and Inventory Planner API",
    description=(
        "Read-only API for product and promotion-recommendation data. "
        "Demand is a historical proxy (not a live forecast), inventory is SIMULATED, "
        "and unit costs are ASSUMED. Recommendations are rule-based suggestions for human review."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    # allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_ITEM_RESULTS = 100  # an item has at most 10 stores, so this is just a safety cap
DB_ERROR_MESSAGE = "Could not read from MongoDB. Check that MongoDB is running on localhost:27017."


def list_documents(collection, skip, limit, store_id):
    """Return one page of documents plus the total number that match."""
    query = {}
    if store_id:
        query["store_id"] = store_id
    try:
        total = collection.count_documents(query)
        # Sorting by _id keeps the page order stable between requests.
        cursor = collection.find(query).sort("_id", 1).skip(skip).limit(limit)
        results = [clean_document(doc) for doc in cursor]
    except PyMongoError:
        raise HTTPException(status_code=503, detail=DB_ERROR_MESSAGE)
    return {
        "total_matching": total,
        "skip": skip,
        "limit": limit,
        "returned": len(results),
        "results": results,
    }


def documents_for_item(collection, item_id, store_id):
    """Return every document for one item_id (optionally one store), or a 404."""
    query = {"item_id": item_id}
    if store_id:
        query["store_id"] = store_id
    try:
        cursor = collection.find(query).sort("_id", 1).limit(MAX_ITEM_RESULTS)
        results = [clean_document(doc) for doc in cursor]
    except PyMongoError:
        raise HTTPException(status_code=503, detail=DB_ERROR_MESSAGE)
    if not results:
        raise HTTPException(status_code=404, detail=f"No documents found for item_id '{item_id}'.")
    return {"item_id": item_id, "returned": len(results), "results": results}


@app.get("/")
def api_status():
    """Simple status check, including whether MongoDB is reachable."""
    try:
        client.admin.command("ping")
        database = "connected"
        counts = {
            "products": products.estimated_document_count(),
            "recommendations": recommendations.estimated_document_count(),
        }
    except PyMongoError:
        database = "unavailable"
        counts = None
    return {
        "status": "ok",
        "api": "Promotion and Inventory Planner API",
        "database": database,
        "collection_counts": counts,
        "docs_url": "/docs",
    }


@app.get("/products")
def get_products(
    limit: int = Query(20, ge=1, le=100, description="How many documents to return (1-100)"),
    skip: int = Query(0, ge=0, description="How many documents to skip (for paging)"),
    store_id: Optional[str] = Query(None, description="Optional filter, e.g. CA_1"),
):
    """List products (one page at a time)."""
    return list_documents(products, skip, limit, store_id)


@app.get("/products/{item_id}")
def get_product_by_item(
    item_id: str,
    store_id: Optional[str] = Query(None, description="Optional filter, e.g. CA_1"),
):
    """All product documents matching an item_id (one per store)."""
    return documents_for_item(products, item_id, store_id)


@app.get("/recommendations")
def get_recommendations(
    limit: int = Query(20, ge=1, le=100, description="How many documents to return (1-100)"),
    skip: int = Query(0, ge=0, description="How many documents to skip (for paging)"),
    store_id: Optional[str] = Query(None, description="Optional filter, e.g. CA_1"),
):
    """List recommendations (one page at a time)."""
    return list_documents(recommendations, skip, limit, store_id)


@app.get("/recommendations/{item_id}/explanation")
def get_recommendation_explanation(
    item_id: str,
    store_id: Optional[str] = Query(
        None,
        description=(
            "Required when item_id is not unique across stores. "
            "Each item_id appears in up to 10 stores (CA_1..CA_4, TX_1..TX_3, WI_1..WI_3). "
            "If omitted and the item exists in multiple stores, a 400 error is returned listing "
            "the available store_ids so you can retry with one."
        ),
    ),
):
    """
    Structured explanation for a single product recommendation.

    Returns the rule-based reasoning behind the recommendation: coverage-day
    thresholds, discount-scenario margins, demand-change checks, and all data
    labels (HISTORICAL PROXY / SIMULATED / ASSUMED).

    Because one item_id appears in multiple stores, supply `store_id` to pin
    the result to a specific store. If the item exists in exactly one store
    the parameter is optional.
    """
    query = {"item_id": item_id}
    if store_id:
        query["store_id"] = store_id
    try:
        rec_docs = list(recommendations.find(query).sort("store_id", 1).limit(12))
    except PyMongoError:
        raise HTTPException(status_code=503, detail=DB_ERROR_MESSAGE)

    if not rec_docs:
        raise HTTPException(
            status_code=404,
            detail=f"No recommendation found for item_id='{item_id}'"
            + (f" store_id='{store_id}'" if store_id else "") + ".",
        )

    # item_id is not unique -- require store_id when there are multiple matches
    if len(rec_docs) > 1:
        available = [d["store_id"] for d in rec_docs if d.get("store_id")]
        raise HTTPException(
            status_code=400,
            detail=(
                f"item_id='{item_id}' exists in {len(rec_docs)} stores: {available}. "
                "Add ?store_id=<value> to select one."
            ),
        )

    rec_doc = clean_document(rec_docs[0])

    # Fetch the corresponding product document
    prod_query = {"item_id": item_id}
    if store_id:
        prod_query["store_id"] = store_id
    try:
        prod_doc_raw = products.find_one(prod_query)
    except PyMongoError:
        raise HTTPException(status_code=503, detail=DB_ERROR_MESSAGE)

    prod_doc = clean_document(prod_doc_raw) if prod_doc_raw else {}

    return build_explanation(prod_doc, rec_doc)


@app.get("/recommendations/{item_id}/ai-explanation")
def get_ai_recommendation_explanation(
    item_id: str,
    store_id: Optional[str] = Query(
        None,
        description=(
            "Required when item_id is not unique across stores. "
            "Each item_id appears in up to 10 stores (CA_1..CA_4, TX_1..TX_3, WI_1..WI_3). "
            "If omitted and the item exists in multiple stores, a 400 error is returned."
        ),
    ),
):
    """
    AI-generated explanation for a single product recommendation.

    Uses Google Gemini (gemini-2.0-flash) to produce a plain-language,
    structured explanation grounded in the stored product and recommendation
    data.  Requires GEMINI_API_KEY to be set in the environment.

    The AI explanation is DISTINCT from the rule-engine explanation returned
    by GET /recommendations/{item_id}/explanation.  The LLM does not change
    the recommendation, the discount, or any stored figures.

    Response fields:
      - explanation_type: 'ai_generated' on success, 'error' on failure.
      - provider / model: identifies the LLM used.
      - ai_explanation: validated structured output (summary, supporting_factors,
        inventory_context, discount_context, limitations, human_review_required).
      - factual_metrics: the exact numbers supplied to the prompt.
      - generated_at: ISO-8601 UTC timestamp.

    On any error (missing key, timeout, rate limit, malformed output) the
    endpoint returns HTTP 200 with explanation_type='error' and a safe
    error_message.  It never returns a fake LLM response.
    """
    # --- Reuse the same item/store resolution logic as the rule-engine endpoint ---
    query = {"item_id": item_id}
    if store_id:
        query["store_id"] = store_id
    try:
        rec_docs = list(recommendations.find(query).sort("store_id", 1).limit(12))
    except PyMongoError:
        raise HTTPException(status_code=503, detail=DB_ERROR_MESSAGE)

    if not rec_docs:
        raise HTTPException(
            status_code=404,
            detail=f"No recommendation found for item_id='{item_id}'"
            + (f" store_id='{store_id}'" if store_id else "") + ".",
        )

    if len(rec_docs) > 1:
        available = [d["store_id"] for d in rec_docs if d.get("store_id")]
        raise HTTPException(
            status_code=400,
            detail=(
                f"item_id='{item_id}' exists in {len(rec_docs)} stores: {available}. "
                "Add ?store_id=<value> to select one."
            ),
        )

    rec_doc = clean_document(rec_docs[0])

    prod_query = {"item_id": item_id}
    if store_id:
        prod_query["store_id"] = store_id
    try:
        prod_doc_raw = products.find_one(prod_query)
    except PyMongoError:
        raise HTTPException(status_code=503, detail=DB_ERROR_MESSAGE)

    prod_doc = clean_document(prod_doc_raw) if prod_doc_raw else {}

    # --- Delegate to the AI service (never raises; always returns a dict) ---
    result = generate_ai_explanation(prod_doc, rec_doc)

    return {
        "item_id":  rec_doc.get("item_id"),
        "store_id": rec_doc.get("store_id"),
        **result,
    }


@app.get("/recommendations/{item_id}")
def get_recommendations_by_item(
    item_id: str,
    store_id: Optional[str] = Query(None, description="Optional filter, e.g. CA_1"),
):
    """All recommendation documents matching an item_id (one per store)."""
    return documents_for_item(recommendations, item_id, store_id)


class DecisionRequest(BaseModel):
    action: str = Field(..., description="Decision action: 'approve' or 'reject'")
    notes: Optional[str] = Field(None, description="Optional manager notes")


@app.post("/recommendations/{item_id}/decision")
def post_recommendation_decision(
    item_id: str,
    body: DecisionRequest,
    store_id: Optional[str] = Query(
        None,
        description=(
            "Required when item_id is not unique across stores. "
            "Each item_id appears in up to 10 stores. "
            "If omitted and the item exists in multiple stores, a 400 error is returned."
        ),
    ),
):
    """
    Record an approval or rejection decision for a recommendation.
    Persists to decision_history collection and updates the recommendation document.
    """
    action = body.action.strip().lower()
    if action not in ("approve", "reject"):
        raise HTTPException(
            status_code=400,
            detail="Invalid action. Must be 'approve' or 'reject' (case-insensitive)."
        )

    query = {"item_id": item_id}
    if store_id:
        query["store_id"] = store_id
    try:
        rec_docs = list(recommendations.find(query).sort("store_id", 1).limit(12))
    except PyMongoError:
        raise HTTPException(status_code=503, detail=DB_ERROR_MESSAGE)

    if not rec_docs:
        raise HTTPException(
            status_code=404,
            detail=f"No recommendation found for item_id='{item_id}'"
            + (f" store_id='{store_id}'" if store_id else "") + ".",
        )

    if len(rec_docs) > 1:
        available = [d["store_id"] for d in rec_docs if d.get("store_id")]
        raise HTTPException(
            status_code=400,
            detail=(
                f"item_id='{item_id}' exists in {len(rec_docs)} stores: {available}. "
                "Add ?store_id=<value> to select one."
            ),
        )

    rec_doc = rec_docs[0]
    resolved_store_id = rec_doc.get("store_id")

    decided_at = datetime.utcnow().isoformat() + "Z"
    actor = "Local Demo Manager (Unauthenticated)"
    decision_status = "approved" if action == "approve" else "rejected"

    history_entry = {
        "item_id": item_id,
        "store_id": resolved_store_id,
        "action": action,
        "decision_status": decision_status,
        "notes": body.notes,
        "actor": actor,
        "decided_at": decided_at,
    }

    try:
        decision_history.insert_one(history_entry)
        recommendations.update_one(
            {"item_id": item_id, "store_id": resolved_store_id},
            {
                "$set": {
                    "decision_status": decision_status,
                    "decision_notes": body.notes,
                    "decided_at": decided_at,
                    "actor": actor,
                }
            }
        )
    except PyMongoError:
        raise HTTPException(status_code=503, detail="Could not write decision to database.")

    updated_rec = clean_document(recommendations.find_one({"item_id": item_id, "store_id": resolved_store_id}))
    history_cursor = decision_history.find({"item_id": item_id, "store_id": resolved_store_id}).sort("_id", -1)
    history_list = [clean_document(h) for h in history_cursor]

    return {
        "status": "success",
        "message": f"Recommendation successfully {decision_status}.",
        "item_id": item_id,
        "store_id": resolved_store_id,
        "decision_status": decision_status,
        "decision_notes": body.notes,
        "decided_at": decided_at,
        "actor": actor,
        "history": history_list,
        "recommendation": updated_rec,
    }


@app.get("/recommendations/{item_id}/decisions")
def get_recommendation_decisions(
    item_id: str,
    store_id: Optional[str] = Query(
        None,
        description=(
            "Required when item_id is not unique across stores. "
            "If omitted and the item exists in multiple stores, a 400 error is returned."
        ),
    ),
):
    """
    Return the decision history for a recommendation.
    """
    query = {"item_id": item_id}
    if store_id:
        query["store_id"] = store_id
    try:
        rec_docs = list(recommendations.find(query).sort("store_id", 1).limit(12))
    except PyMongoError:
        raise HTTPException(status_code=503, detail=DB_ERROR_MESSAGE)

    if not rec_docs:
        raise HTTPException(
            status_code=404,
            detail=f"No recommendation found for item_id='{item_id}'"
            + (f" store_id='{store_id}'" if store_id else "") + ".",
        )

    if len(rec_docs) > 1:
        available = [d["store_id"] for d in rec_docs if d.get("store_id")]
        raise HTTPException(
            status_code=400,
            detail=(
                f"item_id='{item_id}' exists in {len(rec_docs)} stores: {available}. "
                "Add ?store_id=<value> to select one."
            ),
        )

    resolved_store_id = rec_docs[0].get("store_id")
    try:
        cursor = decision_history.find({"item_id": item_id, "store_id": resolved_store_id}).sort("_id", -1)
        history = [clean_document(h) for h in cursor]
    except PyMongoError:
        raise HTTPException(status_code=503, detail=DB_ERROR_MESSAGE)

    return {
        "item_id": item_id,
        "store_id": resolved_store_id,
        "total_decisions": len(history),
        "history": history,
    }


@app.get("/recommendations/{item_id}/affinity")
def get_recommendation_affinity(
    item_id: str,
    store_id: Optional[str] = Query(None, description="Optional store_id filter."),
):
    """
    Retrieve Frequently Bought Together (product affinity) items for a given item_id.
    Note: Based on a synthetic demo basket dataset, clearly labeled as SYNTHETIC.
    """
    try:
        cursor = product_affinity.find({
            "$or": [{"item_a": item_id}, {"item_b": item_id}]
        }).sort("lift", -1).limit(5)
        results = [clean_document(doc) for doc in cursor]
    except PyMongoError:
        raise HTTPException(status_code=503, detail=DB_ERROR_MESSAGE)

    if not results:
        return {
            "item_id": item_id,
            "data_source": "SYNTHETIC_DEMO_BASKET_AFFINITY",
            "affinity_items": [],
            "message": "No synthetic affinity rules found for this item."
        }

    related = []
    for doc in results:
        partner = doc.get("item_b") if doc.get("item_a") == item_id else doc.get("item_a")
        related.append({
            "related_item_id": partner,
            "support": doc.get("support"),
            "confidence": doc.get("confidence"),
            "lift": doc.get("lift"),
            "co_occurrence_count": doc.get("co_occurrence_count"),
            "data_source": "SYNTHETIC_DEMO_BASKET_AFFINITY"
        })

    return {
        "item_id": item_id,
        "data_source": "SYNTHETIC_DEMO_BASKET_AFFINITY",
        "affinity_items": related
    }


@app.get("/segments")
def get_customer_segments():
    """
    Retrieve synthetic customer segments summary and characteristics.
    Note: Based on synthetic demo customer dataset, clearly labeled as SYNTHETIC DEMO DATA.
    """
    try:
        cursor = customer_segments.find({}).sort("customer_count", -1)
        results = [clean_document(doc) for doc in cursor]
    except PyMongoError:
        raise HTTPException(status_code=503, detail=DB_ERROR_MESSAGE)

    return {
        "data_source": "SYNTHETIC_DEMO_DATA",
        "description": "Customer segments derived from reproducible synthetic demo customer transactions.",
        "segments": results
    }


@app.get("/segments/promotions")
def get_segment_promotions():
    """
    Retrieve demo personalized promotion suggestions targeted by customer segment.
    Note: Clearly labeled as SYNTHETIC DEMO DATA.
    """
    try:
        cursor = segment_promotions.find({})
        results = [clean_document(doc) for doc in cursor]
    except PyMongoError:
        raise HTTPException(status_code=503, detail=DB_ERROR_MESSAGE)

    return {
        "data_source": "SYNTHETIC_DEMO_DATA",
        "description": "Segment-targeted promotional campaigns for demonstration purposes.",
        "promotions": results
    }


class CampaignOutcomeRequest(BaseModel):
    item_id: str = Field(..., description="Product item ID")
    store_id: str = Field(..., description="Store ID, e.g. CA_1")
    actual_redemptions: int = Field(..., ge=0, description="Actual promotion redemptions count")
    actual_sales_lift_pct: float = Field(..., description="Measured sales lift percentage")
    actual_revenue_gain: float = Field(..., description="Measured revenue gain")
    measured_period: str = Field(..., description="Time period when results were measured")
    data_source: str = Field("REAL_RETAILER_DATA", description="Data source: REAL_RETAILER_DATA or SYNTHETIC_DEMO_DATA")


@app.get("/campaign-reports")
def get_campaign_reports(
    store_id: Optional[str] = Query(None, description="Optional store_id filter, e.g. CA_1"),
):
    """
    Campaign Effectiveness and Impact Report summary.
    Summarizes recommendation approval/rejection/pending counts, decision rates,
    discount distributions, recommendation categories, and store summaries.
    Clearly distinguishes proposed/approved campaigns from executed campaigns.
    """
    try:
        return compute_campaign_report(store_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/campaign-reports/outcomes")
def get_campaign_outcomes_endpoint(
    store_id: Optional[str] = Query(None, description="Optional store_id filter, e.g. CA_1"),
):
    """
    Retrieve measured campaign outcomes.
    If no actual outcomes are recorded, returns structured demonstration records
    clearly labeled as SYNTHETIC DEMO DATA.
    """
    try:
        return get_campaign_outcomes_list(store_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/campaign-reports/outcomes")
def post_campaign_outcome_endpoint(body: CampaignOutcomeRequest):
    """
    Record or evaluate actual campaign results.
    Keeps proposed recommendation fields separate from measured campaign outcomes.
    Validates input fields and supports REAL_RETAILER_DATA or SYNTHETIC_DEMO_DATA labeling.
    """
    try:
        result = save_campaign_outcome(body.model_dump())
        return {
            "status": "success",
            "message": "Campaign outcome successfully recorded.",
            "outcome": result
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


class MappingRequest(BaseModel):
    dataset_type: str = Field(..., description="Dataset type: products, sales, inventory, prices, customers, stores, campaign_outcomes")
    mapping: Dict[str, str] = Field(..., description="Column mapping dictionary {original_column: canonical_field}")
    sheet_name: Optional[str] = Field(None, description="Sheet name if Excel file")


@app.post("/ingest/upload")
def upload_retailer_data(
    file: UploadFile = File(...),
    retail_id: str = Depends(get_current_retailer_id),
):
    """
    Upload a retailer dataset (.csv or .xlsx/.xls) and create a tenant-scoped import batch.
    Performs header inspection, dataset type inference, and initial validation preview.
    """
    ext = validate_file_upload(file)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
    tmp_path = tmp.name
    total_size = 0
    try:
        while True:
            chunk = file.file.read(1024 * 1024)
            if not chunk:
                break
            total_size += len(chunk)
            if total_size > MAX_UPLOAD_SIZE:
                tmp.close()
                os.unlink(tmp_path)
                raise HTTPException(status_code=413, detail="File size exceeds maximum allowed limit of 50 MB.")
            tmp.write(chunk)
        tmp.close()
    except Exception as e:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise HTTPException(status_code=400, detail=f"Failed to read upload file: {str(e)}")

    try:
        df = parse_uploaded_file(tmp_path, ext)
        columns = list(df.columns)
        dataset_type, mapping = infer_dataset_type_and_mapping(columns)
    except Exception as e:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {str(e)}")

    batch_id = str(uuid.uuid4())
    batch_doc = {
        "batch_id": batch_id,
        "retail_id": retail_id,
        "filename": file.filename,
        "file_path": tmp_path,
        "ext": ext,
        "columns": columns,
        "dataset_type": dataset_type,
        "mapping": mapping,
        "status": "uploaded",
        "created_at": datetime.utcnow(),
        "total_rows": len(df),
    }
    tenant_import_batches.insert_one(batch_doc)

    valid, errors, missing = validate_rows_against_schema(df, dataset_type, mapping, retail_id, batch_id)

    return {
        "batch_id": batch_id,
        "retail_id": retail_id,
        "filename": file.filename,
        "columns": columns,
        "inferred_dataset_type": dataset_type,
        "inferred_mapping": mapping,
        "total_rows": len(df),
        "valid_rows_count": len(valid),
        "invalid_rows_count": len(errors),
        "missing_required_columns": missing,
        "sample_preview": clean_document(valid[:5]),
        "row_errors": clean_document(errors[:10]),
    }


@app.get("/ingest/batches")
def list_import_batches(
    retail_id: str = Depends(get_current_retailer_id),
):
    """List tenant-scoped import batches."""
    try:
        cursor = tenant_import_batches.find(get_tenant_query(retail_id)).sort("created_at", -1)
        results = [clean_document(doc) for doc in cursor]
        for r in results:
            r.pop("file_path", None)
        return {"retail_id": retail_id, "batches": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/ingest/batches/{batch_id}")
def get_import_batch_status(
    batch_id: str,
    retail_id: str = Depends(get_current_retailer_id),
):
    """Retrieve tenant-scoped import batch details and status."""
    query = get_tenant_query(retail_id, {"batch_id": batch_id})
    batch = tenant_import_batches.find_one(query)
    if not batch:
        raise HTTPException(status_code=404, detail=f"Import batch '{batch_id}' not found for tenant.")
    
    batch_copy = dict(batch)
    batch_copy.pop("file_path", None)
    return clean_document(batch_copy)


@app.post("/ingest/batches/{batch_id}/preview")
def preview_import_batch(
    batch_id: str,
    body: MappingRequest,
    retail_id: str = Depends(get_current_retailer_id),
):
    """
    Validate mapped data against canonical schemas and return a preview.
    Does NOT persist business records into canonical tenant collections.
    """
    query = get_tenant_query(retail_id, {"batch_id": batch_id})
    batch = tenant_import_batches.find_one(query)
    if not batch:
        raise HTTPException(status_code=404, detail=f"Import batch '{batch_id}' not found for tenant.")

    file_path = batch.get("file_path")
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=400, detail="Associated temporary upload file no longer exists. Please re-upload.")

    try:
        df = parse_uploaded_file(file_path, batch["ext"], body.sheet_name)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse file for preview: {str(e)}")

    valid, errors, missing = validate_rows_against_schema(df, body.dataset_type, body.mapping, retail_id, batch_id)

    return {
        "batch_id": batch_id,
        "dataset_type": body.dataset_type,
        "total_rows": len(df),
        "valid_rows_count": len(valid),
        "invalid_rows_count": len(errors),
        "missing_required_columns": missing,
        "sample_preview": clean_document(valid[:10]),
        "row_errors": clean_document(errors[:20]),
    }


@app.post("/ingest/batches/{batch_id}/commit")
def commit_import_batch(
    batch_id: str,
    body: MappingRequest,
    retail_id: str = Depends(get_current_retailer_id),
):
    """
    Commit validated batch records into the canonical tenant collection.
    Enforces idempotency guard, successful validation, and cleanup of temporary files.
    """
    query = get_tenant_query(retail_id, {"batch_id": batch_id})
    batch = tenant_import_batches.find_one(query)
    if not batch:
        raise HTTPException(status_code=404, detail=f"Import batch '{batch_id}' not found for tenant.")

    if batch.get("status") == "committed":
        raise HTTPException(status_code=400, detail=f"Import batch '{batch_id}' has already been committed.")

    file_path = batch.get("file_path")
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=400, detail="Associated temporary upload file no longer exists. Please re-upload.")

    try:
        df = parse_uploaded_file(file_path, batch["ext"], body.sheet_name)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse file for commit: {str(e)}")

    valid, errors, missing = validate_rows_against_schema(df, body.dataset_type, body.mapping, retail_id, batch_id)

    if missing:
        raise HTTPException(status_code=400, detail=f"Cannot commit batch due to missing required columns: {missing}")

    if not valid and errors:
        raise HTTPException(status_code=400, detail="Cannot commit batch: all rows failed validation.")

    collection_map = {
        "products": tenant_products,
        "sales": tenant_sales,
        "inventory": tenant_inventory,
        "prices": tenant_prices,
        "customers": tenant_customers,
        "stores": tenant_stores,
        "campaign_outcomes": tenant_campaign_outcomes,
    }

    target_coll = collection_map.get(body.dataset_type, tenant_products)

    try:
        if valid:
            target_coll.insert_many(valid)
        
        tenant_import_batches.update_one(
            {"_id": batch["_id"]},
            {
                "$set": {
                    "status": "committed",
                    "dataset_type": body.dataset_type,
                    "mapping": body.mapping,
                    "valid_rows_count": len(valid),
                    "invalid_rows_count": len(errors),
                    "committed_at": datetime.utcnow(),
                }
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database commit failed: {str(e)}")
    finally:
        if file_path and os.path.exists(file_path):
            try:
                os.unlink(file_path)
            except Exception:
                pass

    return {
        "status": "success",
        "message": f"Successfully committed {len(valid)} records for batch {batch_id}.",
        "batch_id": batch_id,
        "dataset_type": body.dataset_type,
        "committed_records_count": len(valid),
        "invalid_records_count": len(errors),
    }


@app.get("/analytics/readiness")
def get_analytics_readiness(
    retail_id: str = Depends(get_current_retailer_id),
):
    """Assess data readiness across canonical datasets for the tenant retailer."""
    return assess_data_readiness(retail_id)


@app.post("/analytics/run")
def run_analytics_endpoint(
    retail_id: str = Depends(get_current_retailer_id),
):
    """
    Run tenant-scoped analytics (Forecasting, Segmentation, Affinity, Inventory, Recommendations)
    using only successfully committed records for this retailer.
    """
    try:
        result = run_tenant_analytics(retail_id)
        return {
            "status": "success",
            "message": "Analytics successfully computed for retailer.",
            "analytics": result
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analytics/results")
def get_analytics_results(
    retail_id: str = Depends(get_current_retailer_id),
):
    """Retrieve the latest computed analytics run for the tenant retailer."""
    result = get_latest_analytics_run(retail_id)
    if not result:
        return {
            "retail_id": retail_id,
            "status": "no_runs_found",
            "message": "No analytics runs found for this retailer yet. Run analytics first."
        }
    return result


@app.get("/analytics/decisions")
def get_analytics_decisions(
    item_id: Optional[str] = Query(None, description="Optional item_id filter"),
    store_id: Optional[str] = Query(None, description="Optional store_id filter"),
    retail_id: str = Depends(get_current_retailer_id),
):
    """
    Retrieve unified AI/ML decision engine output for the tenant retailer.
    Requires X-Retailer-ID header, respects tenant isolation, and provides
    deterministic recommendations, reliability classification, evidence, and warnings.
    """
    return compute_tenant_decisions(retail_id, item_id, store_id)
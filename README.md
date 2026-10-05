# IntelliPromo
AI-Driven Personalized Promotion and Inventory Alignment Planner

A full-stack, enterprise-grade decision-support platform that empowers retail category managers to align demand forecasting, inventory coverage, customer segmentation, basket affinity, and personalized promotion recommendations.

---

## 1. Problem
Retailers struggle to synchronize demand sensing, inventory holding levels, customer segment behaviors, and promotional pricing across multi-store networks. Fragmented systems lead to stockouts, excess inventory write-downs, unprofitable discounts, and unexplainable AI black-box decisions.

## 2. Solution
IntelliPromo provides an end-to-end multi-tenant platform featuring:
- **Multi-Tenant Ingestion & Validation**: Secure CSV/Excel data upload with schema mapping and validation against canonical schemas.
- **Strict Tenant Isolation**: Complete data separation across tenants using `X-Retailer-ID` headers.
- **Reproducible Demand Forecasting Benchmark**: Chronological train/validation/test splitting, zero data leakage, and rigorous evaluation of Naive, Moving Average, and Random Forest models with MAE/RMSE metrics.
- **Inventory & Risk Alignment**: Automated coverage days calculation and stockout (< 14 days) / excess (> 60 days) risk detection.
- **AI/ML Decision Engine & Explainability**: Deterministic evidence-based recommendations coupled with transparent reliability tiers (`HIGH`, `MEDIUM`, `LOW`, `INSUFFICIENT_DATA`) and structured explanations.
- **Interactive React Dashboard**: Modern analytics hub with readiness checks, forecasting models, inventory risks, AI decisions, and legacy M5 demo support.

---

## 3. Architecture Overview

```
Retailer CSV/Excel Upload
         ↓
 Tenant-Scoped Ingestion & Validation
         ↓
      MongoDB (Tenant Collections)
         ↓
      FastAPI Backend (`src/api/main.py`)
      ├── Data Readiness & Analytics (`retailer_analytics_service.py`)
      ├── Forecasting Benchmark (`forecasting_benchmark.py`)
      └── Unified AI Decision Engine (`ai_decision_engine.py`)
         ↓
 React + Vite + Tailwind Frontend (`frontend/src/App.jsx`)
```

---

## 4. Machine Learning & Forecasting Methodology
- **Chronological Evaluation**: Train (70%), Validation (15%), and Test (15%) splits. Future data is never used in historical feature calculation.
- **Features**: Lag-1 demand and 7-day rolling mean computed strictly using past observation timestamps.
- **Models Evaluated**:
  1. *Naive Baseline*: Last observed demand.
  2. *Moving Average Baseline*: Recent 7-day rolling average.
  3. *Random Forest Regression*: Non-linear ML model evaluated when sufficient history is present.
- **Metrics**: Mean Absolute Error (MAE) and Root Mean Squared Error (RMSE) calculated on held-out test data. Model selection relies exclusively on validation performance.

---

## 5. AI Decision Engine & Explainability
- **Source of Truth**: Deterministic analytics, rules, and model evaluations remain the absolute source of truth. LLMs or AI layers never fabricate metrics or override recommendations.
- **Relireliability Tiers**:
  - `HIGH`: ≥ 30 observation days, valid inventory, and successful benchmark evaluation.
  - `MEDIUM`: 10–29 observation days with inventory alignment.
  - `LOW`: < 10 observation days or sparse history.
  - `INSUFFICIENT_DATA`: No sales or inventory records.
- **Transparent Evidence**: Every recommendation includes structured evidence and warnings traceable to actual stored fields.

---

## 6. Retailer Ingestion & Tenant Security
- Supports file uploads (`.csv`, `.xlsx`, `.xls`) with automated column inspection and mapping.
- Enforces strict tenant isolation via `X-Retailer-ID` headers across all database queries and API endpoints.

---

## 7. Limitations
- Inventory snapshots and unit costs are simulated/assumed where actual ERP data is missing.
- Demand figures represent historical proxies or benchmark forecasts, not guaranteed future sales.
- No causal promotion lift is estimated without explicit promotion-treatment history.
- Local demo authentication uses unauthenticated header headers (`X-Retailer-ID`).

---

## 8. Running Locally

### Prerequisites
- Python 3.10+ (with `.venv` activated)
- Node.js 18+ & npm
- MongoDB running on `localhost:27017`

### Backend Startup
```bash
uvicorn src.api.main:app --reload --host 127.0.0.1 --port 8000
```
API Docs: `http://127.0.0.1:8000/docs`

### Frontend Startup
```bash
cd frontend
npm run dev
```
UI App: `http://localhost:5173`

---

## 9. Example Workflow
1. **Upload Data**: Upload sales and inventory CSV files via the Ingestion Hub.
2. **Validate & Commit**: Preview schema mappings, validate rows, and commit to tenant collections.
3. **Run Analytics**: Execute data readiness checks and forecasting benchmark evaluation.
4. **View AI Decisions**: Inspect unified recommendations, reliability tiers, evidence, and coverage risks at `GET /analytics/decisions`.
5. **Review Recommendations**: Category managers review recommendations and record approval/rejection decisions.

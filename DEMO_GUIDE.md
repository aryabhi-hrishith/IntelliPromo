# Demo Guide — IntelliPromo (AI-Driven Promotion & Inventory Alignment Planner)

*For demonstrators, evaluators, and faculty reviewers.*

---

## Prerequisites Checklist

| # | Requirement | How to verify |
| :--- | :--- | :--- |
| 1 | Python 3.10+ virtual environment active | `python --version` |
| 2 | Required Python packages installed | `pip show fastapi pymongo google-genai pandas scikit-learn` |
| 3 | MongoDB running on `localhost:27017` | `mongosh --eval "db.adminCommand('ping')"` |
| 4 | Database populated (30,490 docs each) | See step below |
| 5 | `.env` file present with `GEMINI_API_KEY` | Check `.env` exists in root |
| 6 | Node.js 18+ installed | `node --version` |

**Verify database population (from project root):**
```bash
.venv\Scripts\python -c "import pymongo; c = pymongo.MongoClient(); db = c['retail_promotion_planner']; print('Products:', db.products.count_documents({})); print('Recommendations:', db.recommendations.count_documents({}))"
```
Both counts should print **30,490**.

---

## Start-Up Sequence

Open **two separate terminal windows** from the project root.

### Terminal 1 — FastAPI Backend
```bash
# Activate virtual environment (Windows)
.venv\Scripts\activate

# Start the API server
uvicorn src.api.main:app --reload --host 127.0.0.1 --port 8000
```
Confirm health check: `http://127.0.0.1:8000/` returns `{"status": "ok", ...}`.

### Terminal 2 — React Frontend
```bash
cd frontend
npm run dev
```
Open **`http://localhost:5173`** in your browser.

---

## Comprehensive Live Walkthrough (15–20 minutes)

### Step 1 — Dashboard View (`/`)
1. Point out the **store selector** in the top bar (default: CA_1).
2. Walk through the four **KPI cards**: Average Simulated Stock, Low Stock Alerts (<14 days), Active Promotions count, Average Discount %.
3. Review the three **Recharts**:
   - Top 10 Products by Average Daily Demand (Bar chart).
   - Promotion Distribution by discount tier (Pie chart).
   - Stock Units vs Coverage Days (Composed chart).
4. Switch store selector to `TX_1` — observe real-time re-rendering.

### Step 2 — Promotions & Approval Workflow (`/promotions`)
1. Click **"Promotions"** in the sidebar.
2. Review table columns: Item ID, Store, Selling Price, Assumed Cost, Coverage, Recommendation badge, Candidate Discount, Decision Status.
3. Click **Approve** or **Reject** on a recommendation card; observe immediate status update and decision logging.
4. Click **"Why this?"** on any item to open the explanation modal.

### Step 3 — Explanation Modal (Rule Engine & AI Tabs)
1. **Rule Engine Tab**: Displays deterministic threshold logic (e.g. coverage > 30 days), margin math, and prototype data labels (`HISTORICAL PROXY`, `SIMULATED`, `ASSUMED`).
2. **✨ AI Explanation Tab**: Click **Generate AI Explanation** to call Google Gemini. Observe the purple **AI-GENERATED** badge, structured cards (Summary, Supporting Factors, Inventory Context, Discount Context, Limitations), and mandatory **Human Review Required** advisory.

### Step 4 — Inventory View (`/inventory`)
1. Click **"Inventory"** in the sidebar.
2. Review stock levels, daily run rate, coverage days, and status badges (Critical <7d, Low <14d, Normal 14-30d, Excess >30d).

### Step 5 — Customer Segments & Promos (`/segments`)
1. Click **"Segments & Promos"** in the sidebar.
2. Review synthetic customer clusters (High-Value, Frequent, Value-Seeking, Occasional) and segment-targeted campaign suggestions clearly labeled with **⚠️ SYNTHETIC DEMO DATA** badges.

### Step 6 — Campaign Reports & Impact Evaluation (`/reports`)
1. Click **"Campaign Reports"** in the sidebar.
2. Review KPI summary cards, decision status breakdown chart, discount distribution chart, and recommendation categories.
3. Note the mandatory warning banner distinguishing proposed/approved campaigns from executed campaigns.
4. Use the **Campaign Outcome Evaluation Form** to record actual or synthetic redemptions, sales lift %, and revenue gain, verifying they appear in the measured outcomes table with explicit data-source labels (`SYNTHETIC_DEMO_DATA` or `REAL_RETAILER_DATA`).

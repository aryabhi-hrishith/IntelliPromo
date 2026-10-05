# Final Submission Checklist

**Project:** AI-Driven Personalized Promotion and Inventory Alignment Planner  
**Audit date:** 2026-10-03  
**Auditor:** Automated + manual verification (Step 29)

---

## Legend

| Symbol | Meaning |
| :---: | :--- |
| ✅ | Verified and passing |
| ⚠️ | Verified with a caveat — read the note |
| 🔲 | Requires **your manual action** before submission |
| ❌ | Defect found and fixed in this audit |

---

## 1. Environment and Start-Up

| # | Check | Status | Notes |
| :--- | :--- | :---: | :--- |
| 1.1 | Python 3.14 virtual environment (`.venv`) | ✅ | Confirmed via test runner output |
| 1.2 | All packages installed from `requirements.txt` | ✅ | Tests pass; live API running |
| 1.3 | MongoDB 8.3.4 reachable on `localhost:27017` | ✅ | Live API returns `"database": "connected"` |
| 1.4 | `products` collection: 30,490 documents | ✅ | Verified via live API |
| 1.5 | `recommendations` collection: 30,490 documents | ✅ | Verified via live API |
| 1.6 | `.env` present in project root | ✅ | File exists; loaded by `load_dotenv()` |
| 1.7 | `GEMINI_API_KEY` set in `.env` | ✅ | Live AI round-trip succeeds |
| 1.8 | `GEMINI_MODEL` set to `gemini-3.5-flash-lite` in `.env` | ✅ | Confirmed via live `/ai-explanation` response |
| 1.9 | Node.js 18+ installed | ✅ | Vite dev server running |

### Exact Start-Up Commands

```bash
# Terminal 1 — Backend
.venv\Scripts\activate
uvicorn src.api.main:app --reload --host 127.0.0.1 --port 8000

# Terminal 2 — Frontend
cd frontend
npm run dev
```

URLs:
- Frontend: `http://localhost:5173`
- API health: `http://127.0.0.1:8000/`
- API docs: `http://127.0.0.1:8000/docs`

---

## 2. Automated Tests

| # | Check | Status | Notes |
| :--- | :--- | :---: | :--- |
| 2.1 | Full test suite: 47 passed, 0 failed | ✅ | Re-run this audit: `47 passed, 2 warnings in 20.58s` |
| 2.2 | Offline unit tests pass without MongoDB or API key | ✅ | `-k "not live and not integration"` confirms |
| 2.3 | API integration tests pass with MongoDB | ✅ | `-m "not live"` confirms |
| 2.4 | Live Gemini test passes with configured API key | ✅ | `TestLiveProvider::test_live_round_trip_returns_valid_structured_response PASSED` |
| 2.5 | 2 deprecation warnings present (third-party) | ⚠️ | `StarletteDeprecationWarning` (httpx) and `_UnionGenericAlias` (google-genai types.py) — not application code, no action required |
| 2.6 | Browser automation (Playwright) | ⚠️ | Blocked by CDN 404 during Playwright driver download. UI verified via `npm run build` and manual checklist instead. |

### Re-Run Commands

```bash
# From project root with .venv active and MongoDB running:
.venv\Scripts\pytest tests/ -v

# Offline only (no MongoDB or API key):
.venv\Scripts\pytest tests/test_ai_explanation.py -v -k "not live and not integration"
```

---

## 3. ML Metrics Verification

| # | Check | Status | Notes |
| :--- | :--- | :---: | :--- |
| 3.1 | Naive MAE = 5.6024 | ✅ | Reproduced from `data/processed/forecast_predictions.csv` |
| 3.2 | RF MAE = 4.2107 (−24.8% vs. naive) | ✅ | Reproduced and matches `reports/forecast_model_metrics.txt` |
| 3.3 | Naive RMSE = 8.9339 | ✅ | Reproduced from prediction artifact |
| 3.4 | RF RMSE = 6.1291 (−31.4% vs. naive) | ✅ | Reproduced and matches metrics file |
| 3.5 | Test rows = 2,520 across 90 series | ✅ | Confirmed in `forecast_model_metrics.txt` |
| 3.6 | Test window = 2016-03-28 to 2016-04-24 | ✅ | Confirmed in metrics file |

---

## 4. Documentation Accuracy

| # | Check | Status | Notes |
| :--- | :--- | :---: | :--- |
| 4.1 | ML metrics consistent across all 4 docs | ✅ | All documents reference the same verified figures |
| 4.2 | API routes accurate in all docs | ✅ | Verified against `src/api/main.py` |
| 4.3 | Demo route example used valid item_id format | ❌→✅ | Fixed: `FOODS_1_001_CA_1` replaced with `FOODS_1_001?store_id=CA_1` |
| 4.4 | Active Gemini model documented correctly | ❌→✅ | Fixed: example JSON updated to `gemini-3.5-flash-lite`; code default (gemini-2.0-flash-lite) clarified as the fallback |
| 4.5 | Simulated inventory labelled everywhere | ✅ | UI, API, prompt, README, PROJECT_REPORT all carry the label |
| 4.6 | Assumed cost (0.7×) disclosed | ✅ | All docs and UI state the assumption explicitly |
| 4.7 | Historical proxy demand disclosed | ✅ | Section 5.5 of PROJECT_REPORT, TESTING_REPORT §7, DEMO_GUIDE §1 |
| 4.8 | No fabricated citations, deployment URLs, or test results | ✅ | All metrics are reproduced from stored artifacts |
| 4.9 | Billing/quota caveat present for Gemini | ✅ | In README §2, PROJECT_REPORT §7.5, `.env.example` |
| 4.10 | `human_review_required` advisory documented | ✅ | API schema, frontend, PROJECT_REPORT §7.2 |
| 4.11 | Cross-reference links (README ↔ reports) | ✅ | README links to PROJECT_REPORT, DEMO_GUIDE, TESTING_REPORT |

---

## 5. Security and Git

| # | Check | Status | Notes |
| :--- | :--- | :---: | :--- |
| 5.1 | `.env` excluded by `.gitignore` | ✅ | Confirmed in `.gitignore` |
| 5.2 | `.env.example` contains only placeholder values | ✅ | `GEMINI_API_KEY=YOUR_KEY_HERE`, no real key |
| 5.3 | `node_modules/` excluded by `.gitignore` | ❌→✅ | Fixed: `frontend/node_modules/` added |
| 5.4 | `data/processed/*` excluded | ✅ | Already present |
| 5.5 | `data/raw/*` excluded | ✅ | Already present |
| 5.6 | `reports/figures/*` excluded | ❌→✅ | Fixed: added to `.gitignore` |
| 5.7 | `frontend/dist/` excluded | ❌→✅ | Fixed: added to `.gitignore` |
| 5.8 | `*.pkl` / `*.joblib` model files excluded | ❌→✅ | Fixed: added to `.gitignore` |
| 5.9 | `.venv-1/` (second venv) excluded | ❌→✅ | Fixed: added to `.gitignore` |
| 5.10 | No API key values printed or logged | ✅ | Service logs errors without exposing credentials |
| 5.11 | Git repository initialised | 🔲 | **No `.git` directory found.** Run `git init` before submission (see action below). |

### Action Required — Initialise Git

```bash
# From project root:
git init
git add .
# Review what will be staged — confirm no secrets or large data files:
git status
git commit -m "Initial submission commit"
```

> **Before `git add .`**, run `git status` and verify that `.env`, `data/processed/`, `data/raw/`, `node_modules/`, and `reports/figures/` are **not** listed as staged. The updated `.gitignore` should exclude them.

---

## 6. Screenshots

| # | Filename | Status |
| :--- | :--- | :---: |
| 1 | `screenshots/01_dashboard_ca1.png` | 🔲 |
| 2 | `screenshots/02_dashboard_tx1.png` | 🔲 |
| 3 | `screenshots/03_promotions_table.png` | 🔲 |
| 4 | `screenshots/04_promotions_search.png` | 🔲 |
| 5 | `screenshots/05_modal_rule_engine.png` | 🔲 |
| 6 | `screenshots/06_modal_ai_explanation.png` | 🔲 |
| 7 | `screenshots/07_modal_human_review.png` | 🔲 |
| 8 | `screenshots/08_inventory_page.png` | 🔲 |
| 9 | `screenshots/09_api_docs.png` | 🔲 |

See `screenshots/README.md` for exact capture instructions.

> Browser automation was blocked during this audit (Playwright CDN 404). All screenshots must be captured manually from the running application.

---

## 7. Known Limitations (for Documentation Purposes)

These are disclosed in PROJECT_REPORT.md §11 and TESTING_REPORT.md §7. Summarised here for reference:

| Limitation | Where disclosed |
| :--- | :--- |
| Inventory is simulated (seed 42), not real stock | UI, API, AI prompt, README, PROJECT_REPORT |
| Unit cost is assumed (0.7 × price), not real COGS | UI, API, AI prompt, README, PROJECT_REPORT |
| Demand figures are 28-day historical averages, not forecasts | UI, PROJECT_REPORT §5.5, TESTING_REPORT §7 |
| No causal promotional uplift measurement | PROJECT_REPORT §11 |
| Discount tiers are heuristic prototypes | PROJECT_REPORT §6.1, TESTING_REPORT §7 |
| Forecast evaluated on one window (28 days, 90 series, 1 seed) | PROJECT_REPORT §11, metrics file footer |
| Browser automation blocked (Playwright CDN 404) | TESTING_REPORT §7.3 |
| `human_review_required: true` always enforced | API schema, PROJECT_REPORT §7.2 |

---

## 8. Demo Preparation Steps

Complete these steps in order before the live demonstration:

1. **✅ Backend running** — confirm `http://127.0.0.1:8000/` returns `"database": "connected"`.
2. **✅ Frontend running** — confirm `http://localhost:5173` loads the Dashboard.
3. **🔲 Capture screenshots** — follow `screenshots/README.md`.
4. **🔲 Git commit** — initialise repo, run `git status` to verify no secrets staged, then commit.
5. **🔲 Test run** — execute `.venv\Scripts\pytest tests/ -v` and confirm 47 passed.
6. **🔲 Tab pre-open** — during demo, pre-open two browser tabs: `http://localhost:5173` and `http://127.0.0.1:8000/docs`.
7. **🔲 Rate limit buffer** — avoid generating multiple AI explanations in rapid succession; the free tier has per-minute rate limits.
8. **🔲 Slide/notes prep** — use the Faculty Q&A section in `DEMO_GUIDE.md` to prepare spoken answers.

---

## Summary

| Category | Verified ✅ | Fixed ❌→✅ | Manual action 🔲 | Caveat ⚠️ |
| :--- | :---: | :---: | :---: | :---: |
| Environment & Start-Up | 9 | 0 | 0 | 0 |
| Automated Tests | 4 | 0 | 0 | 2 |
| ML Metrics | 6 | 0 | 0 | 0 |
| Documentation Accuracy | 9 | 2 | 0 | 0 |
| Security & Git | 5 | 5 | 1 | 0 |
| Screenshots | 0 | 0 | 9 | 0 |
| **Total** | **33** | **7** | **10** | **2** |

**The application is verified and ready for submission pending the 10 manual actions above (git init + 9 screenshots).**

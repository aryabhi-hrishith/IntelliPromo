# Screenshots

Capture the following UI states with both servers running (`uvicorn` on port 8000, `npm run dev` on port 5173).

Save each file in this directory using the exact filename listed below.

---

## Required Screenshots

| # | Filename | Page | State to capture |
| :--- | :--- | :--- | :--- |
| 1 | `01_dashboard_ca1.png` | Dashboard (`/`) | Default view — store CA_1, all 4 KPI cards and 3 charts visible |
| 2 | `02_dashboard_tx1.png` | Dashboard (`/`) | Store selector changed to TX_1 — shows re-rendered data |
| 3 | `03_promotions_table.png` | Promotions (`/promotions`) | Recommendations table with badge colours visible |
| 4 | `04_promotions_search.png` | Promotions (`/promotions`) | Search bar filtered to `FOODS_1` |
| 5 | `05_modal_rule_engine.png` | Promotions modal | "Rule Engine" tab selected — full explanation visible |
| 6 | `06_modal_ai_explanation.png` | Promotions modal | "✨ AI Explanation" tab — purple AI-GENERATED badge and all cards visible |
| 7 | `07_modal_human_review.png` | Promotions modal | Scroll to yellow "Human Review Required" advisory card |
| 8 | `08_inventory_page.png` | Inventory (`/inventory`) | Table with Critical/Low/Normal/Excess status badges |
| 9 | `09_api_docs.png` | `http://127.0.0.1:8000/docs` | Swagger UI with endpoint list visible |

---

## How to Capture

1. Start both servers (see `DEMO_GUIDE.md`).
2. Open `http://localhost:5173` in Chrome or Firefox.
3. Use the browser's built-in screenshot or a tool like **ShareX**, **Lightshot**, or **Snipping Tool** (Win+Shift+S on Windows).
4. Save files here as PNG at a resolution of at least 1280 × 800.

> **Note:** These screenshots must be captured manually from a running instance of the application. They cannot be generated automatically.

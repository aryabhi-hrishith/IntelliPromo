# AI-Driven Personalized Promotion and Inventory Alignment Planner (IntelliPromo)

## Academic Project Report — Final Submission Version

| Field | Details |
| :--- | :--- |
| **IntelliPromo** | AI-Driven Personalized Promotion and Inventory Alignment Planner (IntelliPromo) |
| **Arya abhi hrishith** | 
| **24011A6624** | 
| **CSE** | 
| **JNTUH** | 
| ** [2026–2027]** | 
| **Core Dataset** | Walmart M5 Forecasting (Kaggle, CC BY 4.0) |
| **Backend Stack** | Python 3.14, FastAPI, MongoDB |
| **Frontend Stack** | React 18, Vite, Tailwind CSS, Recharts, Lucide Icons |
| **AI / LLM Layer** | Google Gemini Developer API via `google-genai` SDK |
| **Test Suite** | 70 automated tests — 70 passed, 0 failed |

---

## Abstract

Retail category managers face significant challenges in simultaneously balancing demand forecasting, inventory holding costs, stockout prevention, and promotional discount planning across thousands of SKUs and multiple store locations. This project presents **IntelliPromo**, a full-stack, AI-assisted decision-support system that integrates historical sales data, supervised machine learning, rule-based inventory optimization, LLM-powered natural-language explanations, customer segmentation, product affinity analysis, and campaign effectiveness reporting. 

Using the hierarchical Walmart M5 sales dataset as an empirical baseline, IntelliPromo trains a Random Forest demand forecasting model that outperforms a lag-0 naive baseline by 24.8% in Mean Absolute Error (MAE) and 31.4% in Root Mean Square Error (RMSE). A deterministic rule engine classifies inventory coverage and demand trends into actionable promotion recommendations with enforced margin safety thresholds (minimum 5% post-discount margin). Furthermore, an LLM explanation layer powered by Google Gemini provides grounded, plain-language justifications without altering underlying recommendation logic. Human-in-the-loop workflows enable managers to approve or reject recommendations with persistent decision history. Finally, synthetic customer segmentation, basket affinity analysis, and campaign impact reporting modules deliver a comprehensive, end-to-end promotion planning ecosystem. All automated tests (70/70) and frontend production builds pass successfully.

**Keywords:** Retail Analytics, Demand Forecasting, Inventory Optimization, Promotion Planning, LLM Explanations, FastAPI, React, MongoDB.

---

## 1. Introduction and Project Background

Modern retail enterprises operate in highly competitive environments where pricing strategy, promotional discounting, and inventory availability dictate profitability and customer loyalty. Category managers are tasked with overseeing thousands of Stock Keeping Units (SKUs) across diverse geographic locations. Manual decision-making often leads to suboptimal promotional markdowns, excessive stockholding of slow-moving inventory, or costly stockouts of high-demand items.

IntelliPromo bridges the gap between raw retail transactional data and actionable management decisions. Rather than executing fully autonomous, black-box automated pricing, IntelliPromo operates as a **human-in-the-loop decision-support system**. It combines classical supervised machine learning for demand forecasting, deterministic heuristic rules for inventory alignment, generative AI for transparent explanations, and structured auditing workflows to empower category managers with rigorous analytical insights.

---

## 2. Problem Statement

Retail organizations lack unified platforms that bridge predictive demand modeling with transparent, margin-safe promotional planning and inventory alignment. Specifically, category managers struggle with:
1. **Data Overload**: Navigating massive daily sales logs across multiple stores without automated prioritization of overstocked or declining-demand SKUs.
2. **Opaque Recommendations**: Algorithmic pricing tools that offer no visibility into *why* a discount was suggested or whether gross margins remain legally and financially viable.
3. **Execution Disconnect**: The absence of structured approval workflows, decision history tracking, and campaign effectiveness reporting.

> *How can structured sales history, predictive demand modeling, and inventory heuristics be transformed into prioritized, transparent, margin-safe promotional recommendations and impact reports that retail managers can trust and review?*

---

## 3. Project Objectives and Scope

### 3.1 Objectives
- **Predictive Demand Modeling**: Train and evaluate a supervised machine learning model (Random Forest) on historical retail data to predict item-store unit demand, outperforming naive baselines.
- **Inventory & Promotion Alignment**: Implement a deterministic rule engine that evaluates stock coverage days, demand trends, and gross margin constraints to generate structured promotion recommendations.
- **Explainable AI Integration**: Provide dual-level explanations—deterministic rule-engine breakdowns and Google Gemini LLM-generated plain-language summaries—grounded strictly in MongoDB facts.
- **Governance & Approval Workflows**: Enable managers to record approval or rejection decisions with persistent decision history.
- **Customer & Basket Intelligence**: Model synthetic customer segments and Frequently Bought Together product affinity rules.
- **Campaign Effectiveness Reporting**: Summarize decision distributions and evaluate campaign outcomes separately from proposed recommendations.

### 3.2 Scope
- **Data Scope**: Utilizes the public Walmart M5 forecasting dataset (CA, TX, WI stores) supplemented by reproducible synthetic customer and basket simulations.
- **Operational Scope**: Advisory decision support for human review. Inventory is simulated and unit costs are assumed (30% gross margin baseline) as M5 lacks wholesale cost data. Approvals represent human authorization and do not trigger automated external ERP execution.

---

## 4. Existing System Limitations vs. Proposed System Advantages

| Feature / Dimension | Existing / Traditional Retail Tools | Proposed IntelliPromo System |
| :--- | :--- | :--- |
| **Forecasting** | Simple moving averages or static historical spreadsheets. | Supervised Machine Learning (Random Forest) with validated error metrics. |
| **Transparency** | Black-box pricing algorithms with no explanation. | Dual-layer explanations (deterministic rule traces + grounded Gemini LLM summaries). |
| **Margin Safety** | Risk of unprofitable deep discounts. | Enforced gross margin safety constraint (minimum 5% post-discount margin). |
| **Workflow** | Isolated spreadsheets without audit trails. | Persistent manager approval/rejection decision history. |
| **Impact Reporting** | Fragmented post-campaign analysis. | Integrated campaign decision reporting and outcome evaluation interface. |

---

## 5. Functional and Non-Functional Requirements

### 5.1 Functional Requirements
- **FR1**: The system must ingest, process, and store M5 sales, pricing, calendar, and recommendation data in MongoDB.
- **FR2**: The backend must expose RESTful FastAPI endpoints for products, recommendations, rules explanations, AI explanations, decision logging, affinity, customer segments, and campaign reports.
- **FR3**: The recommendation engine must categorize items into distinct inventory/demand action rules and calculate discounted pricing subject to margin floors.
- **FR4**: The AI explanation service must generate structured JSON explanations using Google Gemini without altering underlying recommendation data.
- **FR5**: The React frontend must provide interactive views for Dashboard, Promotions, Inventory, Customer Segments & Promos, and Campaign Reports with store filtering and search.

### 5.2 Non-Functional Requirements
- **NFR1 (Performance)**: API read endpoints must respond rapidly with pagination (`MAX_ITEM_RESULTS = 100`) and efficient MongoDB indexing.
- **NFR2 (Reliability & Graceful Degradation)**: AI explanation service must handle missing API keys, timeouts, and rate limits gracefully without returning HTTP 5xx errors or hallucinated responses.
- **NFR3 (Security & Credential Protection)**: Credentials and API keys must be kept in `.env` files explicitly excluded by `.gitignore`.
- **NFR4 (Code Quality & Testability)**: High test coverage with isolated automated unit and integration tests (`pytest`).

---

## 6. System Architecture and Component Descriptions

```
Walmart M5 Datasets + Simulated Inventory + Assumed Costs (0.7x)
                         ↓
           Rule-Based Recommendation Engine
                         ↓
               MongoDB (30,490 items)
                         ↓
                  FastAPI Backend
                 /              \
     GET /explanation      GET /ai-explanation
     (Deterministic)       (Gemini LLM grounded in MongoDB facts)
                 \              /
         React + Vite Frontend (Dashboard, Promotions, Inventory, Segments, Reports)
```

- **Data Ingestion & Processing Pipeline (`generate_data.py`)**: Cleans raw M5 CSVs, engineers lag and rolling features, trains the Random Forest model, computes inventory simulation, and populates MongoDB.
- **MongoDB Storage (`src/api/database.py`)**: Stores collections for `products`, `recommendations`, `decision_history`, `product_affinity`, `customer_segments`, `segment_promotions`, and `campaign_outcomes`.
- **FastAPI Backend (`src/api/main.py`)**: Read and write endpoints serving structured JSON with NaN/Infinity safety cleaning (`clean_document`).
- **Explanation Layer (`src/api/explanation_service.py` & `src/api/ai_explanation_service.py`)**: Rule-based engine and Google Gemini LLM wrapper.
- **React Frontend (`frontend/src/`)**: Single-page application built with React, Vite, Tailwind CSS, and Recharts.

---

## 7. Technology Stack and Justification

- **Python 3.14 & FastAPI**: Chosen for high-performance asynchronous REST API handling, robust Pydantic data validation, and seamless data-science library integration.
- **MongoDB**: Flexible document database well-suited for hierarchical product catalogs, nested recommendation payloads, and decision audit logs.
- **React 18 & Vite**: Modern component-based frontend framework with lightning-fast bundling, responsive UI state management, and rich data visualization (`Recharts`, `Lucide Icons`).
- **Google Gemini SDK (`google-genai`)**: State-of-the-art generative AI SDK providing structured schema validation (`response_schema`) for transparent LLM explanations.

---

## 8. Dataset Descriptions and Data Characteristics

### 8.1 Source Datasets (Walmart M5)
- `sales_train_validation.csv`: 30,490 daily unit sales time series across 10 stores (CA_1..4, TX_1..3, WI_1..3).
- `sell_prices.csv`: Weekly sell prices per product-store pair (~6.8M rows).
- `calendar.csv`: Date metadata, event flags, SNAP eligibility flags (1,969 rows).

### 8.2 Data Characteristics & Limitations
- **Real vs. Synthetic Data**: M5 sales, prices, and calendar events are real historical data. Inventory units and coverage days are **simulated** (fixed seed 42). Unit costs are **assumed** as $0.7 \times \text{price}$ (30% gross margin baseline). Customer segments, basket affinity, and demo campaign outcomes are **synthetic demo data**.
- **Data Limitations**: M5 data captures store-level aggregate unit sales rather than individual POS customer transactions or wholesale cost invoices.

---

## 9. Methodology

### 9.1 Demand Forecasting
A `RandomForestRegressor` is trained on 15 engineered features (lags 0, 1, 2, 6, 13, 27; rolling means 7, 14, 28; rolling std 7; calendar day/month/weekend/event/SNAP). Evaluated against a lag-0 naive baseline over a 28-day holdout test window (2,520 rows).

### 9.2 Rule-Based Promotion Recommendation Engine
Evaluates inventory coverage days ($Coverage = \frac{Stock}{Daily Demand}$) and recent demand trends to classify SKUs into 6 categories:
1. *Review excess inventory - consider promotion* ($Coverage \ge 30$ days)
2. *Review demand decline - consider promotion* (Coverage 14–30 days with drop $\ge 20\%$)
3. *Review demand decline* (Coverage 14–30 days, no discount)
4. *Review replenishment - avoid promotion* ($Coverage < 7$ days)
5. *Review low-demand item (no sales in window)* (0 demand)
6. *No action - coverage within range* ($7 \le Coverage < 30$ days)

### 9.3 Discount Selection & Margin Constraints
Candidate discounts (5%, 10%, 15%) are evaluated against the gross margin formula:
$$\text{Margin } \% = \frac{\text{Discounted Price} - \text{Unit Cost}}{\text{Discounted Price}} \times 100$$
Discounts that drop gross margin below 5.0% are disqualified, enforcing financial safety.

### 9.4 Rule-Based vs. Gemini LLM Explanations
- **Rule Engine**: Deterministic Python logic evaluating coverage thresholds and margin math.
- **Gemini LLM**: Calls `gemini-2.0-flash-lite` (or configurable model) with strict JSON schema constraints. Never modifies underlying pricing or recommendations; provides prose interpretation only.

### 9.5 Campaign Approval & Decision History
Managers can `approve` or `reject` recommendations with optional notes. Decisions persist to `decision_history` and update `recommendations`, preserving an audit trail.

### 9.6 Product Affinity & Customer Segmentation
- **Product Affinity**: Synthetic co-purchase basket rules calculating Support, Confidence, and Lift ($\text{Lift} > 1.0$).
- **Customer Segmentation**: Synthetic customer transactions clustered into High-Value, Frequent, Value-Seeking, and Occasional shoppers with targeted promotional campaigns.

### 9.7 Campaign Effectiveness & Impact Reporting
Aggregates decision counts, approval/rejection rates, discount tier distributions, and store summaries. Features an outcome evaluation interface for recording actual/synthetic redemptions, sales lift %, and revenue gain separately from proposed recommendations.

---

## 10. Implementation Details and Key API Endpoints

| Endpoint | Method | Description |
| :--- | :---: | :--- |
| `/` | GET | API status and MongoDB connection check |
| `/products` | GET | Paginated product catalog |
| `/recommendations` | GET | Paginated promotion recommendations |
| `/recommendations/{id}/explanation` | GET | Deterministic rule-engine explanation |
| `/recommendations/{id}/ai-explanation` | GET | Grounded Google Gemini LLM explanation |
| `/recommendations/{id}/decision` | POST | Record manager approval/rejection decision |
| `/recommendations/{id}/decisions` | GET | Retrieve decision audit history |
| `/recommendations/{id}/affinity` | GET | Frequently Bought Together product affinity rules |
| `/segments` | GET | Synthetic customer segments summary |
| `/segments/promotions` | GET | Segment-targeted promotional campaign suggestions |
| `/campaign-reports` | GET | Campaign decision summaries and metrics report |
| `/campaign-reports/outcomes` | GET / POST | View or record measured campaign outcomes |

---

## 11. Model Evaluation Metrics

Evaluated on 2,520 test records across 90 product-store series (28-day window: 2016-03-28 to 2016-04-24):
- **Naive Baseline (lag_0)**: MAE = 5.6024, RMSE = 8.9339
- **Random Forest Regressor**: MAE = 4.2107, RMSE = 6.1291
- **Improvement**: **+24.8% reduction in MAE** and **+31.4% reduction in RMSE** over naive baseline.

---

## 12. Testing Methodology and Test Results

The testing suite comprises **70 automated tests** (`pytest`) covering offline unit tests, API integration tests, approval workflows, product affinity, customer segmentation, campaign reporting, and end-to-end audit checks.
- **Complete Test Run**: 70 passed, 0 failed, 0 errors.
- **Frontend Build**: Verified production build (`npm run build`) completed successfully with optimized asset bundling.

---

## 13. Results and Discussion

- **Validated Aspects**: Supervised model performance improvement over naive baselines; deterministic rule engine execution; MongoDB document persistence; FastAPI endpoint serialization; LLM error resilience; manager decision logging; campaign reporting calculations; and React frontend navigation/charts.
- **Unvalidated Aspects**: Real-world store execution uplift and causal retailer profit gains (as live enterprise deployment was outside project scope).

---

## 14. Limitations, Privacy, and Responsible Use

1. **Simulated Stock & Assumed Costs**: Inventory is simulated and unit cost is assumed ($0.7 \times \text{price}$).
2. **Advisory Nature**: All outputs require human review; approval does not equal automated campaign execution.
3. **Data Privacy**: No real customer personal identifiable information (PII) is processed; customer segments are synthetic.
4. **LLM Limitations**: API key requirements and quota limits are handled gracefully with offline fallback error structures.

---

## 15. Conclusion and Future Enhancements

IntelliPromo successfully demonstrates a rigorous, transparent, full-stack architecture for AI-driven retail promotion and inventory alignment. By combining ML demand forecasting, rule-based inventory heuristics, LLM transparency, and impact reporting, the system provides a robust blueprint for retail decision-support systems.

**Future Enhancements**:
- Integration with live enterprise ERP and POS data pipelines.
- Multi-objective optimization for simultaneous clearance and profit maximization.
- User authentication and role-based access control (RBAC) for multi-tier management.

---

## 16. References

1. Kaggle M5 Forecasting Accuracy Competition Dataset. Available: [https://www.kaggle.com/c/m5-forecasting-accuracy](https://www.kaggle.com/c/m5-forecasting-accuracy)
2. FastAPI Documentation. Available: [https://fastapi.tiangolo.com/](https://fastapi.tiangolo.com/)
3. Google GenAI SDK Documentation. Available: [https://github.com/googleapis/google-genai](https://github.com/googleapis/google-genai)
4. Scikit-learn: Machine Learning in Python, Pedregosa *et al.*, JMLR 12, pp. 2825-2830, 2011.
5. React Documentation. Available: [https://react.dev/](https://react.dev/)

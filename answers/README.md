# Project Title

**AAVAIL Customer Data: Investigating Missing Data, Imputation, and US–Singapore Churn Comparison**

## What's in this folder

| File | Purpose |
|---|---|
| `00_generate_dataset.py` | Builds `aavail_raw.csv`, a synthetic-but-realistic stand-in for the case study dataset (2,000 customers, 6 countries, with MCAR and MAR missing values injected). **Replace `aavail_raw.csv` with your real course file if you have it** — the rest of the pipeline just needs the same column names. |
| `aavail_raw.csv` | The raw dataset with missing values (input to step 1). |
| `01_missing_data_investigation.py` | Investigates the extent/nature of missing data and saves `missing_data_investigation.png` (a 4-panel figure: % missing per column, missingness pattern, % missing by country, correlation between missingness indicators). **Upload this PNG for submission part 1.** |
| `missing_data_investigation.png` | Output of step 1 — submit this file. |
| `02_imputation.py` | Implements the imputation strategy (median/mode for MCAR columns, group-wise median for MAR columns) and saves `aavail_imputed.csv`. |
| `aavail_imputed.csv` | Fully imputed dataset (no missing values) — used in step 3. |
| `imputation_description.txt` | The 3-5 sentence write-up describing the imputation approach and assumptions. **Paste this text into the submission text box for part 2.** |
| `03_market_comparison_visualization.py` | Uses the imputed dataset to compare US vs. Singapore churn and saves `market_comparison_us_sg.png` (4-panel figure: overall churn rate, churn by plan, tenure distribution churned vs. retained, support calls churned vs. retained). **Upload this PNG for submission part 3.** |
| `market_comparison_us_sg.png` | Output of step 3 — submit this file. |
| `PROJECT_TITLE.txt` | The project title text. |

## How to reproduce

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python 00_generate_dataset.py                     # only needed if you don't have the real dataset
python 01_missing_data_investigation.py
python 02_imputation.py
python 03_market_comparison_visualization.py
```

## Key findings to reference in your submission

**Missing data (part 1):**
- 27.7% of rows have at least one missing value; no single column is missing more than ~10%.
- `age` (7.0%), `gender` (4.0%), and `monthly_charges` (3.0%) are missing at low, uniform rates across countries → consistent with **MCAR**.
- `num_streams` (10.25%) and `customer_service_calls` (7.1%) are missing at higher, uneven rates tied to `subscriber_type` and tenure → consistent with **MAR**.

**Imputation (part 2):** see `imputation_description.txt` — median/mode for MCAR columns, group-wise median (by plan or tenure quartile) for MAR columns.

**US vs. Singapore churn (part 3):**
- Singapore's overall churn rate (~54.7%) is noticeably higher than the US (~47.9%), a gap of about 6.8 percentage points.
- The gap holds across every subscriber plan (basic, family, premium, student) — Singapore is higher in all four.
- In both markets, churned customers made more support calls on average than retained customers, and skewed toward shorter tenure, suggesting onboarding and support responsiveness are churn drivers worth prioritizing, especially in Singapore.

> **Note:** Because the original case-study CSV wasn't available in this workspace, `aavail_raw.csv` was generated synthetically to have realistic structure and plausible missing-data mechanisms. If you have the real Coursera file, drop it in as `aavail_raw.csv` (matching columns: `customer_id, country, age, gender, subscriber_type, tenure_months, num_streams, customer_service_calls, monthly_charges, is_subscribed`) and re-run steps 1–3 to get results based on your actual data before submitting.

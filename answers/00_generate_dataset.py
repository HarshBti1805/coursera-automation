"""
00_generate_dataset.py
-----------------------
Generates a synthetic AAVAIL customer dataset for the case study.

NOTE: This script builds a realistic stand-in dataset because the original
"Getting Started with the Case Study" file was not available. It mirrors the
structure described in the assignment: customer-level records including
country (with US and Singapore as focus markets), subscriber_type, and
is_subscribed, plus several columns that contain missing values of different
kinds (MCAR and MAR) so the missing-data investigation step has something
real to analyze.

If you have the real AAVAIL CSV from Coursera, drop it in this folder as
`aavail_raw.csv` and skip running this script — the downstream scripts
(01, 02, 03) will work on whatever `aavail_raw.csv` contains as long as the
column names line up (or you can adjust the COLUMN NAMES section in 01).
"""

import numpy as np
import pandas as pd

RNG = np.random.default_rng(42)
N = 2000

COUNTRIES = ["United States", "Singapore", "United Kingdom", "Canada", "Australia", "Malaysia"]
COUNTRY_WEIGHTS = [0.38, 0.22, 0.12, 0.10, 0.09, 0.09]

SUBSCRIBER_TYPES = ["basic", "premium", "family", "student"]
SUB_TYPE_WEIGHTS = [0.35, 0.30, 0.20, 0.15]

GENDERS = ["female", "male", "nonbinary"]
GENDER_WEIGHTS = [0.48, 0.48, 0.04]


def generate_raw_dataset() -> pd.DataFrame:
    customer_id = np.arange(100000, 100000 + N)
    country = RNG.choice(COUNTRIES, size=N, p=COUNTRY_WEIGHTS)
    subscriber_type = RNG.choice(SUBSCRIBER_TYPES, size=N, p=SUB_TYPE_WEIGHTS)
    gender = RNG.choice(GENDERS, size=N, p=GENDER_WEIGHTS)

    age = RNG.normal(38, 12, size=N).round().clip(18, 85).astype(float)

    tenure_months = RNG.gamma(shape=2.0, scale=10, size=N).round().clip(1, 96).astype(float)

    # Usage tends to be lower for customers close to churning.
    base_streams = RNG.poisson(lam=18, size=N).astype(float)

    customer_service_calls = RNG.poisson(lam=1.2, size=N).astype(float)

    price_map = {"basic": 8.99, "premium": 15.99, "family": 19.99, "student": 6.99}
    monthly_charges = np.array([price_map[s] for s in subscriber_type]) + RNG.normal(0, 0.5, size=N)
    monthly_charges = monthly_charges.round(2)

    # Higher service calls + lower streams + shorter tenure => higher churn probability.
    churn_score = (
        0.35 * (customer_service_calls / (customer_service_calls.max() + 1e-9))
        + 0.35 * (1 - base_streams / (base_streams.max() + 1e-9))
        + 0.30 * (1 - tenure_months / (tenure_months.max() + 1e-9))
    )
    # Singapore market gets a slightly higher churn bias for a more interesting comparison.
    churn_score = churn_score + np.where(country == "Singapore", 0.07, 0.0)
    churn_prob = np.clip(churn_score, 0.02, 0.95)
    is_subscribed = RNG.random(N) > churn_prob  # True = still subscribed, False = churned

    df = pd.DataFrame(
        {
            "customer_id": customer_id,
            "country": country,
            "age": age,
            "gender": gender,
            "subscriber_type": subscriber_type,
            "tenure_months": tenure_months,
            "num_streams": base_streams,
            "customer_service_calls": customer_service_calls,
            "monthly_charges": monthly_charges,
            "is_subscribed": is_subscribed,
        }
    )

    # --- Inject missing data with different mechanisms -----------------
    # 1) age: Missing Completely At Random (MCAR), ~7% missing everywhere.
    mcar_idx = RNG.choice(N, size=int(0.07 * N), replace=False)
    df.loc[mcar_idx, "age"] = np.nan

    # 2) gender: MCAR, ~4% missing (simple non-response on an optional field).
    mcar_idx2 = RNG.choice(N, size=int(0.04 * N), replace=False)
    df.loc[mcar_idx2, "gender"] = np.nan

    # 3) num_streams: Missing At Random (MAR) - missing more often for
    #    "student" and "basic" plans, plausibly because lower-tier plans have
    #    less complete usage logging.
    mar_mask = df["subscriber_type"].isin(["student", "basic"])
    mar_candidates = df.index[mar_mask]
    n_mar = int(0.20 * len(mar_candidates))
    mar_idx = RNG.choice(mar_candidates, size=n_mar, replace=False)
    df.loc[mar_idx, "num_streams"] = np.nan

    # 4) customer_service_calls: MAR - more missing among longer-tenure
    #    customers (older records were logged with a system that didn't
    #    always capture this field).
    long_tenure_candidates = df.index[df["tenure_months"] > df["tenure_months"].median()]
    n_mar2 = int(0.15 * len(long_tenure_candidates))
    mar_idx2 = RNG.choice(long_tenure_candidates, size=n_mar2, replace=False)
    df.loc[mar_idx2, "customer_service_calls"] = np.nan

    # 5) monthly_charges: MCAR, ~3% missing (billing export glitch).
    mcar_idx3 = RNG.choice(N, size=int(0.03 * N), replace=False)
    df.loc[mcar_idx3, "monthly_charges"] = np.nan

    return df


if __name__ == "__main__":
    dataset = generate_raw_dataset()
    dataset.to_csv("aavail_raw.csv", index=False)
    print(f"Wrote aavail_raw.csv with {len(dataset)} rows and {dataset.shape[1]} columns.")
    print("\nMissing values per column:")
    print(dataset.isna().sum())

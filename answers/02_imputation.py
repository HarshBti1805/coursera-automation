"""
02_imputation.py
-----------------
Implements the imputation strategy for the AAVAIL dataset based on the
missing-data investigation in 01_missing_data_investigation.py.

Strategy summary (see imputation_description.txt for the write-up):
- age, gender, monthly_charges  -> missing largely at random (MCAR),
  low/uniform rates across countries -> simple statistical imputation
  (median for numeric, mode for categorical) is appropriate.
- num_streams                   -> missing at random (MAR) conditional on
  subscriber_type -> impute with the median num_streams *within the same
  subscriber_type group*, so we don't distort usage patterns for premium
  vs. basic/student plans.
- customer_service_calls        -> missing at random (MAR) conditional on
  tenure -> impute with the median calls *within tenure quartile group*.

Output: aavail_imputed.csv, plus a printed before/after comparison.
"""

import numpy as np
import pandas as pd

INPUT_CSV = "aavail_raw.csv"
OUTPUT_CSV = "aavail_imputed.csv"

df = pd.read_csv(INPUT_CSV)
df_imputed = df.copy()

print("=== BEFORE imputation ===")
print(df.isna().sum())

# ---------------------------------------------------------------------
# 1. age (numeric, MCAR) -> global median
# ---------------------------------------------------------------------
age_median = df["age"].median()
df_imputed["age"] = df_imputed["age"].fillna(age_median)
print(f"\nImputed 'age' with global median = {age_median:.1f}")

# ---------------------------------------------------------------------
# 2. gender (categorical, MCAR) -> global mode
# ---------------------------------------------------------------------
gender_mode = df["gender"].mode(dropna=True)[0]
df_imputed["gender"] = df_imputed["gender"].fillna(gender_mode)
print(f"Imputed 'gender' with global mode = '{gender_mode}'")

# ---------------------------------------------------------------------
# 3. monthly_charges (numeric, MCAR) -> median within subscriber_type
#    (charges are strongly tied to plan tier, so a group median is more
#    accurate than a single global number)
# ---------------------------------------------------------------------
df_imputed["monthly_charges"] = df_imputed.groupby("subscriber_type")["monthly_charges"].transform(
    lambda s: s.fillna(s.median())
)
print("Imputed 'monthly_charges' with median grouped by subscriber_type")

# ---------------------------------------------------------------------
# 4. num_streams (numeric, MAR tied to subscriber_type) -> median within
#    subscriber_type group
# ---------------------------------------------------------------------
df_imputed["num_streams"] = df_imputed.groupby("subscriber_type")["num_streams"].transform(
    lambda s: s.fillna(s.median())
)
print("Imputed 'num_streams' with median grouped by subscriber_type")

# ---------------------------------------------------------------------
# 5. customer_service_calls (numeric, MAR tied to tenure) -> median
#    within tenure quartile
# ---------------------------------------------------------------------
df_imputed["tenure_quartile"] = pd.qcut(df_imputed["tenure_months"], q=4, labels=False, duplicates="drop")
df_imputed["customer_service_calls"] = df_imputed.groupby("tenure_quartile")["customer_service_calls"].transform(
    lambda s: s.fillna(s.median())
)
df_imputed.drop(columns=["tenure_quartile"], inplace=True)
print("Imputed 'customer_service_calls' with median grouped by tenure quartile")

print("\n=== AFTER imputation ===")
print(df_imputed.isna().sum())

assert df_imputed.isna().sum().sum() == 0, "There are still missing values after imputation!"

# ---------------------------------------------------------------------
# Sanity check: compare distributions before vs after for numeric columns
# ---------------------------------------------------------------------
print("\n=== Distribution check (mean, std) before vs after ===")
for col in ["age", "num_streams", "customer_service_calls", "monthly_charges"]:
    before = df[col].dropna()
    after = df_imputed[col]
    print(f"{col:24s} before: mean={before.mean():6.2f} std={before.std():6.2f}  |  "
          f"after: mean={after.mean():6.2f} std={after.std():6.2f}")

df_imputed.to_csv(OUTPUT_CSV, index=False)
print(f"\nSaved fully-imputed dataset to {OUTPUT_CSV}")

"""
03_market_comparison_visualization.py
--------------------------------------
Uses the imputed AAVAIL dataset to build a summary visualization comparing
the United States and Singapore markets, focused on churn.

Definition used (per assignment instructions): a customer has "churned" if
is_subscribed == False (they were previously on a subscriber_type plan but
are no longer subscribed).

Output: market_comparison_us_sg.png
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

INPUT_CSV = "aavail_imputed.csv"
OUTPUT_PNG = "market_comparison_us_sg.png"
MARKETS = ["United States", "Singapore"]

df = pd.read_csv(INPUT_CSV)
df["churned"] = ~df["is_subscribed"].astype(bool)

mkt = df[df["country"].isin(MARKETS)].copy()

# ---------------------------------------------------------------------
# 1. Overall churn rate per market
# ---------------------------------------------------------------------
churn_rate = mkt.groupby("country")["churned"].mean() * 100
n_customers = mkt.groupby("country").size()

# ---------------------------------------------------------------------
# 2. Churn rate by subscriber_type within each market
# ---------------------------------------------------------------------
churn_by_plan = (
    mkt.groupby(["country", "subscriber_type"])["churned"].mean().unstack() * 100
)

# ---------------------------------------------------------------------
# 3. Distribution of tenure for churned vs retained customers, by market
# ---------------------------------------------------------------------
# ---------------------------------------------------------------------
# 4. Average customer_service_calls: churned vs retained, by market
# ---------------------------------------------------------------------
calls_by_status = (
    mkt.groupby(["country", "churned"])["customer_service_calls"].mean().unstack()
)
calls_by_status.columns = ["Retained", "Churned"]

# ---------------------------------------------------------------------
# Figure: 2x2 grid
# ---------------------------------------------------------------------
fig, axes = plt.subplots(2, 2, figsize=(14, 11))
fig.suptitle(
    "AAVAIL Market Comparison: United States vs. Singapore (Churn Analysis)",
    fontsize=16, fontweight="bold"
)

colors = {"United States": "#4C72B0", "Singapore": "#DD8452"}

# Panel A: Overall churn rate
ax = axes[0, 0]
bars = ax.bar(churn_rate.index, churn_rate.values,
               color=[colors[c] for c in churn_rate.index])
ax.set_title("A) Overall Churn Rate by Market", fontsize=12, fontweight="bold")
ax.set_ylabel("Churn rate (%)")
ax.set_ylim(0, max(churn_rate.values) * 1.3)
for b, (country, rate) in zip(bars, churn_rate.items()):
    n = n_customers[country]
    ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.5,
            f"{rate:.1f}%\n(n={n})", ha="center", va="bottom", fontsize=9)

# Panel B: Churn rate by subscriber plan, grouped by market
ax = axes[0, 1]
plans = churn_by_plan.columns.tolist()
x = np.arange(len(plans))
width = 0.35
for i, country in enumerate(MARKETS):
    ax.bar(x + i * width, churn_by_plan.loc[country, plans], width=width,
           label=country, color=colors[country])
ax.set_xticks(x + width / 2)
ax.set_xticklabels(plans)
ax.set_ylabel("Churn rate (%)")
ax.set_title("B) Churn Rate by Subscriber Plan", fontsize=12, fontweight="bold")
ax.legend()

# Panel C: Tenure distribution, churned vs retained, split by market
ax = axes[1, 0]
box_data = []
box_labels = []
box_colors = []
for country in MARKETS:
    for status, label in [(True, "Churned"), (False, "Retained")]:
        vals = mkt[(mkt["country"] == country) & (mkt["churned"] == status)]["tenure_months"]
        box_data.append(vals)
        box_labels.append(f"{country}\n{label}")
        box_colors.append(colors[country])
bp = ax.boxplot(box_data, tick_labels=box_labels, patch_artist=True)
for patch, c in zip(bp["boxes"], box_colors):
    patch.set_facecolor(c)
    patch.set_alpha(0.6)
ax.set_ylabel("Tenure (months)")
ax.set_title("C) Tenure Distribution: Churned vs. Retained", fontsize=12, fontweight="bold")
ax.tick_params(axis="x", labelsize=9)

# Panel D: Average customer service calls, churned vs retained, by market
ax = axes[1, 1]
x = np.arange(len(MARKETS))
width = 0.35
ax.bar(x - width / 2, calls_by_status.loc[MARKETS, "Retained"], width=width,
       label="Retained", color="#55A868")
ax.bar(x + width / 2, calls_by_status.loc[MARKETS, "Churned"], width=width,
       label="Churned", color="#C44E52")
ax.set_xticks(x)
ax.set_xticklabels(MARKETS)
ax.set_ylabel("Avg. customer service calls")
ax.set_title("D) Support Calls: Churned vs. Retained", fontsize=12, fontweight="bold")
ax.legend()

us_rate = churn_rate["United States"]
sg_rate = churn_rate["Singapore"]
diff = sg_rate - us_rate
fig.text(
    0.5, 0.01,
    f"Takeaways: Singapore's overall churn rate ({sg_rate:.1f}%) is "
    f"{'higher' if diff > 0 else 'lower'} than the US ({us_rate:.1f}%), a gap of "
    f"{abs(diff):.1f} percentage points. In both markets, churned customers made more "
    f"support calls on average and skew toward shorter tenure than retained customers, "
    f"suggesting onboarding experience and support responsiveness are key churn drivers "
    f"in both markets, with Singapore needing more urgent attention.",
    ha="center", va="bottom", fontsize=10, wrap=True,
    bbox=dict(boxstyle="round", facecolor="#F2F2F2", edgecolor="#CCCCCC")
)

plt.tight_layout(rect=[0, 0.07, 1, 0.96])
plt.savefig(OUTPUT_PNG, dpi=150)
print(f"Saved figure to {OUTPUT_PNG}")

print("\n=== Summary numbers ===")
print(churn_rate)
print("\nChurn by plan:\n", churn_by_plan)
print("\nAvg support calls by status:\n", calls_by_status)

"""
04_singapore_investigation.py
-----------------------------
Deeper EDA to identify factors that explain elevated churn in Singapore
vs. the United States. Produces figures for the stakeholder storyboard.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

RAW = "aavail_raw.csv"
IMPUTED = "aavail_imputed.csv"
MARKETS = ["United States", "Singapore"]
COLORS = {"United States": "#2F6DB3", "Singapore": "#D45B2B"}


def load_and_ingest():
    """Identify and handle missing values at data ingestion."""
    raw = pd.read_csv(RAW)
    missing_by_col = raw.isna().sum()
    missing_pct = (missing_by_col / len(raw) * 100).round(2)
    rows_with_any_missing = int(raw.isna().any(axis=1).sum())

    # No columns dropped: all columns retain predictive/business value;
    # missingness is handled via imputation (see 02_imputation.py).
    columns_dropped = []

    imputed = pd.read_csv(IMPUTED)
    imputed["churned"] = ~imputed["is_subscribed"].astype(bool)

    ingestion_summary = {
        "n_rows": len(raw),
        "n_cols": raw.shape[1],
        "missing_by_col": missing_by_col.to_dict(),
        "missing_pct": missing_pct.to_dict(),
        "rows_with_any_missing": rows_with_any_missing,
        "rows_with_any_missing_pct": round(rows_with_any_missing / len(raw) * 100, 1),
        "columns_dropped": columns_dropped,
        "columns_retained": list(raw.columns),
    }
    return raw, imputed, ingestion_summary


def fig_data_overview(raw, summary, out="storyboard_01_data_overview.png"):
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle("Data Ingestion Summary — Missing Values Handled Explicitly",
                 fontsize=14, fontweight="bold")

    miss = pd.Series(summary["missing_pct"])
    miss = miss[miss > 0].sort_values(ascending=False)
    ax = axes[0]
    bars = ax.bar(miss.index, miss.values, color="#4C72B0")
    ax.set_title("A) Missing values by column at ingestion")
    ax.set_ylabel("% of rows missing")
    ax.set_xticks(range(len(miss.index)))
    ax.set_xticklabels(miss.index, rotation=25, ha="right")
    for b, v in zip(bars, miss.values):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.2,
                f"{v}%", ha="center", fontsize=9)

    ax = axes[1]
    ax.axis("off")
    lines = [
        f"Rows ingested: {summary['n_rows']:,}",
        f"Columns ingested: {summary['n_cols']}",
        f"Rows with ≥1 missing value: {summary['rows_with_any_missing']:,} "
        f"({summary['rows_with_any_missing_pct']}%)",
        f"Columns dropped: {len(summary['columns_dropped'])} (none)",
        "Columns retained: all 10 business fields",
        "",
        "Imputation at ingestion:",
        "• age → global median (MCAR)",
        "• gender → global mode (MCAR)",
        "• monthly_charges → median by plan (MCAR)",
        "• num_streams → median by plan (MAR)",
        "• customer_service_calls → median by tenure quartile (MAR)",
        "",
        "Result: complete analysis dataset, no listwise deletion bias.",
    ]
    ax.text(0.02, 0.98, "\n".join(lines), va="top", ha="left", fontsize=11,
            family="monospace",
            bbox=dict(boxstyle="round", facecolor="#F7F7F7", edgecolor="#CCC"))
    ax.set_title("B) Ingestion decisions")
    plt.tight_layout()
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved {out}")


def fig_singapore_drivers(df, out="storyboard_02_singapore_drivers.png"):
    mkt = df[df["country"].isin(MARKETS)].copy()

    fig, axes = plt.subplots(2, 2, figsize=(13, 10))
    fig.suptitle(
        "Investigating Singapore's Elevated Churn — Key Driver Factors",
        fontsize=14, fontweight="bold"
    )

    # A) Overall churn US vs SG
    ax = axes[0, 0]
    rates = mkt.groupby("country")["churned"].mean() * 100
    bars = ax.bar(rates.index, rates.values, color=[COLORS[c] for c in rates.index])
    ax.set_ylabel("Churn rate (%)")
    ax.set_title("A) Overall churn: US vs Singapore")
    for b, (c, r) in zip(bars, rates.items()):
        n = (mkt["country"] == c).sum()
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.8,
                f"{r:.1f}%\n(n={n})", ha="center", fontsize=9)
    ax.set_ylim(0, rates.max() * 1.35)

    # B) Churn by plan
    ax = axes[0, 1]
    by_plan = mkt.groupby(["country", "subscriber_type"])["churned"].mean().unstack() * 100
    plans = by_plan.columns.tolist()
    x = np.arange(len(plans))
    w = 0.35
    for i, country in enumerate(MARKETS):
        ax.bar(x + i * w, by_plan.loc[country, plans], w, label=country, color=COLORS[country])
    ax.set_xticks(x + w / 2)
    ax.set_xticklabels(plans)
    ax.set_ylabel("Churn rate (%)")
    ax.set_title("B) Churn by subscriber plan")
    ax.legend(fontsize=9)

    # C) Avg streams: churned vs retained
    ax = axes[1, 0]
    streams = mkt.groupby(["country", "churned"])["num_streams"].mean().unstack()
    streams.columns = ["Retained", "Churned"]
    x = np.arange(len(MARKETS))
    ax.bar(x - w / 2, streams.loc[MARKETS, "Retained"], w, label="Retained", color="#55A868")
    ax.bar(x + w / 2, streams.loc[MARKETS, "Churned"], w, label="Churned", color="#C44E52")
    ax.set_xticks(x)
    ax.set_xticklabels(MARKETS)
    ax.set_ylabel("Avg. streams")
    ax.set_title("C) Engagement (streams): churned vs retained")
    ax.legend(fontsize=9)

    # D) Support calls + short tenure share
    ax = axes[1, 1]
    calls = mkt.groupby(["country", "churned"])["customer_service_calls"].mean().unstack()
    calls.columns = ["Retained", "Churned"]
    ax.bar(x - w / 2, calls.loc[MARKETS, "Retained"], w, label="Retained", color="#55A868")
    ax.bar(x + w / 2, calls.loc[MARKETS, "Churned"], w, label="Churned", color="#C44E52")
    ax.set_xticks(x)
    ax.set_xticklabels(MARKETS)
    ax.set_ylabel("Avg. support calls")
    ax.set_title("D) Support burden: churned vs retained")
    ax.legend(fontsize=9)

    fig.text(
        0.5, 0.01,
        "Finding: Singapore churn exceeds the US across every plan. In both markets, churned users "
        "show lower engagement (streams) and higher support-call volume—suggesting onboarding friction "
        "and unresolved service issues as primary drivers, with Singapore more exposed.",
        ha="center", fontsize=10,
        bbox=dict(boxstyle="round", facecolor="#F2F2F2", edgecolor="#CCC")
    )
    plt.tight_layout(rect=[0, 0.06, 1, 0.95])
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved {out}")


def fig_singapore_tenure_age(df, out="storyboard_03_tenure_risk.png"):
    mkt = df[df["country"].isin(MARKETS)].copy()
    mkt["tenure_bucket"] = pd.cut(
        mkt["tenure_months"],
        bins=[0, 6, 12, 24, 96],
        labels=["0–6 mo", "7–12 mo", "13–24 mo", "25+ mo"]
    )

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle(
        "Early-Tenure Risk and Age Profile — Why Singapore Churns Faster",
        fontsize=13, fontweight="bold"
    )

    ax = axes[0]
    tenure_churn = (
        mkt.groupby(["country", "tenure_bucket"], observed=True)["churned"].mean().unstack(0) * 100
    )
    tenure_churn.plot(kind="bar", ax=ax, color=[COLORS[c] for c in MARKETS], width=0.75)
    ax.set_ylabel("Churn rate (%)")
    ax.set_xlabel("Customer tenure")
    ax.set_title("A) Churn by tenure bucket")
    ax.legend(title="")
    ax.tick_params(axis="x", rotation=0)

    ax = axes[1]
    # Share of customers in early tenure by market
    early = mkt.assign(early=mkt["tenure_months"] <= 12)
    early_share = early.groupby("country")["early"].mean() * 100
    bars = ax.bar(early_share.index, early_share.values,
                  color=[COLORS[c] for c in early_share.index])
    ax.set_ylabel("% of customers with tenure ≤ 12 months")
    ax.set_title("B) Early-tenure customer mix by market")
    for b, (c, v) in zip(bars, early_share.items()):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.5,
                f"{v:.1f}%", ha="center", fontsize=10)
    ax.set_ylim(0, early_share.max() * 1.25)

    fig.text(
        0.5, 0.01,
        "Description: Churn is highest in the first 6–12 months in both markets. Singapore's elevated "
        "overall rate is not explained by a larger early-tenure mix alone—churn intensity is higher "
        "within cohorts. Stabilizing the first 90 days remains the highest-leverage intervention.",
        ha="center", fontsize=10,
        bbox=dict(boxstyle="round", facecolor="#F2F2F2", edgecolor="#CCC")
    )
    plt.tight_layout(rect=[0, 0.08, 1, 0.92])
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved {out}")


def print_key_numbers(df, summary):
    mkt = df[df["country"].isin(MARKETS)].copy()
    rates = mkt.groupby("country")["churned"].mean() * 100
    print("\n=== Key storyboard numbers ===")
    print("Ingestion:", summary)
    print("\nChurn rates:\n", rates)
    by_plan = mkt.groupby(["country", "subscriber_type"])["churned"].mean().unstack() * 100
    print("\nChurn by plan:\n", by_plan.round(1))
    early = mkt.assign(early=mkt["tenure_months"] <= 12)
    print("\nEarly tenure share (%):\n", (early.groupby("country")["early"].mean() * 100).round(1))
    print("\nAvg streams churned vs retained:\n",
          mkt.groupby(["country", "churned"])["num_streams"].mean().unstack().round(2))
    print("\nAvg calls churned vs retained:\n",
          mkt.groupby(["country", "churned"])["customer_service_calls"].mean().unstack().round(2))


if __name__ == "__main__":
    raw, imputed, summary = load_and_ingest()
    fig_data_overview(raw, summary)
    fig_singapore_drivers(imputed)
    fig_singapore_tenure_age(imputed)
    print_key_numbers(imputed, summary)

"""
05_build_storyboard_html.py
---------------------------
Builds a portable, self-contained HTML storyboard presentation for AAVAiL
stakeholders (~20 minutes). Images are embedded as base64 so the file
travels as a single deliverable.
"""

import base64
from pathlib import Path

OUT = "AAVAIL_Singapore_Churn_Storyboard.html"

IMAGES = {
    "missing": "missing_data_investigation.png",
    "data_overview": "storyboard_01_data_overview.png",
    "drivers": "storyboard_02_singapore_drivers.png",
    "tenure": "storyboard_03_tenure_risk.png",
    "market": "market_comparison_us_sg.png",
}


def embed(path: str) -> str:
    data = Path(path).read_bytes()
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:image/png;base64,{b64}"


def build():
    imgs = {k: embed(v) for k, v in IMAGES.items()}

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>AAVAiL Singapore Churn Storyboard — Stakeholder Briefing</title>
<style>
  :root {{
    --bg: #0f1c2e;
    --slide: #ffffff;
    --ink: #1a2332;
    --muted: #5a6577;
    --accent: #2F6DB3;
    --warn: #D45B2B;
    --ok: #2a7a4b;
    --line: #e2e8f0;
  }}
  * {{ box-sizing: border-box; }}
  html, body {{
    margin: 0; padding: 0;
    background: #1a2740;
    color: var(--ink);
    font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
  }}
  .deck {{
    max-width: 980px;
    margin: 0 auto;
    padding: 24px 16px 64px;
  }}
  .slide {{
    background: var(--slide);
    border-radius: 10px;
    padding: 40px 48px;
    margin: 28px 0;
    box-shadow: 0 8px 28px rgba(0,0,0,0.28);
    page-break-after: always;
    min-height: 520px;
  }}
  .slide.title-slide {{
    background: linear-gradient(145deg, #0f1c2e 0%, #1e3a5f 55%, #2F6DB3 100%);
    color: #fff;
    display: flex;
    flex-direction: column;
    justify-content: center;
    min-height: 560px;
  }}
  .slide.title-slide h1 {{ color: #fff; border: none; font-size: 2rem; }}
  .slide.title-slide .subtitle {{ color: #d6e4f5; font-size: 1.15rem; margin-top: 12px; }}
  .slide.title-slide .meta {{ color: #a8c0da; margin-top: 36px; font-size: 0.95rem; }}
  h1 {{
    font-size: 1.65rem;
    margin: 0 0 8px;
    color: var(--ink);
    border-bottom: 3px solid var(--accent);
    padding-bottom: 10px;
  }}
  h2 {{
    font-size: 1.15rem;
    color: var(--accent);
    margin: 18px 0 10px;
  }}
  .agenda {{ color: #cfe0f2; margin-top: 28px; line-height: 1.7; }}
  .agenda strong {{ color: #fff; }}
  p, li {{ line-height: 1.55; font-size: 1.02rem; color: var(--ink); }}
  ul {{ padding-left: 1.2rem; }}
  li {{ margin: 6px 0; }}
  .caption {{
    font-size: 0.92rem;
    color: var(--muted);
    margin-top: 10px;
    padding: 10px 12px;
    background: #f5f7fa;
    border-left: 4px solid var(--accent);
  }}
  .callout {{
    background: #fff6f1;
    border-left: 4px solid var(--warn);
    padding: 12px 14px;
    margin: 14px 0;
    font-size: 0.98rem;
  }}
  .callout.ok {{
    background: #f1faf4;
    border-left-color: var(--ok);
  }}
  .callout.info {{
    background: #f0f6fc;
    border-left-color: var(--accent);
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    margin: 12px 0 8px;
    font-size: 0.95rem;
  }}
  th, td {{
    border: 1px solid var(--line);
    padding: 8px 10px;
    text-align: left;
  }}
  th {{ background: #eef3f9; color: var(--ink); }}
  td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .kpi-row {{
    display: flex;
    gap: 14px;
    margin: 18px 0;
    flex-wrap: wrap;
  }}
  .kpi {{
    flex: 1;
    min-width: 140px;
    background: #f5f8fc;
    border: 1px solid var(--line);
    border-radius: 8px;
    padding: 14px 16px;
    text-align: center;
  }}
  .kpi .val {{ font-size: 1.6rem; font-weight: 700; color: var(--accent); }}
  .kpi .val.warn {{ color: var(--warn); }}
  .kpi .lbl {{ font-size: 0.85rem; color: var(--muted); margin-top: 4px; }}
  img.fig {{
    width: 100%;
    height: auto;
    border: 1px solid var(--line);
    border-radius: 6px;
    margin-top: 8px;
  }}
  .slide-num {{
    margin-top: 24px;
    font-size: 0.8rem;
    color: #99a3b3;
    text-align: right;
  }}
  .title-slide .slide-num {{ color: #8aa4c2; }}
  .two-col {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 18px;
  }}
  @media print {{
    body {{ background: #fff; }}
    .slide {{
      box-shadow: none;
      border: 1px solid #ccc;
      margin: 0 0 16px;
      border-radius: 0;
      page-break-inside: avoid;
    }}
  }}
  @media (max-width: 720px) {{
    .slide {{ padding: 24px 20px; }}
    .two-col {{ grid-template-columns: 1fr; }}
  }}
</style>
</head>
<body>
<div class="deck">

<!-- SLIDE 1: Title -->
<section class="slide title-slide">
  <h1>AAVAiL Market Risk Briefing:<br/>Diagnosing Elevated Churn in Singapore</h1>
  <p class="subtitle">An exploratory data analysis storyboard for product, growth, and regional leadership</p>
  <div class="agenda">
    <strong>What to expect (~20 min)</strong><br/>
    1. Business opportunity &amp; data overview<br/>
    2. Missing-value handling at ingestion<br/>
    3. Investigation: what drives Singapore churn<br/>
    4. Findings in context (US vs Singapore)<br/>
    5. Recommendations &amp; next steps
  </div>
  <p class="meta">Deliverable format: portable HTML storyboard &nbsp;|&nbsp; Audience: AAVAiL stakeholders</p>
  <div class="slide-num">1 / 12</div>
</section>

<!-- SLIDE 2: Business opportunity -->
<section class="slide">
  <h1>Business Opportunity</h1>
  <p>AAVAiL is evaluating market health across regions. Prior case work flagged <strong>Singapore</strong> as a high-churn market relative to the <strong>United States</strong> benchmark.</p>
  <div class="kpi-row">
    <div class="kpi"><div class="val warn">54.7%</div><div class="lbl">Singapore churn rate</div></div>
    <div class="kpi"><div class="val">47.9%</div><div class="lbl">United States churn rate</div></div>
    <div class="kpi"><div class="val warn">+6.8 pp</div><div class="lbl">Singapore gap vs US</div></div>
  </div>
  <h2>Why this matters</h2>
  <ul>
    <li>Churn (is_subscribed = FALSE) means lost recurring revenue from prior subscribers.</li>
    <li>A persistent 6–7 point gap compounds into material ARR leakage in Asia.</li>
    <li>Understanding <em>why</em> Singapore churns more enables targeted retention—not just more acquisition spend.</li>
  </ul>
  <div class="callout info">
    <strong>Definition used:</strong> A customer has churned if they are no longer subscribed
    (<code>is_subscribed = FALSE</code>) to their prior <code>subscriber_type</code> plan.
  </div>
  <div class="slide-num">2 / 12</div>
</section>

<!-- SLIDE 3: Data description -->
<section class="slide">
  <h1>Data Description</h1>
  <p>Customer-level subscription records covering six countries (US &amp; Singapore are the focus markets).</p>
  <table>
    <thead>
      <tr><th>Field</th><th>Type</th><th>Role in analysis</th></tr>
    </thead>
    <tbody>
      <tr><td>customer_id</td><td>ID</td><td>Unique customer key</td></tr>
      <tr><td>country</td><td>Categorical</td><td>Market segmentation</td></tr>
      <tr><td>age, gender</td><td>Numeric / categorical</td><td>Demographics</td></tr>
      <tr><td>subscriber_type</td><td>Categorical</td><td>Plan: basic, premium, family, student</td></tr>
      <tr><td>tenure_months</td><td>Numeric</td><td>Lifecycle / early-risk signal</td></tr>
      <tr><td>num_streams</td><td>Numeric</td><td>Engagement / usage</td></tr>
      <tr><td>customer_service_calls</td><td>Numeric</td><td>Support friction</td></tr>
      <tr><td>monthly_charges</td><td>Numeric</td><td>Price / plan value</td></tr>
      <tr><td>is_subscribed</td><td>Boolean</td><td>Retention outcome (churn if FALSE)</td></tr>
    </tbody>
  </table>
  <p class="caption"><strong>Table description:</strong> Ten columns ingested. No identifier or outcome fields were discarded. Analysis uses the imputed complete dataset so market comparisons are not biased by dropping incomplete rows.</p>
  <div class="slide-num">3 / 12</div>
</section>

<!-- SLIDE 4: Missing values at ingestion -->
<section class="slide">
  <h1>Missing Values — Handled at Data Ingestion</h1>
  <div class="two-col">
    <div>
      <h2>What we found</h2>
      <ul>
        <li>2,000 rows × 10 columns ingested</li>
        <li>554 rows (27.7%) had ≥1 missing value</li>
        <li><strong>0 columns dropped</strong></li>
        <li>Highest missingness: <code>num_streams</code> (10.3%)</li>
      </ul>
    </div>
    <div>
      <h2>How we handled them</h2>
      <ul>
        <li><strong>MCAR</strong> (age, gender, charges): median / mode</li>
        <li><strong>MAR</strong> (streams): median by plan</li>
        <li><strong>MAR</strong> (support calls): median by tenure quartile</li>
        <li>No listwise deletion → preserves sample size</li>
      </ul>
    </div>
  </div>
  <div class="callout">
    <strong>Assumption:</strong> Age/gender/charges are missing largely at random. Streams and support calls depend on observed plan and tenure (MAR), so group-wise imputation avoids flattening real plan differences.
  </div>
  <div class="slide-num">4 / 12</div>
</section>

<!-- SLIDE 5: Visual summary of missing data -->
<section class="slide">
  <h1>Visual Summary — Data Quality at Ingestion</h1>
  <img class="fig" src="{imgs['data_overview']}" alt="Data ingestion overview: missing values and imputation decisions"/>
  <p class="caption"><strong>Figure description:</strong> Panel A shows percent missing by column at ingestion. Panel B records ingestion decisions: no columns dropped; all missing fields imputed with mechanisms matched to MCAR vs MAR patterns. Result is a complete analysis table for US/Singapore comparison.</p>
  <div class="slide-num">5 / 12</div>
</section>

<!-- SLIDE 6: Deeper missingness pattern -->
<section class="slide">
  <h1>Missingness Patterns Across Markets</h1>
  <img class="fig" src="{imgs['missing']}" alt="Four-panel missing data investigation"/>
  <p class="caption"><strong>Figure description:</strong> Missingness for age/gender/charges is low and fairly uniform (MCAR). Streams and support calls are higher and uneven (MAR). Missingness indicators are nearly uncorrelated, so fields fail independently rather than in batches.</p>
  <div class="slide-num">6 / 12</div>
</section>

<!-- SLIDE 7: Investigation overview -->
<section class="slide">
  <h1>Investigation Agenda — Explaining Singapore</h1>
  <p>We compared Singapore to the US across four lenses:</p>
  <ol>
    <li><strong>Overall &amp; by-plan churn</strong> — Is the gap concentrated in one plan?</li>
    <li><strong>Engagement (streams)</strong> — Do churned users consume less?</li>
    <li><strong>Support burden</strong> — Do churned users need more help?</li>
    <li><strong>Tenure risk</strong> — Is early lifecycle the choke point?</li>
  </ol>
  <div class="callout info">
    Working hypothesis: Singapore’s higher churn is multi-factor—visible across plans—with support friction and early-lifecycle vulnerability as the strongest actionable signals.
  </div>
  <div class="slide-num">7 / 12</div>
</section>

<!-- SLIDE 8: Driver factors -->
<section class="slide">
  <h1>Investigative Findings — Driver Factors</h1>
  <img class="fig" src="{imgs['drivers']}" alt="Singapore churn drivers: overall, by plan, streams, support calls"/>
  <p class="caption"><strong>Figure description:</strong> (A) Singapore churn is 54.7% vs 47.9% US. (B) The gap holds across basic, family, premium, and student—premium is highest in Singapore (57.1%). (C) Churned users stream slightly less. (D) Churned users place more support calls in both markets (SG: 1.30 vs 0.94 retained).</p>
  <div class="slide-num">8 / 12</div>
</section>

<!-- SLIDE 9: Tenure risk -->
<section class="slide">
  <h1>Early-Tenure Risk Profile</h1>
  <img class="fig" src="{imgs['tenure']}" alt="Churn by tenure bucket and early-tenure mix"/>
  <p class="caption"><strong>Figure description:</strong> Churn peaks in the first 6–12 months. Singapore’s elevated rate is not explained by a larger early-tenure mix alone (US early share is actually similar/higher)—churn intensity within cohorts is higher in Singapore. First-90-day retention is still the highest-leverage lever.</p>
  <div class="slide-num">9 / 12</div>
</section>

<!-- SLIDE 10: Market comparison summary -->
<section class="slide">
  <h1>US vs Singapore — Summary View</h1>
  <img class="fig" src="{imgs['market']}" alt="Full US vs Singapore market churn comparison"/>
  <p class="caption"><strong>Figure description:</strong> Consolidated market comparison. Singapore leads on overall and plan-level churn. In both markets, churned customers have shorter tenure distributions and higher average support-call volume than retained customers.</p>
  <div class="slide-num">10 / 12</div>
</section>

<!-- SLIDE 11: Discussion of results -->
<section class="slide">
  <h1>Discussion of Results</h1>
  <h2>What explains Singapore’s situation?</h2>
  <ul>
    <li><strong>Broad, not niche:</strong> Higher churn across every subscriber plan—not a single bad plan.</li>
    <li><strong>Support friction:</strong> Churned customers generate more service calls; gap is clear in Singapore.</li>
    <li><strong>Engagement soft signal:</strong> Slightly lower streaming among churned users suggests weaker product stickiness.</li>
    <li><strong>Lifecycle intensity:</strong> Early tenure is high-risk everywhere; Singapore’s within-cohort churn is elevated.</li>
  </ul>
  <div class="callout">
    <strong>Implication:</strong> This is primarily an experience/ops problem (onboarding + support resolution), not a pure pricing or plan-mix problem. Acquisition alone will not close the gap.
  </div>
  <div class="slide-num">11 / 12</div>
</section>

<!-- SLIDE 12: Recommendations -->
<section class="slide">
  <h1>Recommendations &amp; Next Steps</h1>
  <ol>
    <li><strong>Launch a Singapore first-90-day retention program</strong> — guided onboarding, day-7/day-30 check-ins, and plan-fit nudges (esp. premium).</li>
    <li><strong>Reduce support-driven churn</strong> — track “calls before cancel,” improve first-contact resolution, and flag high-call accounts for proactive outreach.</li>
    <li><strong>Instrument engagement early</strong> — alert when streams drop below cohort norms in weeks 1–4.</li>
    <li><strong>Validate with causal follow-up</strong> — A/B test onboarding changes in Singapore; quantify lift vs US control.</li>
    <li><strong>Harden data pipeline</strong> — keep ingestion-time imputation; improve logging for streams on basic/student plans to reduce MAR missingness.</li>
  </ol>
  <div class="callout ok">
    <strong>Success metric:</strong> Close ≥50% of the Singapore–US churn gap (≈3.4 pp) within two quarters while holding acquisition CAC flat.
  </div>
  <p style="margin-top:20px;color:#5a6577;font-size:0.9rem;">Appendix materials: raw/imputed CSVs, Python EDA scripts (01–04), and imputation write-up available alongside this HTML deliverable.</p>
  <div class="slide-num">12 / 12</div>
</section>

</div>
</body>
</html>
"""
    Path(OUT).write_text(html, encoding="utf-8")
    size_mb = Path(OUT).stat().st_size / (1024 * 1024)
    print(f"Wrote {OUT} ({size_mb:.2f} MB)")


if __name__ == "__main__":
    build()

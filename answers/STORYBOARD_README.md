# Storyboard Deliverable — Upload Guide

## Project Title

**AAVAiL Market Risk Briefing: Diagnosing Elevated Churn in Singapore**

## File to upload

**Primary deliverable:** `AAVAIL_Singapore_Churn_Storyboard.html`

This is a self-contained (~20 min) HTML presentation with embedded figures. Open it in any browser; print to PDF if needed.

## Storyboard structure (12 slides)

1. Title & agenda  
2. Business opportunity (Singapore vs US churn gap)  
3. Data description (fields & roles)  
4. Missing values handled at ingestion (MCAR/MAR strategy)  
5. Visual summary of ingestion decisions  
6. Missingness patterns across markets  
7. Investigation agenda  
8. Driver factors (plan, engagement, support)  
9. Early-tenure risk profile  
10. Full US vs Singapore summary  
11. Discussion of results  
12. Recommendations & next steps  

## Grading criteria covered

| Requirement | Where |
|---|---|
| Identify & handle missing values at ingestion | Slides 4–5 |
| Visual summaries (missing counts, columns dropped) | Slides 5–6; 0 columns dropped |
| Investigative viz explaining Singapore | Slides 8–10 |
| Descriptions with each plot/table | Captions under every figure/table |
| Discussion & recommendations | Slides 11–12 |
| ~20 min presentation length | 12 slides, agenda on slide 1 |
| Portable format | Single HTML file (PDF via browser Print) |

## Rebuild (optional)

```bash
source .venv/bin/activate
pip install -r requirements.txt
python 04_singapore_investigation.py
python 05_build_storyboard_html.py
```

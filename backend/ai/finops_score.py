"""
FinOps Health Score Engine.

Calculates a composite score (0–100) from 5 weighted dimensions:

  1. Waste Ratio        (30%) — how much of spend is potentially wasted
  2. Resource Utilization (25%) — average CPU utilization across compute
  3. Tagging Coverage  (20%) — % of resources with team + project tags
  4. Anomaly Rate      (15%) — % of resources flagged as anomalous
  5. Cost Predictability (10%) — stability/smoothness of daily spend

Score → Grade mapping:
  90–100  A+
  80–89   A
  70–79   B
  60–69   C
  50–59   D
  0–49    F
"""
from typing import List, Dict
import numpy as np
import pandas as pd


def _grade(score: float) -> str:
    if score >= 90:
        return "A+"
    elif score >= 80:
        return "A"
    elif score >= 70:
        return "B"
    elif score >= 60:
        return "C"
    elif score >= 50:
        return "D"
    else:
        return "F"


def calculate_finops_score(
    df: pd.DataFrame,
    waste_findings: List[Dict],
    daily_costs: pd.Series,
) -> Dict:
    """
    df: full per-record billing DataFrame
    waste_findings: output of detect_waste()
    daily_costs: daily total cost Series indexed by date
    """
    dimensions = []

    if df.empty:
        return {
            "score": 0.0,
            "grade": "F",
            "explanation": "No billing data available. Upload billing records to compute a FinOps score.",
            "dimensions": [],
        }

    total_cost = float(df["cost"].sum())

    # ── Dimension 1: Waste Ratio (30%) ───────────────────────────────────────
    total_waste = sum(f["estimated_monthly_savings"] for f in waste_findings)
    waste_ratio = (total_waste / total_cost) if total_cost > 0 else 0.0
    # Score: 100 when waste=0%, 0 when waste≥60%
    waste_score = max(0.0, 100 - (waste_ratio / 0.60) * 100)
    waste_score = min(100.0, waste_score)
    dimensions.append({
        "name": "Waste Ratio",
        "score": round(waste_score, 1),
        "weight": 30,
        "detail": (
            f"Potential waste is {waste_ratio*100:.1f}% of total spend "
            f"(${total_waste:,.2f} of ${total_cost:,.2f}). "
            + ("Excellent waste control." if waste_score >= 80
               else "Significant savings opportunities detected.")
        ),
    })

    # ── Dimension 2: Resource Utilization (25%) ───────────────────────────────
    compute_df = df[df["avg_cpu_utilization"].notna() & (df["avg_cpu_utilization"] > 0)]
    if not compute_df.empty:
        avg_util = float(compute_df["avg_cpu_utilization"].mean())
        # Score: 100 at 60%+ utilization, 0 at 0%
        util_score = min(100.0, (avg_util / 60.0) * 100)
    else:
        avg_util = None
        util_score = 60.0  # neutral if no compute data
    dimensions.append({
        "name": "Resource Utilization",
        "score": round(util_score, 1),
        "weight": 25,
        "detail": (
            f"Average compute CPU utilization: {avg_util:.1f}%." if avg_util is not None
            else "No compute utilization data available."
        ) + (
            " Good utilization levels." if util_score >= 70
            else " Many resources appear underutilized."
        ),
    })

    # ── Dimension 3: Tagging Coverage (20%) ──────────────────────────────────
    resource_df = df.groupby("resource_id").first().reset_index()
    total_resources = len(resource_df)
    tagged = resource_df[
        resource_df["team"].notna() & resource_df["project"].notna()
        & (resource_df["team"] != "") & (resource_df["project"] != "")
    ]
    tagging_pct = (len(tagged) / total_resources * 100) if total_resources > 0 else 0.0
    tag_score = tagging_pct  # 1:1 mapping (100% tagged = 100 score)
    dimensions.append({
        "name": "Tagging Coverage",
        "score": round(tag_score, 1),
        "weight": 20,
        "detail": (
            f"{tagging_pct:.0f}% of resources ({len(tagged)}/{total_resources}) "
            f"have both 'team' and 'project' tags. "
            + ("Full tagging coverage." if tagging_pct >= 90
               else "Incomplete tagging reduces cost allocation accuracy.")
        ),
    })

    # ── Dimension 4: Anomaly Rate (15%) ──────────────────────────────────────
    anomaly_count = sum(1 for f in waste_findings if f["issue"] == "Anomalous cost pattern")
    anomaly_rate = (anomaly_count / max(total_resources, 1)) * 100
    # Score: 100 when anomaly_rate=0%, 0 when rate≥20%
    anomaly_score = max(0.0, 100 - (anomaly_rate / 20.0) * 100)
    dimensions.append({
        "name": "Anomaly Rate",
        "score": round(anomaly_score, 1),
        "weight": 15,
        "detail": (
            f"{anomaly_count} anomalous resource(s) detected out of {total_resources} total. "
            + ("No cost anomalies detected." if anomaly_count == 0
               else "Investigate flagged resources for unexpected charges.")
        ),
    })

    # ── Dimension 5: Cost Predictability (10%) ────────────────────────────────
    if len(daily_costs) >= 7:
        cv = float(daily_costs.std()) / float(daily_costs.mean()) if float(daily_costs.mean()) > 0 else 1.0
        # Score: 100 when CV=0 (perfectly stable), 0 when CV≥1 (very volatile)
        predictability_score = max(0.0, 100 - cv * 100)
    else:
        cv = None
        predictability_score = 50.0  # neutral
    dimensions.append({
        "name": "Cost Predictability",
        "score": round(predictability_score, 1),
        "weight": 10,
        "detail": (
            f"Daily cost variability (CV): {cv:.2f}." if cv is not None
            else "Insufficient data for variability analysis."
        ) + (
            " Spending is stable and predictable." if predictability_score >= 75
            else " Spending shows high day-to-day variability."
        ),
    })

    # ── Composite score ──────────────────────────────────────────────────────
    composite = sum(d["score"] * d["weight"] / 100 for d in dimensions)
    composite = round(composite, 1)
    grade = _grade(composite)

    # Plain-English summary
    worst = min(dimensions, key=lambda d: d["score"])
    best = max(dimensions, key=lambda d: d["score"])
    if composite >= 80:
        summary = f"Strong FinOps practice. Biggest improvement area: {worst['name']} ({worst['score']:.0f}/100)."
    elif composite >= 60:
        summary = f"Good cost governance with room to improve. Focus on {worst['name']} ({worst['score']:.0f}/100)."
    else:
        summary = (
            f"Significant FinOps gaps detected. Priority areas: "
            f"{worst['name']} ({worst['score']:.0f}/100) and waste reduction."
        )

    return {
        "score": composite,
        "grade": grade,
        "explanation": summary,
        "dimensions": dimensions,
    }

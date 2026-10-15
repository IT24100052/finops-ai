"""
FinOps Health Score Engine.

Calculates a composite score (0–100) from 5 weighted dimensions:

  1. Waste Ratio        (30%) — how much of verified spend is potentially wasted
  2. Resource Utilization (25%) — average CPU utilization across compute
  3. Tagging Coverage  (20%) — % of resources with team + project tags
  4. Anomaly Rate      (15%) — % of resources flagged as anomalous
  5. Cost Predictability (10%) — stability/smoothness of daily spend

Score -> Grade mapping:
  90–100  A+
  80–89   A
  70–79   B
  60–69   C
  50–59   D
  0–49    F
"""
from typing import List, Dict, Optional, Tuple
import numpy as np
import pandas as pd
from ai.waste_detection import (
    _detect_period_metadata,
    _is_demonstrably_comparable_period,
    aggregate_savings_conservatively,
)


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
    period_metadata: Optional[Tuple[bool, str]] = None,
) -> Dict:
    """
    df: full per-record billing DataFrame
    waste_findings: output of detect_waste()
    daily_costs: daily total cost Series indexed by date
    period_metadata: optional (is_monthly, period_label) tuple
    """
    dimensions = []

    if df.empty:
        return {
            "score": 0.0,
            "grade": "F",
            "explanation": "No billing data available. Upload billing records to compute a FinOps score.",
            "dimensions": [],
        }

    # Extract period metadata from df if not explicitly provided
    is_monthly, period_label = (
        period_metadata if period_metadata is not None else _detect_period_metadata(df)
    )

    # Clean and verify total costs (exclude non-finite, invalid, or negative values)
    cost_raw = pd.to_numeric(df["cost"], errors="coerce") if "cost" in df.columns else pd.Series(dtype=float)
    valid_costs = cost_raw[cost_raw.notna() & np.isfinite(cost_raw) & (cost_raw >= 0.0)]
    total_cost = float(valid_costs.sum()) if not valid_costs.empty else 0.0

    # ── Dimension 1: Waste Ratio (30%) ───────────────────────────────────────
    # Conservative non-overlapping aggregation for waste
    resource_cost_map = {}
    if not valid_costs.empty and "resource_id" in df.columns:
        valid_df = df.loc[valid_costs.index].assign(_clean_cost=valid_costs)
        resource_cost_map = valid_df.groupby("resource_id")["_clean_cost"].sum().to_dict()

    conservative_waste, gross_waste = aggregate_savings_conservatively(waste_findings, resource_cost_map)
    total_waste = conservative_waste

    # Check for demonstrably comparable periods with verified date boundaries
    periods_comparable = _is_demonstrably_comparable_period(is_monthly, period_label)

    # Check for unaligned observation periods between waste findings and df using explicit period metadata
    has_mismatched_period = False
    if waste_findings:
        findings_monthly_flags = [f.get("is_verified_monthly") for f in waste_findings if "is_verified_monthly" in f]
        if findings_monthly_flags and any(flag != is_monthly for flag in findings_monthly_flags):
            has_mismatched_period = True
        findings_periods = [f.get("savings_period") for f in waste_findings if "savings_period" in f]
        if findings_periods and any(p != period_label for p in findings_periods):
            has_mismatched_period = True

    if total_cost <= 0:
        # Avoid giving an artificially high score when spend is zero or unavailable
        waste_score = 50.0  # Neutral baseline
        waste_detail = "Insufficient verified spend data available in this period to evaluate waste ratio. Assigned neutral baseline score."
    elif has_mismatched_period or total_waste > total_cost:
        # Unaligned observation periods or savings exceed verified spend
        waste_score = 50.0  # Neutral fallback
        waste_detail = (
            f"Waste savings estimate (${total_waste:,.2f}) exceeds verified spend (${total_cost:,.2f}) "
            f"or represents unaligned observation periods. Applied neutral baseline score."
        )
    elif not periods_comparable:
        # Generic unanchored label (e.g. 'observed period') without exact date boundaries
        waste_score = 50.0  # Neutral fallback
        waste_detail = (
            f"Period comparability cannot be established for generic '{period_label}' without verified date boundaries. "
            f"Applied neutral baseline score."
        )
    else:
        waste_ratio = total_waste / total_cost
        # Score: 100 when waste=0%, 0 when waste>=60%
        waste_score = max(0.0, min(100.0, 100.0 - (waste_ratio / 0.60) * 100.0))
        overlap_note = f" (conservative aggregate from ${gross_waste:,.2f} gross estimates)" if gross_waste > total_waste else ""
        waste_detail = (
            f"Potential waste is {waste_ratio*100:.1f}% of verified spend "
            f"(${total_waste:,.2f} of ${total_cost:,.2f}{overlap_note}) across {period_label}. "
            + ("Excellent waste control." if waste_score >= 80
               else "Significant savings opportunities detected.")
        )

    dimensions.append({
        "name": "Waste Ratio",
        "score": round(waste_score, 1),
        "weight": 30,
        "detail": waste_detail,
    })

    # ── Dimension 2: Resource Utilization (25%) ───────────────────────────────
    cpu_raw = pd.to_numeric(df["avg_cpu_utilization"], errors="coerce") if "avg_cpu_utilization" in df.columns else pd.Series(dtype=float)
    valid_cpu = cpu_raw[cpu_raw.notna() & np.isfinite(cpu_raw) & (cpu_raw >= 0.0) & (cpu_raw <= 100.0)]

    if not valid_cpu.empty:
        avg_util = float(valid_cpu.mean())
        # Score: 100 at 60%+ utilization, 0 at 0%
        util_score = min(100.0, max(0.0, (avg_util / 60.0) * 100.0))
    else:
        avg_util = None
        util_score = 60.0  # Neutral baseline if no compute CPU data is available

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
    if "resource_id" in df.columns:
        resource_df = df.groupby("resource_id").first().reset_index()
    else:
        resource_df = df.copy()

    total_resources = len(resource_df)
    has_team = (
        resource_df["team"].notna() & (resource_df["team"].astype(str).str.strip() != "")
        if "team" in resource_df.columns
        else pd.Series(False, index=resource_df.index)
    )
    has_proj = (
        resource_df["project"].notna() & (resource_df["project"].astype(str).str.strip() != "")
        if "project" in resource_df.columns
        else pd.Series(False, index=resource_df.index)
    )
    tagged = resource_df[has_team & has_proj]
    tagging_pct = (len(tagged) / total_resources * 100.0) if total_resources > 0 else 0.0
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
    anomaly_count = sum(1 for f in waste_findings if f.get("issue") == "Anomalous cost pattern")
    anomaly_rate = (anomaly_count / max(total_resources, 1)) * 100.0
    # Score: 100 when anomaly_rate=0%, 0 when rate>=20%
    anomaly_score = max(0.0, min(100.0, 100.0 - (anomaly_rate / 20.0) * 100.0))

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
    if daily_costs is not None and len(daily_costs) >= 7:
        daily_num = pd.to_numeric(daily_costs, errors="coerce").dropna()
        daily_num = daily_num[np.isfinite(daily_num) & (daily_num >= 0.0)]
        if len(daily_num) >= 7 and float(daily_num.mean()) > 0:
            cv = float(daily_num.std()) / float(daily_num.mean())
            predictability_score = max(0.0, min(100.0, 100.0 - cv * 100.0))
        else:
            cv = None
            predictability_score = 50.0
    else:
        cv = None
        predictability_score = 50.0  # Neutral

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
    composite = sum(d["score"] * d["weight"] / 100.0 for d in dimensions)
    composite = round(composite, 1)

    worst = min(dimensions, key=lambda d: d["score"])
    if total_cost <= 0:
        # Avoid giving an artificially high score when spend is zero or unavailable
        composite = min(composite, 50.0)
        grade = _grade(composite)
        summary = (
            "Insufficient verified spend data to compute a complete FinOps score. "
            "Review data quality and upload verified cost records."
        )
    elif composite >= 80:
        grade = _grade(composite)
        summary = f"Strong FinOps practice. Biggest improvement area: {worst['name']} ({worst['score']:.0f}/100)."
    elif composite >= 60:
        grade = _grade(composite)
        summary = f"Good cost governance with room to improve. Focus on {worst['name']} ({worst['score']:.0f}/100)."
    else:
        grade = _grade(composite)
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

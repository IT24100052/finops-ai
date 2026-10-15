"""
AI Insights Router.

Existing endpoints preserved:
  GET /ai/prediction    — cost forecast
  GET /ai/waste         — waste findings
  GET /ai/insights      — combined dashboard insight cards

New endpoints:
  GET /ai/finops-score  — FinOps Health Score (0-100)
  GET /ai/data-quality  — Data quality analysis
"""
import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

import models
from database import get_db
from auth import get_current_user
from ai.cost_prediction import predict_next_period_cost
from ai.waste_detection import (
    detect_waste,
    _detect_period_metadata,
    _is_demonstrably_comparable_period,
    aggregate_savings_conservatively,
)
from ai.finops_score import calculate_finops_score
from ai.data_quality import analyse_data_quality
from routers.costs_router import _user_billing_df

router = APIRouter(prefix="/ai", tags=["ai insights"])


def _get_agg_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build per-resource aggregated DataFrame for waste/score engines.
    Excludes invalid, non-finite, and negative costs without silently coercing them.
    """
    if df.empty:
        return df
    group_cols = [
        "resource_id", "service", "instance_type", "provider",
        "region", "environment", "team", "resource_name", "resource_type", "project"
    ]
    existing = [c for c in group_cols if c in df.columns]

    clean_df = df.copy()
    if "cost" in clean_df.columns:
        c = pd.to_numeric(clean_df["cost"], errors="coerce")
        clean_df["cost"] = c.where(c.notna() & np.isfinite(c) & (c >= 0.0))
    if "usage_hours" in clean_df.columns:
        u = pd.to_numeric(clean_df["usage_hours"], errors="coerce")
        clean_df["usage_hours"] = u.where(u.notna() & np.isfinite(u) & (u >= 0.0))
    if "avg_cpu_utilization" in clean_df.columns:
        cpu = pd.to_numeric(clean_df["avg_cpu_utilization"], errors="coerce")
        clean_df["avg_cpu_utilization"] = cpu.where(cpu.notna() & np.isfinite(cpu) & (cpu >= 0.0) & (cpu <= 100.0))
    if "storage_gb" in clean_df.columns:
        s = pd.to_numeric(clean_df["storage_gb"], errors="coerce")
        clean_df["storage_gb"] = s.where(s.notna() & np.isfinite(s) & (s >= 0.0))

    agg = clean_df.groupby(existing, dropna=False).agg(
        usage_hours=("usage_hours", lambda s: s.sum(min_count=1) if s.notna().any() else np.nan),
        avg_cpu_utilization=("avg_cpu_utilization", "mean"),
        storage_gb=("storage_gb", "mean"),
        cost=("cost", lambda s: s.sum(min_count=1) if s.notna().any() else np.nan),
    ).reset_index()
    return agg


def _get_valid_daily_costs(df: pd.DataFrame) -> pd.Series:
    """Extract valid daily cost series (excluding negative, non-finite, and missing costs)."""
    if df.empty or "cost" not in df.columns or "date" not in df.columns:
        return pd.Series(dtype=float)
    cost_raw = pd.to_numeric(df["cost"], errors="coerce")
    valid_mask = cost_raw.notna() & np.isfinite(cost_raw) & (cost_raw >= 0.0)
    valid_df = df[valid_mask].copy()
    if valid_df.empty:
        return pd.Series(dtype=float)
    valid_df["_clean_cost"] = cost_raw[valid_mask]
    daily = valid_df.groupby("date")["_clean_cost"].sum()
    daily.index = pd.to_datetime(daily.index, errors="coerce")
    daily = daily[daily.index.notna()].sort_index()
    return daily


# ── Existing endpoints (preserved + extended) ────────────────────────────────

@router.get("/prediction")
def get_cost_prediction(
    horizon_days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    df = _user_billing_df(db, current_user.id)
    if df.empty:
        return {"message": "No billing data uploaded yet."}
    daily = _get_valid_daily_costs(df)
    return predict_next_period_cost(daily, horizon_days=horizon_days)


@router.get("/waste")
def get_waste_findings(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    df = _user_billing_df(db, current_user.id)
    if df.empty:
        return []
    is_monthly, period_label = _detect_period_metadata(df)
    agg = _get_agg_df(df)
    return detect_waste(agg, period_label=period_label, is_verified_monthly=is_monthly)


@router.get("/insights")
def get_combined_insights(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Combined dashboard insights: headline cards built on top of
    waste detection and cost prediction outputs.
    """
    df = _user_billing_df(db, current_user.id)
    if df.empty:
        return {"message": "No billing data uploaded yet."}

    cost_raw = pd.to_numeric(df["cost"], errors="coerce") if "cost" in df.columns else pd.Series(dtype=float)
    valid_costs = cost_raw[cost_raw.notna() & np.isfinite(cost_raw) & (cost_raw >= 0.0)]
    total_cost = float(valid_costs.sum()) if not valid_costs.empty else 0.0

    is_monthly, period_label = _detect_period_metadata(df)
    agg = _get_agg_df(df)
    waste_findings = detect_waste(agg, period_label=period_label, is_verified_monthly=is_monthly)

    # Conservative non-overlapping aggregation for achievable potential savings
    resource_cost_map = {}
    if not valid_costs.empty and "resource_id" in df.columns:
        valid_df = df.loc[valid_costs.index].assign(_clean_cost=valid_costs)
        resource_cost_map = valid_df.groupby("resource_id")["_clean_cost"].sum().to_dict()

    conservative_savings, gross_savings = aggregate_savings_conservatively(waste_findings, resource_cost_map)
    total_potential_savings = conservative_savings

    # Waste percentage: only calculated when savings and spend are demonstrably comparable and periods match
    has_mismatched_period = False
    if waste_findings:
        findings_monthly_flags = [f.get("is_verified_monthly") for f in waste_findings if "is_verified_monthly" in f]
        if findings_monthly_flags and any(flag != is_monthly for flag in findings_monthly_flags):
            has_mismatched_period = True
        findings_periods = [f.get("savings_period") for f in waste_findings if "savings_period" in f]
        if findings_periods and any(p != period_label for p in findings_periods):
            has_mismatched_period = True

    periods_comparable = _is_demonstrably_comparable_period(is_monthly, period_label) and not has_mismatched_period
    if periods_comparable and total_cost > 0:
        waste_pct = min(100.0, max(0.0, round((total_potential_savings / total_cost * 100.0), 1)))
    else:
        waste_pct = 0.0

    daily = _get_valid_daily_costs(df)
    prediction = predict_next_period_cost(daily, horizon_days=30)

    # FinOps score for dashboard badge
    finops = calculate_finops_score(df, waste_findings, daily, period_metadata=(is_monthly, period_label))

    period_suffix = "/month (verified monthly)" if is_monthly else f" (observed-period estimate across {period_label})"

    if gross_savings > conservative_savings:
        savings_msg = f"~${total_potential_savings:,.2f}{period_suffix} achievable savings, gross estimates up to ${gross_savings:,.2f}"
    else:
        savings_msg = f"~${total_potential_savings:,.2f}{period_suffix}"

    headline_cards = [
        {
            "icon": "trending-down",
            "title": "Potential Waste",
            "message": (
                f"You could be wasting {waste_pct:.0f}% of your cloud budget ({savings_msg})."
                if periods_comparable and total_cost > 0
                else f"Potential waste identified ({savings_msg}). Period alignment required to compute budget ratio."
            ),
        },
        {
            "icon": "calendar",
            "title": "Next 30-Day Forecast",
            "message": (
                f"Estimated cost: ${prediction['predicted_cost']:,.2f} "
                f"(${prediction['lower_bound']:,.2f}–${prediction['upper_bound']:,.2f}), "
                f"trend is {prediction['trend']}."
            ),
        },
        {
            "icon": "award",
            "title": "FinOps Score",
            "message": (
                f"Your FinOps Health Score is {finops['score']:.0f}/100 (Grade: {finops['grade']}). "
                f"{finops['explanation']}"
            ),
        },
    ]
    if waste_findings:
        top = waste_findings[0]
        headline_cards.append({
            "icon": "alert-triangle",
            "title": "Top Issue",
            "message": (
                f"{top['resource_id']} ({top['issue']}) — "
                f"potential savings of ${top['estimated_monthly_savings']:,.2f}{period_suffix}."
            ),
        })

    return {
        "total_cost":              round(total_cost, 2),
        "total_potential_savings": round(total_potential_savings, 2),
        "gross_potential_savings": round(gross_savings, 2),
        "net_potential_savings":   round(conservative_savings, 2),
        "waste_percentage":        round(waste_pct, 1),
        "is_verified_monthly":     is_monthly,
        "savings_period":          period_label,
        "top_issues":              waste_findings[:3],
        "prediction":              prediction,
        "finops_score":            finops["score"],
        "finops_grade":            finops["grade"],
        "headline_cards":          headline_cards,
    }


# ── New endpoints ────────────────────────────────────────────────────────────

@router.get("/finops-score")
def get_finops_score(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Full FinOps Health Score breakdown with dimension-level detail."""
    df = _user_billing_df(db, current_user.id)
    if df.empty:
        return {"message": "No billing data uploaded yet."}

    is_monthly, period_label = _detect_period_metadata(df)
    agg = _get_agg_df(df)
    waste_findings = detect_waste(agg, period_label=period_label, is_verified_monthly=is_monthly)
    daily = _get_valid_daily_costs(df)
    return calculate_finops_score(df, waste_findings, daily, period_metadata=(is_monthly, period_label))


@router.get("/data-quality")
def get_data_quality(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Data quality analysis of all uploaded billing records."""
    df = _user_billing_df(db, current_user.id)
    return analyse_data_quality(df)

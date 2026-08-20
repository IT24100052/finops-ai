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
import pandas as pd
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

import models
from database import get_db
from auth import get_current_user
from ai.cost_prediction import predict_next_period_cost
from ai.waste_detection import detect_waste
from ai.finops_score import calculate_finops_score
from ai.data_quality import analyse_data_quality
from routers.costs_router import _user_billing_df

router = APIRouter(prefix="/ai", tags=["ai insights"])


def _get_agg_df(df: pd.DataFrame) -> pd.DataFrame:
    """Build per-resource aggregated DataFrame for waste/score engines."""
    if df.empty:
        return df
    group_cols = [
        "resource_id", "service", "instance_type", "provider",
        "region", "environment", "team", "resource_name", "resource_type", "project"
    ]
    existing = [c for c in group_cols if c in df.columns]
    agg = df.groupby(existing, dropna=False).agg(
        usage_hours=("usage_hours", "sum"),
        avg_cpu_utilization=("avg_cpu_utilization", "mean"),
        storage_gb=("storage_gb", "mean"),
        cost=("cost", "sum"),
    ).reset_index()
    return agg


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
    daily = df.groupby("date")["cost"].sum()
    daily.index = pd.to_datetime(daily.index)
    return predict_next_period_cost(daily, horizon_days=horizon_days)


@router.get("/waste")
def get_waste_findings(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    df = _user_billing_df(db, current_user.id)
    if df.empty:
        return []
    agg = _get_agg_df(df)
    return detect_waste(agg)


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

    total_cost = float(df["cost"].sum())
    agg = _get_agg_df(df)
    waste_findings = detect_waste(agg)
    total_potential_savings = sum(f["estimated_monthly_savings"] for f in waste_findings)
    waste_pct = (total_potential_savings / total_cost * 100) if total_cost > 0 else 0

    daily = df.groupby("date")["cost"].sum()
    daily.index = pd.to_datetime(daily.index)
    prediction = predict_next_period_cost(daily, horizon_days=30)

    # FinOps score for dashboard badge
    finops = calculate_finops_score(df, waste_findings, daily)

    headline_cards = [
        {
            "icon": "trending-down",
            "title": "Potential Waste",
            "message": (
                f"You could be wasting {waste_pct:.0f}% of your cloud budget "
                f"(~${total_potential_savings:,.2f}/month)."
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
                f"potential savings of ${top['estimated_monthly_savings']:,.2f}/month."
            ),
        })

    return {
        "total_cost":             round(total_cost, 2),
        "total_potential_savings": round(total_potential_savings, 2),
        "waste_percentage":       round(waste_pct, 1),
        "top_issues":             waste_findings[:3],
        "prediction":             prediction,
        "finops_score":           finops["score"],
        "finops_grade":           finops["grade"],
        "headline_cards":         headline_cards,
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

    agg = _get_agg_df(df)
    waste_findings = detect_waste(agg)
    daily = df.groupby("date")["cost"].sum()
    daily.index = pd.to_datetime(daily.index)
    return calculate_finops_score(df, waste_findings, daily)


@router.get("/data-quality")
def get_data_quality(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Data quality analysis of all uploaded billing records."""
    df = _user_billing_df(db, current_user.id)
    return analyse_data_quality(df)

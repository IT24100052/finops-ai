import pandas as pd
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

import models
from database import get_db
from auth import get_current_user
from ai.cost_prediction import predict_next_period_cost
from ai.waste_detection import detect_waste
from routers.costs_router import _user_billing_df

router = APIRouter(prefix="/ai", tags=["ai insights"])


@router.get("/prediction")
def get_cost_prediction(horizon_days: int = 30, db: Session = Depends(get_db),
                         current_user: models.User = Depends(get_current_user)):
    df = _user_billing_df(db, current_user.id)
    if df.empty:
        return {"message": "No billing data uploaded yet."}
    daily = df.groupby("date")["cost"].sum()
    daily.index = pd.to_datetime(daily.index)
    return predict_next_period_cost(daily, horizon_days=horizon_days)


@router.get("/waste")
def get_waste_findings(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    df = _user_billing_df(db, current_user.id)
    if df.empty:
        return []
    agg = df.groupby(["resource_id", "service", "instance_type"], dropna=False).agg(
        usage_hours=("usage_hours", "sum"),
        avg_cpu_utilization=("avg_cpu_utilization", "mean"),
        storage_gb=("storage_gb", "mean"),
        cost=("cost", "sum"),
    ).reset_index()
    return detect_waste(agg)


@router.get("/insights")
def get_combined_insights(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """
    The headline feature for the dashboard: plain-English insight cards like
    "You are wasting 32% of your budget" -- built on top of the prediction
    and waste-detection outputs above.
    """
    df = _user_billing_df(db, current_user.id)
    if df.empty:
        return {"message": "No billing data uploaded yet."}

    total_cost = float(df["cost"].sum())

    agg = df.groupby(["resource_id", "service", "instance_type"], dropna=False).agg(
        usage_hours=("usage_hours", "sum"),
        avg_cpu_utilization=("avg_cpu_utilization", "mean"),
        storage_gb=("storage_gb", "mean"),
        cost=("cost", "sum"),
    ).reset_index()
    waste_findings = detect_waste(agg)
    total_potential_savings = sum(f["estimated_monthly_savings"] for f in waste_findings)
    waste_pct = (total_potential_savings / total_cost * 100) if total_cost > 0 else 0

    daily = df.groupby("date")["cost"].sum()
    daily.index = pd.to_datetime(daily.index)
    prediction = predict_next_period_cost(daily, horizon_days=30)

    headline_cards = [
        {
            "icon": "trending-down",
            "title": "Potential Waste",
            "message": f"You could be wasting {waste_pct:.0f}% of your cloud budget "
                       f"(~${total_potential_savings:,.2f}/month).",
        },
        {
            "icon": "calendar",
            "title": "Next 30-Day Forecast",
            "message": f"Estimated cost: ${prediction['predicted_cost']:,.2f} "
                       f"(range ${prediction['lower_bound']:,.2f}\u2013${prediction['upper_bound']:,.2f}), "
                       f"trend is {prediction['trend']}.",
        },
    ]
    if waste_findings:
        top = waste_findings[0]
        headline_cards.append({
            "icon": "alert-triangle",
            "title": "Top Issue",
            "message": f"{top['resource_id']} ({top['issue']}) -- "
                       f"potential savings of ${top['estimated_monthly_savings']:,.2f}/month.",
        })

    return {
        "total_cost": round(total_cost, 2),
        "total_potential_savings": round(total_potential_savings, 2),
        "waste_percentage": round(waste_pct, 1),
        "top_issues": waste_findings[:3],
        "prediction": prediction,
        "headline_cards": headline_cards,
    }

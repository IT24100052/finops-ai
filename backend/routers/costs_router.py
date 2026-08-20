import pandas as pd
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

import models
from database import get_db
from auth import get_current_user

router = APIRouter(prefix="/costs", tags=["costs"])


def _user_billing_df(db: Session, user_id: int) -> pd.DataFrame:
    rows = db.query(models.BillingRecord).filter(models.BillingRecord.owner_id == user_id).all()
    data = [{
        "date": r.date,
        "service": r.service,
        "resource_id": r.resource_id,
        "instance_type": r.instance_type,
        "usage_hours": r.usage_hours,
        "avg_cpu_utilization": r.avg_cpu_utilization,
        "storage_gb": r.storage_gb,
        "cost": r.cost,
    } for r in rows]
    return pd.DataFrame(data)


@router.get("/summary")
def cost_summary(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    df = _user_billing_df(db, current_user.id)
    if df.empty:
        return {"total_cost": 0, "record_count": 0, "service_breakdown": [], "date_range": None}

    total_cost = float(df["cost"].sum())
    service_breakdown = (
        df.groupby("service")["cost"].sum().sort_values(ascending=False).round(2)
    )
    return {
        "total_cost": round(total_cost, 2),
        "record_count": len(df),
        "service_breakdown": [
            {"service": s, "cost": c} for s, c in service_breakdown.items()
        ],
        "date_range": {
            "start": str(df["date"].min()),
            "end": str(df["date"].max()),
        },
    }


@router.get("/daily")
def daily_costs(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """Returns a daily total-cost time series -- feeds the dashboard line chart."""
    df = _user_billing_df(db, current_user.id)
    if df.empty:
        return []
    daily = df.groupby("date")["cost"].sum().round(2).sort_index()
    return [{"date": str(d), "cost": c} for d, c in daily.items()]


@router.get("/by-resource")
def cost_by_resource(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """Per-resource aggregate -- this is what feeds the AI waste detection engine."""
    df = _user_billing_df(db, current_user.id)
    if df.empty:
        return []
    agg = df.groupby(["resource_id", "service", "instance_type"], dropna=False).agg(
        usage_hours=("usage_hours", "sum"),
        avg_cpu_utilization=("avg_cpu_utilization", "mean"),
        storage_gb=("storage_gb", "mean"),
        cost=("cost", "sum"),
    ).reset_index().round(2)
    records = agg.to_dict(orient="records")
    return [
        {k: (None if isinstance(v, float) and pd.isna(v) else v) for k, v in r.items()}
        for r in records
    ]

"""
Budgets Router — Full CRUD for named budgets with current spend tracking.

Each budget has:
  - A monthly spend limit
  - A scope (overall | provider | service | team | project | environment)
  - Configurable alert thresholds (50/75/80/90/100/110%)

GET /budgets             → list user's budgets with live spend vs limit
POST /budgets            → create a budget
PUT /budgets/{id}        → update a budget
DELETE /budgets/{id}     → delete a budget
"""
from datetime import date
from typing import Optional
import pandas as pd

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from auth import get_current_user
from routers.costs_router import _user_billing_df

router = APIRouter(prefix="/budgets", tags=["budgets"])


def _current_month_spend(df: pd.DataFrame, scope: str, scope_value: Optional[str]) -> float:
    """Calculate spend for the current calendar month matching the budget scope."""
    if df.empty:
        return 0.0

    now = date.today()
    # Filter to current month
    month_df = df[
        pd.to_datetime(df["date"]).dt.year == now.year
    ]
    month_df = month_df[pd.to_datetime(month_df["date"]).dt.month == now.month]

    if month_df.empty:
        # Fall back to last 30 days if no current-month data
        month_df = df[pd.to_datetime(df["date"]) >= pd.to_datetime(str(now)[:7] + "-01")]

    if month_df.empty:
        return 0.0

    # Filter by scope
    if scope == "overall":
        pass  # all data
    elif scope == "provider" and scope_value:
        month_df = month_df[month_df["provider"].fillna("").str.lower() == scope_value.lower()]
    elif scope == "service" and scope_value:
        month_df = month_df[month_df["service"].fillna("").str.lower() == scope_value.lower()]
    elif scope == "team" and scope_value:
        month_df = month_df[month_df["team"].fillna("").str.lower() == scope_value.lower()]
    elif scope == "project" and scope_value:
        month_df = month_df[month_df["project"].fillna("").str.lower() == scope_value.lower()]
    elif scope == "environment" and scope_value:
        month_df = month_df[month_df["environment"].fillna("").str.lower() == scope_value.lower()]

    return round(float(month_df["cost"].sum()), 2)


def _enrich_budget(budget: models.Budget, df: pd.DataFrame) -> dict:
    """Compute live spend metrics for a budget record."""
    current_spend = _current_month_spend(df, budget.scope, budget.scope_value)
    limit = budget.monthly_limit
    remaining = max(round(limit - current_spend, 2), 0.0)
    utilization_pct = round(current_spend / limit * 100, 1) if limit > 0 else 0.0

    # Simple linear forecast: extrapolate current spend to full month
    now = date.today()
    days_in_month = 28 if now.month == 2 else 30 if now.month in [4, 6, 9, 11] else 31
    day_of_month = now.day
    daily_rate = current_spend / max(day_of_month, 1)
    forecasted_spend = round(daily_rate * days_in_month, 2)
    projected_overrun = max(round(forecasted_spend - limit, 2), 0.0)

    # Status and triggered thresholds
    triggered = []
    thresholds = [
        (50, budget.alert_at_50),
        (75, budget.alert_at_75),
        (80, budget.alert_at_80),
        (90, budget.alert_at_90),
        (100, budget.alert_at_100),
        (110, budget.alert_at_110),
    ]
    for pct, enabled in thresholds:
        if enabled and utilization_pct >= pct:
            triggered.append(pct)

    if utilization_pct >= 100:
        budget_status = "exceeded"
    elif utilization_pct >= 90:
        budget_status = "critical"
    elif utilization_pct >= 75:
        budget_status = "warning"
    else:
        budget_status = "ok"

    return {
        "id":                budget.id,
        "name":              budget.name,
        "scope":             budget.scope,
        "scope_value":       budget.scope_value,
        "monthly_limit":     limit,
        "current_spend":     current_spend,
        "remaining":         remaining,
        "utilization_pct":   utilization_pct,
        "forecasted_spend":  forecasted_spend,
        "projected_overrun": projected_overrun,
        "status":            budget_status,
        "triggered_thresholds": triggered,
        "alert_at_50":       budget.alert_at_50,
        "alert_at_75":       budget.alert_at_75,
        "alert_at_80":       budget.alert_at_80,
        "alert_at_90":       budget.alert_at_90,
        "alert_at_100":      budget.alert_at_100,
        "alert_at_110":      budget.alert_at_110,
    }


@router.get("")
def list_budgets(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    budgets = db.query(models.Budget).filter(
        models.Budget.owner_id == current_user.id
    ).all()
    df = _user_billing_df(db, current_user.id)
    return [_enrich_budget(b, df) for b in budgets]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_budget(
    budget_in: schemas.BudgetCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if budget_in.monthly_limit <= 0:
        raise HTTPException(status_code=400, detail="monthly_limit must be greater than 0")

    budget = models.Budget(
        owner_id=current_user.id,
        name=budget_in.name,
        scope=budget_in.scope,
        scope_value=budget_in.scope_value,
        monthly_limit=budget_in.monthly_limit,
        alert_at_50=budget_in.alert_at_50,
        alert_at_75=budget_in.alert_at_75,
        alert_at_80=budget_in.alert_at_80,
        alert_at_90=budget_in.alert_at_90,
        alert_at_100=budget_in.alert_at_100,
        alert_at_110=budget_in.alert_at_110,
    )
    db.add(budget)
    db.commit()
    db.refresh(budget)
    df = _user_billing_df(db, current_user.id)
    return _enrich_budget(budget, df)


@router.put("/{budget_id}")
def update_budget(
    budget_id: int,
    budget_in: schemas.BudgetUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    budget = db.query(models.Budget).filter(
        models.Budget.id == budget_id,
        models.Budget.owner_id == current_user.id,
    ).first()
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")

    for field, value in budget_in.model_dump(exclude_none=True).items():
        setattr(budget, field, value)

    db.commit()
    db.refresh(budget)
    df = _user_billing_df(db, current_user.id)
    return _enrich_budget(budget, df)


@router.delete("/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_budget(
    budget_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    budget = db.query(models.Budget).filter(
        models.Budget.id == budget_id,
        models.Budget.owner_id == current_user.id,
    ).first()
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    db.delete(budget)
    db.commit()

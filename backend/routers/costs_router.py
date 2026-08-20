"""
Costs Router — Analytics endpoints for billing data.
Existing endpoints (summary, daily, by-resource) are preserved.
New endpoints added: by-provider, by-region, by-team, by-project, by-environment.
All endpoints support optional query filters.
"""
from typing import Optional
import pandas as pd
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

import models
from database import get_db
from auth import get_current_user

router = APIRouter(prefix="/costs", tags=["costs"])


# ── Data loader ──────────────────────────────────────────────────────────────

def _user_billing_df(
    db: Session,
    user_id: int,
    provider: Optional[str] = None,
    region: Optional[str] = None,
    environment: Optional[str] = None,
    team: Optional[str] = None,
    department: Optional[str] = None,
    project: Optional[str] = None,
    service: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> pd.DataFrame:
    """Load billing records for a user into a DataFrame with optional filters."""
    rows = db.query(models.BillingRecord).filter(
        models.BillingRecord.owner_id == user_id
    ).all()

    data = [{
        "date":                 r.date,
        "provider":             r.provider,
        "account_id":           r.account_id,
        "service":              r.service,
        "resource_id":          r.resource_id,
        "resource_name":        r.resource_name,
        "resource_type":        r.resource_type,
        "region":               r.region,
        "availability_zone":    r.availability_zone,
        "environment":          r.environment,
        "team":                 r.team,
        "department":           r.department,
        "project":              r.project,
        "instance_type":        r.instance_type,
        "tags":                 r.tags,
        "usage_hours":          r.usage_hours,
        "avg_cpu_utilization":  r.avg_cpu_utilization,
        "storage_gb":           r.storage_gb,
        "usage_quantity":       r.usage_quantity,
        "usage_unit":           r.usage_unit,
        "currency":             r.currency,
        "list_cost":            r.list_cost,
        "discount":             r.discount,
        "cost":                 r.cost,
    } for r in rows]

    df = pd.DataFrame(data)
    if df.empty:
        return df

    # Apply filters
    if provider:
        df = df[df["provider"].fillna("").str.lower() == provider.lower()]
    if region:
        df = df[df["region"].fillna("").str.lower() == region.lower()]
    if environment:
        df = df[df["environment"].fillna("").str.lower() == environment.lower()]
    if team:
        df = df[df["team"].fillna("").str.lower() == team.lower()]
    if department:
        df = df[df["department"].fillna("").str.lower() == department.lower()]
    if project:
        df = df[df["project"].fillna("").str.lower() == project.lower()]
    if service:
        df = df[df["service"].fillna("").str.lower() == service.lower()]
    if date_from:
        df = df[pd.to_datetime(df["date"]) >= pd.to_datetime(date_from)]
    if date_to:
        df = df[pd.to_datetime(df["date"]) <= pd.to_datetime(date_to)]

    return df


def _clean_breakdown(series: pd.Series, key_name: str):
    """Convert a groupby sum series to a clean list of dicts, replacing NaN labels."""
    result = []
    for k, v in series.items():
        label = k if (k and not (isinstance(k, float) and pd.isna(k))) else "Untagged"
        result.append({key_name: label, "cost": round(float(v), 2)})
    return result


# ── Existing endpoints (preserved) ──────────────────────────────────────────

@router.get("/summary")
def cost_summary(
    provider: Optional[str] = Query(None),
    region: Optional[str] = Query(None),
    environment: Optional[str] = Query(None),
    team: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    df = _user_billing_df(db, current_user.id, provider=provider, region=region,
                          environment=environment, team=team,
                          date_from=date_from, date_to=date_to)
    if df.empty:
        return {"total_cost": 0, "record_count": 0, "service_breakdown": [], "date_range": None}

    total_cost = float(df["cost"].sum())
    service_breakdown = (
        df.groupby("service")["cost"].sum().sort_values(ascending=False).round(2)
    )

    # Extra stats
    providers = sorted(df["provider"].dropna().unique().tolist())
    regions = sorted(df["region"].dropna().unique().tolist())
    daily_avg = round(total_cost / max(df["date"].nunique(), 1), 2)
    resource_count = df["resource_id"].nunique()

    return {
        "total_cost": round(total_cost, 2),
        "record_count": len(df),
        "resource_count": resource_count,
        "daily_average": daily_avg,
        "service_breakdown": [
            {"service": s, "cost": c} for s, c in service_breakdown.items()
        ],
        "providers": providers,
        "regions": regions,
        "date_range": {
            "start": str(df["date"].min()),
            "end": str(df["date"].max()),
        },
    }


@router.get("/daily")
def daily_costs(
    provider: Optional[str] = Query(None),
    region: Optional[str] = Query(None),
    environment: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Daily total-cost time series — feeds the dashboard line chart."""
    df = _user_billing_df(db, current_user.id, provider=provider, region=region,
                          environment=environment, date_from=date_from, date_to=date_to)
    if df.empty:
        return []
    daily = df.groupby("date")["cost"].sum().round(2).sort_index()
    return [{"date": str(d), "cost": c} for d, c in daily.items()]


@router.get("/by-resource")
def cost_by_resource(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Per-resource aggregate — feeds the AI waste detection engine."""
    df = _user_billing_df(db, current_user.id)
    if df.empty:
        return []
    group_cols = ["resource_id", "service", "instance_type", "provider",
                  "region", "environment", "team", "resource_name", "resource_type"]
    existing_group_cols = [c for c in group_cols if c in df.columns]
    agg = df.groupby(existing_group_cols, dropna=False).agg(
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


# ── New breakdown endpoints ──────────────────────────────────────────────────

@router.get("/by-provider")
def cost_by_provider(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    df = _user_billing_df(db, current_user.id, date_from=date_from, date_to=date_to)
    if df.empty:
        return []
    breakdown = df.groupby(df["provider"].fillna("Generic"))["cost"].sum().sort_values(ascending=False)
    return _clean_breakdown(breakdown, "provider")


@router.get("/by-region")
def cost_by_region(
    provider: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    df = _user_billing_df(db, current_user.id, provider=provider,
                          date_from=date_from, date_to=date_to)
    if df.empty:
        return []
    breakdown = df.groupby(df["region"].fillna("Unknown"))["cost"].sum().sort_values(ascending=False)
    return _clean_breakdown(breakdown, "region")


@router.get("/by-service")
def cost_by_service(
    provider: Optional[str] = Query(None),
    region: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    df = _user_billing_df(db, current_user.id, provider=provider, region=region,
                          date_from=date_from, date_to=date_to)
    if df.empty:
        return []
    breakdown = df.groupby("service")["cost"].sum().sort_values(ascending=False)
    return _clean_breakdown(breakdown, "service")


@router.get("/by-team")
def cost_by_team(
    provider: Optional[str] = Query(None),
    environment: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    df = _user_billing_df(db, current_user.id, provider=provider, environment=environment,
                          date_from=date_from, date_to=date_to)
    if df.empty:
        return []
    breakdown = df.groupby(df["team"].fillna("Untagged"))["cost"].sum().sort_values(ascending=False)
    return _clean_breakdown(breakdown, "team")


@router.get("/by-project")
def cost_by_project(
    provider: Optional[str] = Query(None),
    team: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    df = _user_billing_df(db, current_user.id, provider=provider, team=team,
                          date_from=date_from, date_to=date_to)
    if df.empty:
        return []
    breakdown = df.groupby(df["project"].fillna("Untagged"))["cost"].sum().sort_values(ascending=False)
    return _clean_breakdown(breakdown, "project")


@router.get("/by-environment")
def cost_by_environment(
    provider: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    df = _user_billing_df(db, current_user.id, provider=provider,
                          date_from=date_from, date_to=date_to)
    if df.empty:
        return []
    breakdown = df.groupby(df["environment"].fillna("Untagged"))["cost"].sum().sort_values(ascending=False)
    return _clean_breakdown(breakdown, "environment")


# ── Resource views ──────────────────────────────────────────────────────────

@router.get("/resources")
def list_resources(
    provider: Optional[str] = Query(None),
    service: Optional[str] = Query(None),
    region: Optional[str] = Query(None),
    environment: Optional[str] = Query(None),
    team: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Paginated resource list with aggregate metrics."""
    df = _user_billing_df(db, current_user.id, provider=provider, service=service,
                          region=region, environment=environment, team=team)
    if df.empty:
        return []

    group_cols = ["resource_id", "resource_name", "resource_type", "provider",
                  "service", "region", "environment", "team", "instance_type"]
    existing = [c for c in group_cols if c in df.columns]
    agg = df.groupby(existing, dropna=False).agg(
        total_cost=("cost", "sum"),
        days_active=("date", "nunique"),
        avg_cpu=("avg_cpu_utilization", "mean"),
        total_hours=("usage_hours", "sum"),
        storage_gb=("storage_gb", "mean"),
    ).reset_index().round(2)

    records = agg.to_dict(orient="records")
    cleaned = [
        {k: (None if isinstance(v, float) and pd.isna(v) else v) for k, v in r.items()}
        for r in records
    ]
    # Sort by total cost desc
    cleaned.sort(key=lambda x: x.get("total_cost", 0), reverse=True)
    return cleaned


@router.get("/resources/{resource_id}")
def get_resource_detail(
    resource_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Full resource detail with cost history."""
    df = _user_billing_df(db, current_user.id)
    if df.empty:
        return {"error": "No billing data"}

    rdf = df[df["resource_id"] == resource_id]
    if rdf.empty:
        return {"error": f"Resource '{resource_id}' not found"}

    # Metadata from latest record
    meta_row = rdf.sort_values("date").iloc[-1]
    meta = {
        "resource_id":       resource_id,
        "resource_name":     meta_row.get("resource_name"),
        "resource_type":     meta_row.get("resource_type"),
        "provider":          meta_row.get("provider"),
        "account_id":        meta_row.get("account_id"),
        "service":           meta_row.get("service"),
        "region":            meta_row.get("region"),
        "instance_type":     meta_row.get("instance_type"),
        "environment":       meta_row.get("environment"),
        "team":              meta_row.get("team"),
        "project":           meta_row.get("project"),
        "tags":              meta_row.get("tags"),
    }
    # Clean NaN
    meta = {k: (None if isinstance(v, float) and pd.isna(v) else v) for k, v in meta.items()}

    # Aggregate metrics
    total_cost = round(float(rdf["cost"].sum()), 2)
    avg_cpu = rdf["avg_cpu_utilization"].mean()
    avg_cpu = round(float(avg_cpu), 1) if not pd.isna(avg_cpu) else None
    total_hours = round(float(rdf["usage_hours"].sum()), 1)
    avg_storage = rdf["storage_gb"].mean()
    avg_storage = round(float(avg_storage), 1) if not pd.isna(avg_storage) else None

    # Daily cost history
    daily_history = (
        rdf.groupby("date")["cost"].sum().round(2).sort_index()
    )
    cost_history = [{"date": str(d), "cost": c} for d, c in daily_history.items()]

    return {
        **meta,
        "total_cost":    total_cost,
        "avg_cpu":       avg_cpu,
        "total_hours":   total_hours,
        "avg_storage_gb": avg_storage,
        "days_active":   int(rdf["date"].nunique()),
        "cost_history":  cost_history,
    }

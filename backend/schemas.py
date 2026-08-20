from pydantic import BaseModel, EmailStr
from datetime import date as date_type
from typing import Optional, List, Dict, Any


# ── Auth ─────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: EmailStr
    role: str

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ── Billing Records ───────────────────────────────────────────────────────────

class BillingRecordOut(BaseModel):
    date: date_type
    provider: Optional[str] = None
    account_id: Optional[str] = None
    service: str
    resource_id: str
    resource_name: Optional[str] = None
    resource_type: Optional[str] = None
    region: Optional[str] = None
    availability_zone: Optional[str] = None
    environment: Optional[str] = None
    team: Optional[str] = None
    department: Optional[str] = None
    project: Optional[str] = None
    instance_type: Optional[str] = None
    usage_hours: float = 0.0
    avg_cpu_utilization: Optional[float] = None
    storage_gb: Optional[float] = None
    usage_quantity: Optional[float] = None
    usage_unit: Optional[str] = None
    currency: Optional[str] = "USD"
    list_cost: Optional[float] = None
    discount: Optional[float] = None
    cost: float
    billing_period_start: Optional[date_type] = None
    billing_period_end: Optional[date_type] = None
    tags: Optional[str] = None

    class Config:
        from_attributes = True


# ── AI — Waste Detection ──────────────────────────────────────────────────────

class WasteFinding(BaseModel):
    resource_id: str
    resource_name: Optional[str] = None
    provider: Optional[str] = None
    service: str
    region: Optional[str] = None
    environment: Optional[str] = None
    team: Optional[str] = None
    instance_type: Optional[str] = None
    issue: str
    severity: str                   # "critical" | "high" | "medium" | "low"
    monthly_cost: float
    estimated_monthly_savings: float
    savings_percentage: float
    detail: str
    recommendation: str
    confidence: str                 # "high" | "medium" | "low"


# ── AI — Cost Prediction ─────────────────────────────────────────────────────

class CostPrediction(BaseModel):
    next_period_days: int
    predicted_cost: float
    lower_bound: float
    upper_bound: float
    trend: str                              # "rising" | "falling" | "flat"
    daily_avg_recent: float
    historical_average: float
    forecast_change_percentage: float
    confidence: str                         # "high" | "medium" | "low"
    explanation: str


# ── AI — FinOps Score ────────────────────────────────────────────────────────

class FinOpsScoreDimension(BaseModel):
    name: str
    score: float       # 0-100
    weight: float
    detail: str


class FinOpsScoreOut(BaseModel):
    score: float                           # 0-100
    grade: str                             # A+ / A / B / C / D / F
    explanation: str
    dimensions: List[FinOpsScoreDimension]


# ── AI — Data Quality ────────────────────────────────────────────────────────

class DataQualityFieldIssue(BaseModel):
    field: str
    missing_count: int
    missing_pct: float
    impact: str                            # "high" | "medium" | "low"


class DataQualityOut(BaseModel):
    score: float                           # 0-100
    total_records: int
    valid_records: int
    invalid_records: int
    duplicate_records: int
    missing_provider: int
    missing_region: int
    missing_environment: int
    missing_team: int
    missing_tags: int
    invalid_cpu_values: int
    invalid_costs: int
    tagging_coverage_pct: float
    field_issues: List[DataQualityFieldIssue]
    recommendations: List[str]


# ── Budgets ───────────────────────────────────────────────────────────────────

class BudgetCreate(BaseModel):
    name: str
    scope: str = "overall"        # overall | provider | service | team | project | environment
    scope_value: Optional[str] = None
    monthly_limit: float
    alert_at_50: bool = True
    alert_at_75: bool = True
    alert_at_80: bool = True
    alert_at_90: bool = True
    alert_at_100: bool = True
    alert_at_110: bool = False


class BudgetUpdate(BaseModel):
    name: Optional[str] = None
    monthly_limit: Optional[float] = None
    alert_at_50: Optional[bool] = None
    alert_at_75: Optional[bool] = None
    alert_at_80: Optional[bool] = None
    alert_at_90: Optional[bool] = None
    alert_at_100: Optional[bool] = None
    alert_at_110: Optional[bool] = None


class BudgetOut(BaseModel):
    id: int
    name: str
    scope: str
    scope_value: Optional[str] = None
    monthly_limit: float
    current_spend: float = 0.0
    remaining: float = 0.0
    utilization_pct: float = 0.0
    forecasted_spend: float = 0.0
    projected_overrun: float = 0.0
    status: str = "ok"             # ok | warning | critical | exceeded
    triggered_thresholds: List[int] = []
    alert_at_50: bool = True
    alert_at_75: bool = True
    alert_at_80: bool = True
    alert_at_90: bool = True
    alert_at_100: bool = True
    alert_at_110: bool = False

    class Config:
        from_attributes = True


# ── Upload Response ───────────────────────────────────────────────────────────

class UploadResponse(BaseModel):
    filename: str
    rows_inserted: int
    rows_rejected: int
    validation_errors: List[str]
    total_cost: float
    date_range: Optional[Dict[str, str]] = None
    services_detected: List[str]
    providers_detected: List[str]

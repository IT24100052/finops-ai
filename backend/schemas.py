from pydantic import BaseModel, EmailStr
from datetime import date as date_type
from typing import Optional


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


class BillingRecordOut(BaseModel):
    date: date_type
    service: str
    resource_id: str
    instance_type: Optional[str] = None
    usage_hours: float
    avg_cpu_utilization: Optional[float] = None
    storage_gb: Optional[float] = None
    cost: float

    class Config:
        from_attributes = True


class WasteFinding(BaseModel):
    resource_id: str
    service: str
    instance_type: Optional[str]
    issue: str
    detail: str
    monthly_cost: float
    estimated_monthly_savings: float
    severity: str  # "high" | "medium" | "low"
    recommendation: str


class CostPrediction(BaseModel):
    next_period_days: int
    predicted_cost: float
    lower_bound: float
    upper_bound: float
    trend: str  # "rising" | "falling" | "flat"
    daily_avg_recent: float

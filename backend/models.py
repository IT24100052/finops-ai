from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey, Boolean
from sqlalchemy.sql import func
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="user")  # "user" or "admin"
    created_at = Column(DateTime, server_default=func.now())


class BillingRecord(Base):
    """
    One row = one resource's usage/cost on a given day.
    Mirrors line-item data from AWS CUR / Azure Cost Export / GCP Billing Export.
    All fields beyond the core 5 (date, provider, service, resource_id, cost) are optional
    to support heterogeneous cloud billing formats.
    """
    __tablename__ = "billing_records"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # ── Core fields (required on upload) ──
    date = Column(Date, nullable=False, index=True)
    service = Column(String, nullable=False)           # EC2, S3, Compute Engine, etc.
    resource_id = Column(String, nullable=False)        # i-0a1b2c3d, vm-prod-01, etc.
    cost = Column(Float, nullable=False)

    # ── Cloud provider / account context ──
    provider = Column(String, nullable=True, index=True)   # AWS | Azure | GCP
    account_id = Column(String, nullable=True, index=True) # AWS account, Azure sub, GCP project
    region = Column(String, nullable=True, index=True)     # us-east-1, eastus, us-central1
    availability_zone = Column(String, nullable=True)      # us-east-1a (AWS only)

    # ── Cost allocation tags ──
    environment = Column(String, nullable=True, index=True)  # production | staging | development
    team = Column(String, nullable=True, index=True)
    department = Column(String, nullable=True)
    project = Column(String, nullable=True, index=True)

    # ── Resource metadata ──
    resource_name = Column(String, nullable=True)       # human-readable name
    resource_type = Column(String, nullable=True)       # compute | storage | database | network
    instance_type = Column(String, nullable=True)       # m5.xlarge, Standard_D4s_v3, n2-standard-4
    tags = Column(String, nullable=True)                # project=x;team=y;env=prod (k=v semicolons)

    # ── Usage metrics ──
    usage_hours = Column(Float, default=0.0)
    avg_cpu_utilization = Column(Float, nullable=True)  # percent, 0-100
    storage_gb = Column(Float, nullable=True)
    usage_quantity = Column(Float, nullable=True)       # generic usage amount
    usage_unit = Column(String, nullable=True)          # hours | GB-month | requests | etc.

    # ── Financial details ──
    currency = Column(String, nullable=True, default="USD")
    list_cost = Column(Float, nullable=True)    # undiscounted/on-demand price
    discount = Column(Float, nullable=True)     # discount amount applied

    # ── Billing period ──
    billing_period_start = Column(Date, nullable=True)
    billing_period_end = Column(Date, nullable=True)


class Budget(Base):
    """
    Named budget with a monthly spend limit and threshold alerts.
    Scope can be: overall | provider | service | team | project | environment
    """
    __tablename__ = "budgets"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    name = Column(String, nullable=False)
    scope = Column(String, nullable=False, default="overall")       # overall | provider | service | team | project | environment
    scope_value = Column(String, nullable=True)                     # e.g. "EC2" if scope=service

    monthly_limit = Column(Float, nullable=False)

    # Alert thresholds (True = enabled)
    alert_at_50 = Column(Boolean, default=True)
    alert_at_75 = Column(Boolean, default=True)
    alert_at_80 = Column(Boolean, default=True)
    alert_at_90 = Column(Boolean, default=True)
    alert_at_100 = Column(Boolean, default=True)
    alert_at_110 = Column(Boolean, default=False)

    created_at = Column(DateTime, server_default=func.now())

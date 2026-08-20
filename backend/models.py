from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey
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
    This mirrors the kind of line-item data you'd get from an
    AWS Cost & Usage Report / Azure Cost Management export.
    """
    __tablename__ = "billing_records"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    date = Column(Date, nullable=False, index=True)
    service = Column(String, nullable=False)          # e.g. EC2, S3, RDS
    resource_id = Column(String, nullable=False)       # e.g. i-0a1b2c3d
    instance_type = Column(String, nullable=True)      # e.g. m5.xlarge
    usage_hours = Column(Float, default=0.0)
    avg_cpu_utilization = Column(Float, nullable=True)  # percent, 0-100
    storage_gb = Column(Float, nullable=True)
    cost = Column(Float, nullable=False)

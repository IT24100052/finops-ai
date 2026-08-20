import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv()

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

if not SQLALCHEMY_DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set")

# For SQLite: connect_args needed for thread safety in FastAPI
connect_args = {}
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args=connect_args)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Safe incremental migration ──────────────────────────────────────────────
# Adds new columns to billing_records without touching existing data.
# Uses try/except per column so it is idempotent — safe to run every startup.

_NEW_BILLING_COLUMNS = [
    ("provider",              "VARCHAR"),
    ("account_id",            "VARCHAR"),
    ("region",                "VARCHAR"),
    ("availability_zone",     "VARCHAR"),
    ("environment",           "VARCHAR"),
    ("team",                  "VARCHAR"),
    ("department",            "VARCHAR"),
    ("project",               "VARCHAR"),
    ("resource_name",         "VARCHAR"),
    ("resource_type",         "VARCHAR"),
    ("tags",                  "VARCHAR"),
    ("usage_quantity",        "FLOAT"),
    ("usage_unit",            "VARCHAR"),
    ("currency",              "VARCHAR DEFAULT 'USD'"),
    ("list_cost",             "FLOAT"),
    ("discount",              "FLOAT"),
    ("billing_period_start",  "DATE"),
    ("billing_period_end",    "DATE"),
]

_NEW_BUDGET_COLUMNS = []  # Budget table is created fresh by create_all


def run_migrations():
    """
    Safely add new columns to billing_records if they don't already exist.
    This allows upgrading an existing database without losing data.
    Works for both SQLite and PostgreSQL.
    """
    is_sqlite = SQLALCHEMY_DATABASE_URL.startswith("sqlite")

    with engine.connect() as conn:
        for col_name, col_type in _NEW_BILLING_COLUMNS:
            try:
                if is_sqlite:
                    # SQLite does not support IF NOT EXISTS for ALTER TABLE
                    # so we catch the OperationalError if column exists
                    conn.execute(
                        text(f"ALTER TABLE billing_records ADD COLUMN {col_name} {col_type}")
                    )
                else:
                    # PostgreSQL supports this natively
                    conn.execute(
                        text(
                            f"ALTER TABLE billing_records "
                            f"ADD COLUMN IF NOT EXISTS {col_name} {col_type}"
                        )
                    )
                conn.commit()
            except Exception:
                # Column already exists — skip silently
                conn.rollback()
"""
Provider CSV Normalizer
=======================
Maps provider-specific column names and values to the internal
BillingRecord schema. Currently supports:
  - Generic (default)
  - AWS (Cost & Usage Report naming conventions)
  - Azure (Cost Management export naming conventions)
  - GCP (Cloud Billing export naming conventions)

Architecture is open for extension: add a new provider mapping below
without touching any router code.
"""
import calendar
import datetime
from typing import Optional, Tuple, Any
import numpy as np
import pandas as pd


# ── Column alias maps ────────────────────────────────────────────────────────
# Maps (provider_specific_column -> internal_column_name)

_AWS_ALIASES = {
    "lineitem_usagestartdate":         "date",
    "lineitem_productcode":            "service",
    "lineitem_resourceid":             "resource_id",
    "lineitem_unblendedcost":          "cost",
    "lineitem_lineitemdescription":    "resource_name",
    "lineitem_usagetype":              "usage_unit",
    "lineitem_usageamount":            "usage_quantity",
    "product_instancetype":            "instance_type",
    "product_region":                  "region",
    "product_location":                "availability_zone",
    "lineitem_availabilityzone":       "availability_zone",
    "user_environment":                "environment",
    "user_team":                       "team",
    "user_project":                    "project",
    "user_department":                 "department",
    "resourcetags_userenvironment":    "environment",
    "resourcetags_userteam":           "team",
    "resourcetags_userproject":        "project",
    "bill_payeraccountid":             "account_id",
    "lineitem_currencycode":           "currency",
    "pricing_publicondemandcost":      "list_cost",
    "billing_period_start_date":       "billing_period_start",
    "billing_period_end_date":         "billing_period_end",
}

_AZURE_ALIASES = {
    "date":                            "date",
    "servicename":                     "service",
    "resourceid":                      "resource_id",
    "cost":                            "cost",
    "pretaxcost":                      "cost",
    "costinbillingcurrency":           "cost",
    "resourcename":                    "resource_name",
    "resourcetype":                    "resource_type",
    "resourcelocation":                "region",
    "subscriptionid":                  "account_id",
    "subscriptionname":                "account_id",
    "tags":                            "tags",
    "currency":                        "currency",
    "billingcurrency":                 "currency",
    "quantity":                        "usage_quantity",
    "unitofmeasure":                   "usage_unit",
    "billingperiodstartdate":          "billing_period_start",
    "billingperiodenddate":            "billing_period_end",
}

_GCP_ALIASES = {
    "usage_start_time":                "date",
    "service_description":             "service",
    "resource_name":                   "resource_id",
    "cost":                            "cost",
    "resource_global_name":            "resource_name",
    "resource_type":                   "resource_type",
    "location_region":                 "region",
    "location_zone":                   "availability_zone",
    "project_id":                      "account_id",
    "project_name":                    "project",
    "currency":                        "currency",
    "usage_amount":                    "usage_quantity",
    "usage_unit":                      "usage_unit",
    "invoice_month":                   "billing_period_start",
    "labels":                          "tags",
}


def _parse_year_month(val: Any) -> Optional[Tuple[datetime.date, datetime.date]]:
    """
    Parses a YYYYMM or YYYY-MM string/number representing a billing month (e.g. 202606 or '2026-06').
    Returns (start_date, end_date) as datetime.date objects, where start is the 1st
    and end is the last calendar day of that month (taking leap years into account).
    Returns None if val is invalid, malformed, or out of range (1 <= month <= 12).
    """
    if val is None or (isinstance(val, float) and (np.isnan(val) or not np.isfinite(val))):
        return None
    if isinstance(val, float) and val.is_integer():
        s = str(int(val))
    else:
        s = str(val).strip()

    if not s:
        return None

    # Check for YYYYMM (exact 6 digits)
    if len(s) == 6 and s.isdigit():
        year = int(s[:4])
        month = int(s[4:])
    # Or YYYY-MM (e.g. 2026-06)
    elif len(s) == 7 and s[:4].isdigit() and s[4] == '-' and s[5:].isdigit():
        year = int(s[:4])
        month = int(s[5:])
    else:
        return None

    if not (1 <= month <= 12) or not (1970 <= year <= 2100):
        return None

    _, last_day = calendar.monthrange(year, month)
    start_date = datetime.date(year, month, 1)
    end_date = datetime.date(year, month, last_day)
    return start_date, end_date


def _parse_single_date(val: Any) -> Optional[datetime.date]:
    """
    Safely parses an ISO date or timestamp string/object into a datetime.date object.
    Does not convert raw integers or floats into epoch dates.
    Returns None if unparseable, malformed, or missing.
    """
    if val is None or (isinstance(val, float) and (np.isnan(val) or not np.isfinite(val))):
        return None
    if isinstance(val, datetime.datetime):
        return val.date()
    if isinstance(val, datetime.date):
        return val
    if not isinstance(val, str):
        return None
    s = val.strip()
    if not s:
        return None
    try:
        ts = pd.to_datetime(s, errors="coerce")
        if pd.isna(ts):
            return None
        return ts.date()
    except Exception:
        return None


def _detect_provider(columns: set) -> str:
    """Heuristically detect provider from column names."""
    # AWS CUR has lineitem_ prefix columns
    if any(c.startswith("lineitem_") for c in columns):
        return "AWS"
    # Azure has pretaxcost / billingcurrency
    if "pretaxcost" in columns or "billingcurrency" in columns or "subscriptionid" in columns:
        return "Azure"
    # GCP column names have already been normalized to underscores.
    if (
        "project_id" in columns
        or "location_region" in columns
        or "service_description" in columns
        or "usage_start_time" in columns
        or "invoice_month" in columns
    ):
        return "GCP"
    # Check explicit provider column
    return "Generic"


def normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize a raw uploaded CSV DataFrame into the internal BillingRecord schema.
    - Detects or reads provider column
    - Applies column aliases
    - Normalises provider-specific date formats (including GCP YYYYMM invoice-month)
    - Adds provider column if missing
    Returns a new DataFrame with internal column names.
    """
    # Work on lowercase column names for matching
    df = df.copy()
    df.columns = [c.strip().lower().replace(" ", "_").replace(".", "_") for c in df.columns]
    col_set = set(df.columns)


    # Detect the column format even when a provider column already exists.
    detected_provider = _detect_provider(col_set)

    # Select aliases based on the detected column format.
    if detected_provider == "AWS":
        alias_map = _AWS_ALIASES
    elif detected_provider == "Azure":
        alias_map = _AZURE_ALIASES
    elif detected_provider == "GCP":
        alias_map = _GCP_ALIASES
    else:
        alias_map = {}  # Generic — columns already use internal names


    # Apply renames (only rename columns that exist and aren't already present)
    rename_map = {}
    for src, dst in alias_map.items():
        if src in col_set and dst not in col_set:
            rename_map[src] = dst

    # Ensure invoice_month maps to billing_period_start even if detected as Generic
    if "invoice_month" in col_set and "billing_period_start" not in col_set:
        rename_map["invoice_month"] = "billing_period_start"

    if rename_map:
        df = df.rename(columns=rename_map)

    # Inject detected provider if not in data
    if detected_provider and "provider" not in df.columns:
        df["provider"] = detected_provider

    # Normalise date column — handle various formats
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date

    # Normalise billing period dates (including GCP YYYYMM invoice-month format)
    if "billing_period_start" in df.columns or "billing_period_end" in df.columns:
        if "billing_period_start" not in df.columns:
            df["billing_period_start"] = None
        if "billing_period_end" not in df.columns:
            df["billing_period_end"] = None

        new_starts = []
        new_ends = []

        for _, row in df.iterrows():
            raw_start = row.get("billing_period_start")
            raw_end = row.get("billing_period_end")

            ym_res = _parse_year_month(raw_start)
            if ym_res:
                s_date, e_date = ym_res
                new_starts.append(s_date)
                # If billing_period_end was not provided or is empty/NaT, populate calculated month end
                if raw_end is None or (isinstance(raw_end, float) and np.isnan(raw_end)) or str(raw_end).strip() in ("", "nan", "none", "nat"):
                    new_ends.append(e_date)
                else:
                    parsed_end = _parse_single_date(raw_end)
                    new_ends.append(parsed_end if parsed_end else e_date)
            else:
                # Standard date parsing (e.g. ISO 8601 strings)
                parsed_start = _parse_single_date(raw_start)
                parsed_end = _parse_single_date(raw_end)
                new_starts.append(parsed_start)
                new_ends.append(parsed_end)

        df["billing_period_start"] = new_starts
        df["billing_period_end"] = new_ends

    return df


# ── Internal column listing ──────────────────────────────────────────────────

REQUIRED_COLUMNS = {"date", "service", "resource_id", "cost"}

ALL_OPTIONAL_COLUMNS = [
    "provider", "account_id", "region", "availability_zone",
    "environment", "team", "department", "project",
    "resource_name", "resource_type", "instance_type", "tags",
    "usage_hours", "avg_cpu_utilization", "storage_gb",
    "usage_quantity", "usage_unit",
    "currency", "list_cost", "discount",
    "billing_period_start", "billing_period_end",
]

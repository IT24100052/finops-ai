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
from typing import Optional
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
    "service.description":             "service",
    "resource.name":                   "resource_id",
    "cost":                            "cost",
    "resource.global_name":            "resource_name",
    "resource.type":                   "resource_type",
    "location.region":                 "region",
    "location.zone":                   "availability_zone",
    "project.id":                      "account_id",
    "project.name":                    "project",
    "currency":                        "currency",
    "usage.amount":                    "usage_quantity",
    "usage.unit":                      "usage_unit",
    "invoice.month":                   "billing_period_start",
    "labels":                          "tags",
}


def _detect_provider(columns: set) -> str:
    """Heuristically detect provider from column names."""
    # AWS CUR has lineitem_ prefix columns
    if any(c.startswith("lineitem_") for c in columns):
        return "AWS"
    # Azure has pretaxcost / billingcurrency
    if "pretaxcost" in columns or "billingcurrency" in columns or "subscriptionid" in columns:
        return "Azure"
    # GCP has project.id or usage_start_time
    if "project.id" in columns or "location.region" in columns:
        return "GCP"
    # Check explicit provider column
    return "Generic"


def normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize a raw uploaded CSV DataFrame into the internal BillingRecord schema.
    - Detects or reads provider column
    - Applies column aliases
    - Normalises provider-specific date formats
    - Adds provider column if missing
    Returns a new DataFrame with internal column names.
    """
    # Work on lowercase column names for matching
    df = df.copy()
    df.columns = [c.strip().lower().replace(" ", "_").replace(".", "_") for c in df.columns]
    col_set = set(df.columns)

    # Detect provider from columns or existing 'provider' column
    if "provider" in col_set:
        detected_provider = None  # use per-row value
    else:
        detected_provider = _detect_provider(col_set)

    # Select the right alias map
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
    if rename_map:
        df = df.rename(columns=rename_map)

    # Inject detected provider if not in data
    if detected_provider and "provider" not in df.columns:
        df["provider"] = detected_provider

    # Normalise date column — handle various formats
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date

    for date_col in ("billing_period_start", "billing_period_end"):
        if date_col in df.columns:
            df[date_col] = pd.to_datetime(df[date_col], errors="coerce").dt.date

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

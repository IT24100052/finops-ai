"""
Waste Detection Engine.

Two layers, deliberately kept separate so you can explain each clearly
in a viva/interview:

1. RULE ENGINE (deterministic, explainable) -- encodes real FinOps
   heuristics that cloud cost consultants actually use:
     - Idle resources: running almost all month, near-zero CPU.
     - Oversized resources: large instance family, low utilization.
     - Low-efficiency storage: high cost-per-GB relative to the fleet.

2. ANOMALY DETECTION (statistical "AI" layer): an IsolationForest
   flags resources whose cost is anomalous *given* their own usage
   pattern (hours x utilization) -- i.e. resources costing far more
   than their actual workload would justify. This is the genuinely
   "ML" part of the waste engine, on top of the explainable rules.
"""
from typing import List, Dict
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

# Instance families we treat as "large" for the oversized-instance heuristic.
LARGE_INSTANCE_HINTS = ["xlarge", "2xlarge", "4xlarge", "8xlarge", "large"]

IDLE_CPU_THRESHOLD = 5.0          # % CPU below which a resource is "idle"
IDLE_USAGE_HOURS_THRESHOLD = 100  # hours/month running to count as "always on"
OVERSIZED_CPU_THRESHOLD = 30.0    # % CPU below which a large instance is "oversized"


def _is_large_instance(instance_type) -> bool:
    if not isinstance(instance_type, str) or not instance_type:
        return False
    return any(hint in instance_type.lower() for hint in LARGE_INSTANCE_HINTS)


def _clean_instance_type(value):
    if isinstance(value, str):
        return value
    return None


def detect_waste(df: pd.DataFrame) -> List[Dict]:
    """
    df columns expected: resource_id, service, instance_type,
    usage_hours, avg_cpu_utilization, storage_gb, cost
    (already aggregated per-resource over the analysis period)
    """
    findings = []

    if df.empty:
        return findings

    # ---- Rule 1: Idle compute resources ----
    idle_mask = (
        (df["avg_cpu_utilization"].fillna(100) < IDLE_CPU_THRESHOLD)
        & (df["usage_hours"].fillna(0) >= IDLE_USAGE_HOURS_THRESHOLD)
    )
    for _, row in df[idle_mask].iterrows():
        findings.append({
            "resource_id": row["resource_id"],
            "service": row["service"],
            "instance_type": _clean_instance_type(row.get("instance_type")),
            "issue": "Idle resource",
            "detail": f"Running {row['usage_hours']:.0f} hrs with only "
                      f"{row['avg_cpu_utilization']:.1f}% avg CPU utilization.",
            "monthly_cost": round(float(row["cost"]), 2),
            "estimated_monthly_savings": round(float(row["cost"]) * 0.9, 2),
            "severity": "high",
            "recommendation": "Stop or terminate this resource, or schedule it to "
                               "shut down outside business hours.",
        })

    # ---- Rule 2: Oversized instances ----
    oversized_mask = (
        df["instance_type"].apply(_is_large_instance)
        & (df["avg_cpu_utilization"].fillna(100) < OVERSIZED_CPU_THRESHOLD)
        & ~idle_mask  # don't double-report idle ones
    )
    for _, row in df[oversized_mask].iterrows():
        findings.append({
            "resource_id": row["resource_id"],
            "service": row["service"],
            "instance_type": _clean_instance_type(row.get("instance_type")),
            "issue": "Oversized instance",
            "detail": f"{row['instance_type']} averaging only "
                      f"{row['avg_cpu_utilization']:.1f}% CPU -- likely over-provisioned.",
            "monthly_cost": round(float(row["cost"]), 2),
            "estimated_monthly_savings": round(float(row["cost"]) * 0.4, 2),
            "severity": "medium",
            "recommendation": "Downgrade to a smaller instance type or enable "
                               "auto-scaling to match real demand.",
        })

    # ---- Rule 3: Inefficient storage ----
    storage_df = df[df["storage_gb"].fillna(0) > 0].copy()
    if not storage_df.empty:
        storage_df["cost_per_gb"] = storage_df["cost"] / storage_df["storage_gb"].replace(0, np.nan)
        fleet_median = storage_df["cost_per_gb"].median()
        if pd.notna(fleet_median) and fleet_median > 0:
            expensive_storage = storage_df[storage_df["cost_per_gb"] > fleet_median * 2]
            for _, row in expensive_storage.iterrows():
                findings.append({
                    "resource_id": row["resource_id"],
                    "service": row["service"],
                    "instance_type": _clean_instance_type(row.get("instance_type")),
                    "issue": "Inefficient storage tier",
                    "detail": f"Cost per GB (${row['cost_per_gb']:.3f}) is over 2x the "
                              f"fleet median (${fleet_median:.3f}) -- likely on a premium tier "
                              f"that isn't needed.",
                    "monthly_cost": round(float(row["cost"]), 2),
                    "estimated_monthly_savings": round(float(row["cost"]) * 0.3, 2),
                    "severity": "low",
                    "recommendation": "Move to a cheaper storage tier (e.g. S3 Infrequent "
                                       "Access / cold HDD) or set up lifecycle rules.",
                })

    # ---- Layer 2: Isolation Forest anomaly detection ----
    feature_df = df[["usage_hours", "avg_cpu_utilization", "cost"]].fillna(0)
    if len(feature_df) >= 5:
        model = IsolationForest(contamination=0.1, random_state=42)
        feature_df = feature_df.copy()
        # Normalize cost by usage to surface "expensive for what it does" resources
        feature_df["cost_per_hour"] = df["cost"] / df["usage_hours"].replace(0, np.nan).fillna(1)
        preds = model.fit_predict(feature_df.fillna(0))
        anomaly_idx = df.index[preds == -1]

        already_flagged = {f["resource_id"] for f in findings}
        for idx in anomaly_idx:
            row = df.loc[idx]
            if row["resource_id"] in already_flagged:
                continue
            findings.append({
                "resource_id": row["resource_id"],
                "service": row["service"],
                "instance_type": _clean_instance_type(row.get("instance_type")),
                "issue": "Anomalous cost pattern",
                "detail": "ML anomaly detector flagged this resource's cost as statistically "
                          "unusual relative to its usage hours and CPU utilization.",
                "monthly_cost": round(float(row["cost"]), 2),
                "estimated_monthly_savings": round(float(row["cost"]) * 0.2, 2),
                "severity": "medium",
                "recommendation": "Investigate this resource manually -- its cost-to-usage "
                                   "ratio doesn't match the rest of the fleet.",
            })

    findings.sort(key=lambda f: f["estimated_monthly_savings"], reverse=True)
    return findings

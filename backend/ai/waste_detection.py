"""
Waste Detection Engine — Enhanced v2.

Two layers, deliberately kept separate for clarity and explainability:

LAYER 1 — RULE ENGINE (deterministic FinOps heuristics):
  1. Idle compute           CPU < 5%, running ≥100 hrs/month
  2. Low utilization        CPU < 15%, running ≥100 hrs/month
  3. Oversized instance     Large family, CPU < 30%
  4. Dev always-on          dev/staging environment running ~24/7
  5. Missing tags           resource has no team/project tags
  6. Inefficient storage    cost/GB > 2× fleet median

LAYER 2 — ANOMALY DETECTION (IsolationForest):
  Flags resources whose cost is statistically unusual relative to their
  usage pattern — catches anomalies the rules miss.
"""
from typing import List, Dict, Optional
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

LARGE_INSTANCE_HINTS = ["xlarge", "2xlarge", "4xlarge", "8xlarge", "large"]

IDLE_CPU_THRESHOLD       = 5.0
LOW_UTIL_CPU_THRESHOLD   = 15.0
OVERSIZED_CPU_THRESHOLD  = 30.0
IDLE_HOURS_THRESHOLD     = 100   # hrs/month to count as "always on"


def _is_large_instance(instance_type) -> bool:
    if not isinstance(instance_type, str) or not instance_type:
        return False
    return any(h in instance_type.lower() for h in LARGE_INSTANCE_HINTS)


def _safe_str(val) -> Optional[str]:
    if isinstance(val, str):
        return val or None
    return None


def _missing_tags(row: pd.Series) -> bool:
    """Returns True if key cost-allocation tags (team + project) are both missing."""
    team = _safe_str(row.get("team"))
    project = _safe_str(row.get("project"))
    return (not team) and (not project)


def _is_dev_env(row: pd.Series) -> bool:
    env = _safe_str(row.get("environment")) or ""
    return env.lower() in ("development", "dev", "staging", "test", "sandbox")


def _savings_pct(savings: float, monthly_cost: float) -> float:
    if monthly_cost <= 0:
        return 0.0
    return round(savings / monthly_cost * 100, 1)


def _make_finding(
    row: pd.Series,
    issue: str,
    detail: str,
    recommendation: str,
    savings_factor: float,
    severity: str,
    confidence: str,
) -> Dict:
    monthly_cost = round(float(row["cost"]), 2)
    savings = round(monthly_cost * savings_factor, 2)
    return {
        "resource_id":               row["resource_id"],
        "resource_name":             _safe_str(row.get("resource_name")),
        "provider":                  _safe_str(row.get("provider")),
        "service":                   row["service"],
        "region":                    _safe_str(row.get("region")),
        "environment":               _safe_str(row.get("environment")),
        "team":                      _safe_str(row.get("team")),
        "instance_type":             _safe_str(row.get("instance_type")),
        "issue":                     issue,
        "severity":                  severity,
        "monthly_cost":              monthly_cost,
        "estimated_monthly_savings": savings,
        "savings_percentage":        _savings_pct(savings, monthly_cost),
        "detail":                    detail,
        "recommendation":            recommendation,
        "confidence":                confidence,
    }


def detect_waste(df: pd.DataFrame) -> List[Dict]:
    """
    df columns expected (per-resource aggregates):
      resource_id, service, instance_type, provider, region, environment,
      team, resource_name, usage_hours, avg_cpu_utilization, storage_gb, cost
    All optional columns may be absent/None.
    """
    findings: List[Dict] = []
    flagged_ids: set = set()

    if df.empty:
        return findings

    # ── Rule 1: Idle compute ─────────────────────────────────────────────────
    idle_mask = (
        (df["avg_cpu_utilization"].fillna(100) < IDLE_CPU_THRESHOLD)
        & (df["usage_hours"].fillna(0) >= IDLE_HOURS_THRESHOLD)
    )
    for _, row in df[idle_mask].iterrows():
        cpu = row["avg_cpu_utilization"]
        hrs = row["usage_hours"]
        f = _make_finding(
            row,
            issue="Idle resource",
            detail=f"Running {hrs:.0f} hrs with only {cpu:.1f}% avg CPU. "
                   f"Resource is consuming budget while providing near-zero value.",
            recommendation=(
                "Stop or terminate this resource, or schedule automated shutdown "
                "outside business hours using instance scheduling."
            ),
            savings_factor=0.9,
            severity="high",
            confidence="high",
        )
        findings.append(f)
        flagged_ids.add(row["resource_id"])

    # ── Rule 2: Low utilization (not idle but still underused) ───────────────
    low_util_mask = (
        (df["avg_cpu_utilization"].fillna(100) >= IDLE_CPU_THRESHOLD)
        & (df["avg_cpu_utilization"].fillna(100) < LOW_UTIL_CPU_THRESHOLD)
        & (df["usage_hours"].fillna(0) >= IDLE_HOURS_THRESHOLD)
        & ~idle_mask
    )
    for _, row in df[low_util_mask].iterrows():
        if row["resource_id"] in flagged_ids:
            continue
        cpu = row["avg_cpu_utilization"]
        f = _make_finding(
            row,
            issue="Low utilization",
            detail=f"CPU averaging only {cpu:.1f}% — significantly below healthy utilization (>30%).",
            recommendation=(
                "Review workload requirements and consider rightsizing to a smaller instance type, "
                "or consolidating workloads across fewer instances."
            ),
            savings_factor=0.5,
            severity="medium",
            confidence="high",
        )
        findings.append(f)
        flagged_ids.add(row["resource_id"])

    # ── Rule 3: Oversized instances ──────────────────────────────────────────
    oversized_mask = (
        df["instance_type"].apply(_is_large_instance)
        & (df["avg_cpu_utilization"].fillna(100) < OVERSIZED_CPU_THRESHOLD)
        & ~idle_mask
        & ~low_util_mask
    )
    for _, row in df[oversized_mask].iterrows():
        if row["resource_id"] in flagged_ids:
            continue
        cpu = row["avg_cpu_utilization"]
        inst = _safe_str(row.get("instance_type")) or "instance"
        # Suggest one tier down
        smaller = inst.replace("2xlarge", "xlarge").replace("xlarge", "large").replace("4xlarge", "2xlarge").replace("8xlarge", "4xlarge")
        f = _make_finding(
            row,
            issue="Oversized instance",
            detail=f"{inst} averaging only {cpu:.1f}% CPU — over-provisioned for the workload.",
            recommendation=(
                f"Consider moving from {inst} to {smaller} to better match actual usage. "
                "Enable auto-scaling to handle peak demand elastically."
            ),
            savings_factor=0.4,
            severity="medium",
            confidence="medium",
        )
        findings.append(f)
        flagged_ids.add(row["resource_id"])

    # ── Rule 4: Dev/staging resources running 24/7 ──────────────────────────
    dev_always_on_mask = (
        df.apply(_is_dev_env, axis=1)
        & (df["usage_hours"].fillna(0) >= 20 * 30)  # ~600 hrs/month → near 24/7
        & (df["avg_cpu_utilization"].fillna(0) < 30)
    )
    for _, row in df[dev_always_on_mask].iterrows():
        if row["resource_id"] in flagged_ids:
            continue
        env = _safe_str(row.get("environment")) or "dev"
        f = _make_finding(
            row,
            issue="Dev/staging resource running 24/7",
            detail=f"{env.capitalize()} environment resource running continuously "
                   f"({row['usage_hours']:.0f} hrs) with only {row['avg_cpu_utilization']:.1f}% CPU. "
                   f"Dev resources rarely need to run overnight or on weekends.",
            recommendation=(
                "Schedule this resource to stop after business hours (e.g. 20:00–08:00 Mon–Fri) "
                "and over weekends. This alone typically saves 60–70% of the cost."
            ),
            savings_factor=0.6,
            severity="medium",
            confidence="high",
        )
        findings.append(f)
        flagged_ids.add(row["resource_id"])

    # ── Rule 5: Resources missing cost-allocation tags ───────────────────────
    missing_tag_mask = df.apply(_missing_tags, axis=1)
    # Only flag expensive untagged resources (top 30% by cost)
    cost_threshold = df["cost"].quantile(0.70) if len(df) > 5 else 0
    expensive_untagged = (
        missing_tag_mask
        & (df["cost"] >= max(cost_threshold, 10))  # at least $10/period
    )
    for _, row in df[expensive_untagged].iterrows():
        if row["resource_id"] in flagged_ids:
            continue
        f = _make_finding(
            row,
            issue="Missing cost-allocation tags",
            detail=f"Resource has no team or project tags. ${row['cost']:.2f} in spend "
                   f"cannot be attributed to any team or initiative.",
            recommendation=(
                "Add 'team', 'project', and 'environment' tags to enable accurate "
                "cost allocation, chargeback reporting, and FinOps score improvement."
            ),
            savings_factor=0.0,   # Tagging doesn't reduce cost directly
            severity="low",
            confidence="high",
        )
        # Override savings to a small nudge value so it sorts reasonably
        f["estimated_monthly_savings"] = round(float(row["cost"]) * 0.05, 2)
        f["savings_percentage"] = 5.0
        findings.append(f)
        flagged_ids.add(row["resource_id"])

    # ── Rule 6: Inefficient storage ──────────────────────────────────────────
    storage_df = df[df["storage_gb"].fillna(0) > 0].copy()
    if not storage_df.empty:
        storage_df["cost_per_gb"] = (
            storage_df["cost"] / storage_df["storage_gb"].replace(0, np.nan)
        )
        fleet_median = storage_df["cost_per_gb"].median()
        if pd.notna(fleet_median) and fleet_median > 0:
            expensive_storage = storage_df[storage_df["cost_per_gb"] > fleet_median * 2]
            for _, row in expensive_storage.iterrows():
                if row["resource_id"] in flagged_ids:
                    continue
                f = _make_finding(
                    row,
                    issue="Inefficient storage tier",
                    detail=(
                        f"Cost/GB (${row['cost_per_gb']:.3f}) is {row['cost_per_gb']/fleet_median:.1f}× "
                        f"the fleet median (${fleet_median:.3f}). Likely on a premium tier."
                    ),
                    recommendation=(
                        "Move infrequently accessed data to a lower-cost tier "
                        "(e.g. S3 Infrequent Access, Azure Cool, GCS Nearline) "
                        "and enable lifecycle policies for automatic tiering."
                    ),
                    savings_factor=0.3,
                    severity="low",
                    confidence="medium",
                )
                findings.append(f)
                flagged_ids.add(row["resource_id"])

    # ── Layer 2: Isolation Forest anomaly detection ──────────────────────────
    feature_df = df[["usage_hours", "avg_cpu_utilization", "cost"]].fillna(0).copy()
    if len(feature_df) >= 5:
        feature_df["cost_per_hour"] = (
            df["cost"] / df["usage_hours"].replace(0, np.nan).fillna(1)
        )
        model = IsolationForest(contamination=0.10, random_state=42)
        preds = model.fit_predict(feature_df.fillna(0))
        anomaly_idx = df.index[preds == -1]

        for idx in anomaly_idx:
            row = df.loc[idx]
            if row["resource_id"] in flagged_ids:
                continue
            f = _make_finding(
                row,
                issue="Anomalous cost pattern",
                detail=(
                    "ML anomaly detector (Isolation Forest) flagged this resource's "
                    "cost as statistically unusual relative to its usage hours and CPU. "
                    "Its cost-to-usage ratio is an outlier compared to the rest of the fleet."
                ),
                recommendation=(
                    "Investigate manually — check for unexpected usage spikes, "
                    "data transfer charges, or licensing costs that don't match the workload."
                ),
                savings_factor=0.2,
                severity="medium",
                confidence="medium",
            )
            findings.append(f)
            flagged_ids.add(row["resource_id"])

    # Sort by estimated savings (highest first), then severity
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    findings.sort(
        key=lambda f: (
            -f["estimated_monthly_savings"],
            severity_order.get(f["severity"], 99),
        )
    )
    return findings

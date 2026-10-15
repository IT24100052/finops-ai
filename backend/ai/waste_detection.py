"""
Waste Detection Engine — Enhanced v2.

Two layers, deliberately kept separate for clarity and explainability:

LAYER 1 — RULE ENGINE (deterministic FinOps heuristics):
  1. Idle compute           CPU < 5%, running >= 100 hrs/period
  2. Low utilization        CPU < 15%, running >= 100 hrs/period
  3. Oversized instance     Large family, CPU < 30%
  4. Dev always-on          dev/staging environment running ~24/7 with low CPU
  5. Missing tags           resource has no team/project tags (governance recommendation, $0 direct savings)
  6. Inefficient storage    cost/GB > 2x fleet median

LAYER 2 — ANOMALY DETECTION (IsolationForest):
  Flags resources whose cost is statistically unusual relative to their
  usage pattern — catches anomalies the rules miss. Only runs on verified observations.
"""
from typing import List, Dict, Optional, Tuple, Any
import datetime
import re
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

LARGE_INSTANCE_HINTS = ["xlarge", "2xlarge", "4xlarge", "8xlarge", "large"]

IDLE_CPU_THRESHOLD       = 5.0
LOW_UTIL_CPU_THRESHOLD   = 15.0
OVERSIZED_CPU_THRESHOLD  = 30.0
IDLE_HOURS_THRESHOLD     = 100.0   # hrs to count as active compute


def _is_large_instance(instance_type) -> bool:
    if not isinstance(instance_type, str) or not instance_type:
        return False
    return any(h in instance_type.lower() for h in LARGE_INSTANCE_HINTS)


def _safe_str(val) -> Optional[str]:
    if isinstance(val, str):
        s = val.strip()
        return s if s else None
    return None


def _missing_tags(row: pd.Series) -> bool:
    """Returns True if key cost-allocation tags (team + project) are both missing."""
    team = _safe_str(row.get("team"))
    project = _safe_str(row.get("project"))
    return (not team) and (not project)


def _is_dev_env(row: pd.Series) -> bool:
    env = _safe_str(row.get("environment")) or ""
    return env.lower() in ("development", "dev", "staging", "test", "sandbox")


def _savings_pct(savings: float, cost: float) -> float:
    if cost <= 0:
        return 0.0
    return round(savings / cost * 100.0, 1)


def _detect_period_metadata(df: pd.DataFrame) -> Tuple[bool, str]:
    """
    Determines whether df reliably represents a single monthly billing period or an observed period.
    Never infers monthly period solely from first-to-last dates spanning 28-31 days.
    """
    if df.empty:
        return False, "unknown period"

    # 1. Check explicit billing_period_start and billing_period_end columns
    if "billing_period_start" in df.columns and "billing_period_end" in df.columns:
        bp_s = pd.to_datetime(df["billing_period_start"], errors="coerce").dropna()
        bp_e = pd.to_datetime(df["billing_period_end"], errors="coerce").dropna()
        if not bp_s.empty and not bp_e.empty and bp_s.nunique() == 1 and bp_e.nunique() == 1:
            s_date = bp_s.iloc[0].date()
            e_date = bp_e.iloc[0].date()
            if s_date.day == 1:
                # Same calendar month (e.g. 2026-06-01 to 2026-06-30)
                if s_date.year == e_date.year and s_date.month == e_date.month:
                    next_day = e_date + datetime.timedelta(days=1)
                    if next_day.day == 1:
                        return True, f"monthly ({s_date.strftime('%B %Y')})"
                # 1st of next month boundary (e.g. 2026-06-01 to 2026-07-01)
                elif (e_date.year * 12 + e_date.month) - (s_date.year * 12 + s_date.month) == 1 and e_date.day == 1:
                    return True, f"monthly ({s_date.strftime('%B %Y')})"

    # 2. Check date column
    if "date" in df.columns:
        dates = pd.to_datetime(df["date"], errors="coerce").dropna()
        if not dates.empty:
            min_d = dates.min().date()
            max_d = dates.max().date()
            # Verified monthly ONLY if records start on day 1 and end on the exact last day of the same month
            if min_d.year == max_d.year and min_d.month == max_d.month and min_d.day == 1:
                next_day = max_d + datetime.timedelta(days=1)
                if next_day.day == 1:
                    return True, f"monthly ({min_d.strftime('%B %Y')})"

            days_count = int(dates.dt.date.nunique())
            if min_d == max_d:
                return False, f"single-day ({min_d})"
            return False, f"observed date range ({min_d} to {max_d}, {days_count} active days)"

    # No date metadata available (e.g. pre-aggregated per-resource DataFrame)
    return False, "observed period"


_VALID_MONTH_NAMES = {
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december"
}

_RE_MONTHLY = re.compile(r"^monthly\s*\(([a-z]+)\s+(\d{4})\)$", re.IGNORECASE)
_RE_DATE_RANGE = re.compile(
    r"^observed date range\s*\(([0-9]{4}-[0-9]{2}-[0-9]{2})\s+to\s+([0-9]{4}-[0-9]{2}-[0-9]{2}),\s*(\d+)\s+active\s+days\)$",
    re.IGNORECASE
)
_RE_SINGLE_DAY = re.compile(r"^single-day\s*\(([0-9]{4}-[0-9]{2}-[0-9]{2})\)$", re.IGNORECASE)


def _is_demonstrably_comparable_period(is_monthly: bool, period_label: str) -> bool:
    """
    Checks if a period has demonstrable, verified boundaries.
    Strictly validates month/year or parsed ISO date ranges/single-day dates.
    Generic, malformed, unanchored, or prefix-only labels return False.
    """
    if not period_label or not isinstance(period_label, str):
        return False
    norm = period_label.strip()
    if not norm:
        return False
    lower_norm = norm.lower()
    if lower_norm in ("observed period", "unknown period", "none", "unspecified period"):
        return False

    if is_monthly:
        m = _RE_MONTHLY.match(norm)
        if not m:
            return False
        month_name = m.group(1).lower()
        year_str = m.group(2)
        if month_name not in _VALID_MONTH_NAMES:
            return False
        try:
            year = int(year_str)
            if year < 1970 or year > 2100:
                return False
        except (ValueError, TypeError):
            return False
        return True

    # When is_monthly is False, must be a strictly validated date range or single-day date
    m_range = _RE_DATE_RANGE.match(norm)
    if m_range:
        start_str = m_range.group(1)
        end_str = m_range.group(2)
        try:
            active_days = int(m_range.group(3))
            d_start = datetime.date.fromisoformat(start_str)
            d_end = datetime.date.fromisoformat(end_str)
        except (ValueError, TypeError):
            return False

        if d_end < d_start:
            return False
        calendar_span = (d_end - d_start).days + 1
        if active_days <= 0 or active_days > calendar_span:
            return False
        return True

    m_day = _RE_SINGLE_DAY.match(norm)
    if m_day:
        day_str = m_day.group(1)
        try:
            _ = datetime.date.fromisoformat(day_str)
            return True
        except (ValueError, TypeError):
            return False

    return False


def aggregate_savings_conservatively(
    findings: List[Dict],
    resource_cost_map: Optional[Dict[str, float]] = None,
) -> Tuple[float, float]:
    """
    Computes (conservative_savings, gross_savings) across findings.

    Conservative aggregation strategy:
    - Multiple recommendations for the same resource are non-additive (overlapping).
    - For each identified resource, achievable savings is capped at the maximum individual recommendation,
      and further capped at the resource's known cost for the period (from resource_cost_map or finding).
    - Findings without a reliable resource ID (None, NaN, blank, whitespace, 'unknown', etc.) are given
      independent aggregation keys so they do not artificially collapse into each other.
    - Achievable savings for an unidentified finding is capped at its own period_cost (or monthly_cost).
    - Non-finite (inf, nan) and negative values are excluded (treated as 0.0).
    - Gross savings is the sum of all valid finding savings (for transparency).
    """
    if not findings:
        return 0.0, 0.0

    by_resource: Dict[str, Dict[str, Any]] = {}
    gross_savings = 0.0

    for idx, f in enumerate(findings):
        if not isinstance(f, dict):
            continue

        # Extract and validate savings amount
        val = f.get("estimated_monthly_savings")
        if val is None:
            val = f.get("estimated_savings", 0.0)
        try:
            amt = float(val) if val is not None else 0.0
            if not np.isfinite(amt) or amt < 0.0:
                amt = 0.0
        except (ValueError, TypeError):
            amt = 0.0

        gross_savings += amt

        # Extract and validate finding-level cost cap
        p_cost = f.get("period_cost")
        if p_cost is None:
            p_cost = f.get("monthly_cost")
        finding_cost_cap: Optional[float] = None
        if p_cost is not None:
            try:
                c = float(p_cost)
                if np.isfinite(c) and c >= 0.0:
                    finding_cost_cap = c
            except (ValueError, TypeError):
                finding_cost_cap = None

        # Determine reliable resource identity
        rid_raw = f.get("resource_id")
        is_reliable = False
        clean_rid = ""

        if rid_raw is not None:
            if isinstance(rid_raw, float) and (np.isnan(rid_raw) or not np.isfinite(rid_raw)):
                is_reliable = False
            else:
                s = str(rid_raw).strip()
                if s and s.lower() not in ("unknown", "none", "nan", "null"):
                    is_reliable = True
                    clean_rid = s

        if is_reliable:
            group_key = clean_rid
        else:
            # Independent aggregation key per unidentified finding
            group_key = f"__unidentified_{idx}__"

        if group_key not in by_resource:
            by_resource[group_key] = {
                "amounts": [],
                "finding_caps": [],
                "is_reliable": is_reliable,
                "clean_rid": clean_rid,
            }
        by_resource[group_key]["amounts"].append(amt)
        if finding_cost_cap is not None:
            by_resource[group_key]["finding_caps"].append(finding_cost_cap)

    conservative_savings = 0.0
    for group_key, data in by_resource.items():
        amounts = data["amounts"]
        finding_caps = data["finding_caps"]
        is_reliable = data["is_reliable"]
        clean_rid = data["clean_rid"]

        res_max = max(amounts) if amounts else 0.0

        cost_cap: Optional[float] = None
        if is_reliable and resource_cost_map and clean_rid in resource_cost_map:
            try:
                m_cap = float(resource_cost_map[clean_rid])
                if np.isfinite(m_cap) and m_cap >= 0.0:
                    cost_cap = m_cap
            except (ValueError, TypeError):
                pass

        if cost_cap is None and finding_caps:
            cost_cap = max(finding_caps)

        if cost_cap is not None:
            res_max = min(res_max, cost_cap)

        conservative_savings += res_max

    return round(conservative_savings, 2), round(gross_savings, 2)



def _make_finding(
    row: pd.Series,
    issue: str,
    detail: str,
    recommendation: str,
    savings_factor: float,
    severity: str,
    confidence: str,
    period_label: str = "observed period",
    is_verified_monthly: bool = False,
) -> Dict:
    raw_cost = pd.to_numeric(row.get("cost"), errors="coerce")
    period_cost = round(float(raw_cost), 2) if pd.notna(raw_cost) and np.isfinite(raw_cost) and raw_cost >= 0 else 0.0
    savings = round(period_cost * savings_factor, 2)

    # Clearly label the value as an observed-period estimate if not verified monthly
    if not is_verified_monthly:
        detail_annotated = f"{detail} (Observed-period estimate across {period_label}; unverified monthly)."
    else:
        detail_annotated = f"{detail} (Verified monthly for {period_label})."

    return {
        "resource_id":               str(row.get("resource_id", "unknown")),
        "resource_name":             _safe_str(row.get("resource_name")),
        "provider":                  _safe_str(row.get("provider")),
        "service":                   str(row.get("service", "unknown")),
        "region":                    _safe_str(row.get("region")),
        "environment":               _safe_str(row.get("environment")),
        "team":                      _safe_str(row.get("team")),
        "instance_type":             _safe_str(row.get("instance_type")),
        "issue":                     issue,
        "severity":                  severity,
        "monthly_cost":              period_cost,          # Preserved for API schema compatibility
        "estimated_monthly_savings": savings,              # Preserved for API schema compatibility
        "estimated_savings":         savings,
        "period_cost":               period_cost,
        "savings_period":            period_label,
        "is_verified_monthly":       is_verified_monthly,
        "savings_percentage":        _savings_pct(savings, period_cost),
        "detail":                    detail_annotated,
        "recommendation":            recommendation,
        "confidence":                confidence,
    }


def detect_waste(
    df: pd.DataFrame,
    period_label: Optional[str] = None,
    is_verified_monthly: Optional[bool] = None,
) -> List[Dict]:
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

    # Determine period metadata if not explicitly provided
    if period_label is None or is_verified_monthly is None:
        detected_is_monthly, detected_label = _detect_period_metadata(df)
        if period_label is None:
            period_label = detected_label
        if is_verified_monthly is None:
            is_verified_monthly = detected_is_monthly

    # Clean numeric columns. Preserve missingness (never coerce missing/invalid to verified 0.0)
    cpu_raw = (
        pd.to_numeric(df["avg_cpu_utilization"], errors="coerce")
        if "avg_cpu_utilization" in df.columns
        else pd.Series(np.nan, index=df.index)
    )
    cpu_num = cpu_raw.where(cpu_raw.notna() & np.isfinite(cpu_raw) & (cpu_raw >= 0.0) & (cpu_raw <= 100.0))

    usage_raw = (
        pd.to_numeric(df["usage_hours"], errors="coerce")
        if "usage_hours" in df.columns
        else pd.Series(np.nan, index=df.index)
    )
    usage_num = usage_raw.where(usage_raw.notna() & np.isfinite(usage_raw) & (usage_raw >= 0.0))

    cost_raw = (
        pd.to_numeric(df["cost"], errors="coerce")
        if "cost" in df.columns
        else pd.Series(np.nan, index=df.index)
    )
    cost_num = cost_raw.where(cost_raw.notna() & np.isfinite(cost_raw) & (cost_raw >= 0.0))

    storage_raw = (
        pd.to_numeric(df["storage_gb"], errors="coerce")
        if "storage_gb" in df.columns
        else pd.Series(np.nan, index=df.index)
    )
    storage_num = storage_raw.where(storage_raw.notna() & np.isfinite(storage_raw) & (storage_raw >= 0.0))

    instance_series = (
        df["instance_type"]
        if "instance_type" in df.columns
        else pd.Series(None, index=df.index)
    )

    # ── Rule 1: Idle compute ─────────────────────────────────────────────────
    # Requires genuine CPU observation AND genuine usage-hour measurement AND verified cost
    idle_mask = (
        cpu_num.notna()
        & (cpu_num < IDLE_CPU_THRESHOLD)
        & usage_num.notna()
        & (usage_num >= IDLE_HOURS_THRESHOLD)
        & cost_num.notna()
    )
    for _, row in df[idle_mask].iterrows():
        cpu = cpu_num.loc[row.name]
        hrs = usage_num.loc[row.name]
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
            period_label=period_label,
            is_verified_monthly=is_verified_monthly,
        )
        findings.append(f)
        flagged_ids.add(str(row.get("resource_id", "")))

    # ── Rule 2: Low utilization (not idle but still underused) ───────────────
    # Requires genuine CPU observation AND genuine usage-hour measurement AND verified cost
    low_util_mask = (
        cpu_num.notna()
        & (cpu_num >= IDLE_CPU_THRESHOLD)
        & (cpu_num < LOW_UTIL_CPU_THRESHOLD)
        & usage_num.notna()
        & (usage_num >= IDLE_HOURS_THRESHOLD)
        & cost_num.notna()
        & ~idle_mask
    )
    for _, row in df[low_util_mask].iterrows():
        rid = str(row.get("resource_id", ""))
        if rid in flagged_ids:
            continue
        cpu = cpu_num.loc[row.name]
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
            period_label=period_label,
            is_verified_monthly=is_verified_monthly,
        )
        findings.append(f)
        flagged_ids.add(rid)

    # ── Rule 3: Oversized instances ──────────────────────────────────────────
    # Requires genuine CPU observation AND verified cost
    oversized_mask = (
        instance_series.apply(_is_large_instance)
        & cpu_num.notna()
        & (cpu_num < OVERSIZED_CPU_THRESHOLD)
        & cost_num.notna()
        & ~idle_mask
        & ~low_util_mask
    )
    for _, row in df[oversized_mask].iterrows():
        rid = str(row.get("resource_id", ""))
        if rid in flagged_ids:
            continue
        cpu = cpu_num.loc[row.name]
        inst = _safe_str(row.get("instance_type")) or "instance"
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
            period_label=period_label,
            is_verified_monthly=is_verified_monthly,
        )
        findings.append(f)
        flagged_ids.add(rid)

    # ── Rule 4: Dev/staging resources running 24/7 ──────────────────────────
    # Requires genuine CPU observation AND genuine usage-hour measurement AND verified cost
    dev_always_on_mask = (
        df.apply(_is_dev_env, axis=1)
        & usage_num.notna()
        & (usage_num >= 20 * 30)  # ~600 hrs -> near 24/7
        & cpu_num.notna()
        & (cpu_num < 30)
        & cost_num.notna()
    )
    for _, row in df[dev_always_on_mask].iterrows():
        rid = str(row.get("resource_id", ""))
        if rid in flagged_ids:
            continue
        env = _safe_str(row.get("environment")) or "dev"
        f = _make_finding(
            row,
            issue="Dev/staging resource running 24/7",
            detail=f"{env.capitalize()} environment resource running continuously "
                   f"({usage_num.loc[row.name]:.0f} hrs) with only {cpu_num.loc[row.name]:.1f}% CPU. "
                   f"Dev resources rarely need to run overnight or on weekends.",
            recommendation=(
                "Schedule this resource to stop after business hours (e.g. 20:00–08:00 Mon–Fri) "
                "and over weekends. This alone typically saves 60–70% of the cost."
            ),
            savings_factor=0.6,
            severity="medium",
            confidence="high",
            period_label=period_label,
            is_verified_monthly=is_verified_monthly,
        )
        findings.append(f)
        flagged_ids.add(rid)

    # ── Rule 5: Resources missing cost-allocation tags ───────────────────────
    # Missing tags is a governance recommendation, NOT verified monetary savings
    missing_tag_mask = df.apply(_missing_tags, axis=1)
    valid_costs = cost_num.dropna()
    cost_threshold = valid_costs.quantile(0.70) if len(valid_costs) > 5 else 0
    expensive_untagged = (
        missing_tag_mask
        & cost_num.notna()
        & (cost_num >= max(cost_threshold, 10.0))
    )
    for _, row in df[expensive_untagged].iterrows():
        rid = str(row.get("resource_id", ""))
        # Rule 5 is governance only ($0 direct savings); do not suppress
        # untagged resources even if they already have operational findings
        c_val = float(cost_num.loc[row.name])
        f = _make_finding(
            row,
            issue="Missing cost-allocation tags",
            detail=f"Resource has no team or project tags. ${c_val:.2f} in spend "
                   f"cannot be attributed to any team or initiative.",
            recommendation=(
                "Add 'team', 'project', and 'environment' tags to enable accurate "
                "cost allocation, chargeback reporting, and FinOps score improvement."
            ),
            savings_factor=0.0,   # Governance only; zero direct monetary savings
            severity="low",
            confidence="high",
            period_label=period_label,
            is_verified_monthly=is_verified_monthly,
        )
        findings.append(f)
        flagged_ids.add(rid)

    # ── Rule 6: Inefficient storage ──────────────────────────────────────────
    storage_mask = storage_num.notna() & (storage_num > 0) & cost_num.notna() & (cost_num > 0)
    storage_df = df[storage_mask].copy()
    if not storage_df.empty:
        valid_s = storage_num[storage_mask]
        valid_c = cost_num[storage_mask]
        cost_per_gb = valid_c / valid_s
        fleet_median = cost_per_gb.median()
        if pd.notna(fleet_median) and fleet_median > 0:
            expensive_storage_idx = cost_per_gb[cost_per_gb > fleet_median * 2].index
            for idx in expensive_storage_idx:
                row = df.loc[idx]
                rid = str(row.get("resource_id", ""))
                if rid in flagged_ids:
                    continue
                c_pgb = float(cost_per_gb.loc[idx])
                f = _make_finding(
                    row,
                    issue="Inefficient storage tier",
                    detail=(
                        f"Cost/GB (${c_pgb:.3f}) is {c_pgb/fleet_median:.1f}x "
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
                    period_label=period_label,
                    is_verified_monthly=is_verified_monthly,
                )
                findings.append(f)
                flagged_ids.add(rid)

    # ── Layer 2: Isolation Forest anomaly detection ──────────────────────────
    # Only run on records with valid, measured usage, CPU, and cost (no imputed zeros)
    valid_feature_mask = (
        usage_num.notna()
        & cpu_num.notna()
        & cost_num.notna()
        & (cost_num >= 0)
    )
    if valid_feature_mask.sum() >= 5:
        feature_df = pd.DataFrame({
            "usage_hours": usage_num[valid_feature_mask],
            "avg_cpu_utilization": cpu_num[valid_feature_mask],
            "cost": cost_num[valid_feature_mask],
        })
        feature_df["cost_per_hour"] = (
            feature_df["cost"] / feature_df["usage_hours"].replace(0, np.nan).fillna(1)
        )
        model = IsolationForest(contamination=0.10, random_state=42)
        preds = model.fit_predict(feature_df)
        anomaly_idx = feature_df.index[preds == -1]

        for idx in anomaly_idx:
            row = df.loc[idx]
            rid = str(row.get("resource_id", ""))
            if rid in flagged_ids:
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
                period_label=period_label,
                is_verified_monthly=is_verified_monthly,
            )
            findings.append(f)
            flagged_ids.add(rid)

    # Sort by estimated savings (highest first), then severity
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    findings.sort(
        key=lambda f: (
            -f["estimated_monthly_savings"],
            severity_order.get(f["severity"], 99),
        )
    )
    return findings

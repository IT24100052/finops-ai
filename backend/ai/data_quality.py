"""
Data Quality Engine.

Analyses uploaded billing data for quality issues and computes
a Data Quality Score (0–100). Issues reduce the score.

Checks:
  - Missing required-ish fields (provider, region, environment, team)
  - Invalid CPU values (outside 0–100)
  - Invalid/negative costs
  - Duplicate records (same date+service+resource_id)
  - Empty tags / missing cost-allocation metadata
  - Tagging coverage (team + project)
"""
from typing import List, Dict
import pandas as pd


def analyse_data_quality(df: pd.DataFrame) -> Dict:
    """
    df: full per-record billing DataFrame (all records for the user).
    Returns a dict matching schemas.DataQualityOut.
    """
    if df.empty:
        return {
            "score":              0.0,
            "total_records":      0,
            "valid_records":      0,
            "invalid_records":    0,
            "duplicate_records":  0,
            "missing_provider":   0,
            "missing_region":     0,
            "missing_environment": 0,
            "missing_team":       0,
            "missing_tags":       0,
            "invalid_cpu_values": 0,
            "invalid_costs":      0,
            "tagging_coverage_pct": 0.0,
            "field_issues":       [],
            "recommendations":    ["Upload billing data to see data quality metrics."],
        }

    total = len(df)
    penalty = 0.0   # accumulated penalty points (max 100)
    field_issues: List[Dict] = []
    recommendations: List[str] = []

    def _pct(n: int) -> float:
        return round(n / total * 100, 1) if total > 0 else 0.0

    def _impact(pct: float) -> str:
        if pct >= 20:
            return "high"
        elif pct >= 5:
            return "medium"
        return "low"

    # ── Duplicate records ────────────────────────────────────────────────────
    dup_cols = [c for c in ["date", "service", "resource_id"] if c in df.columns]
    if dup_cols:
        dup_mask = df.duplicated(subset=dup_cols, keep="first")
        n_dupes = int(dup_mask.sum())
    else:
        n_dupes = 0
    dup_pct = _pct(n_dupes)
    if n_dupes > 0:
        penalty += min(15.0, dup_pct * 0.5)
        recommendations.append(
            f"Remove {n_dupes} duplicate records (same date+service+resource_id) to avoid inflated cost totals."
        )

    # ── Invalid costs ────────────────────────────────────────────────────────
    invalid_cost_mask = df["cost"] < 0
    n_invalid_cost = int(invalid_cost_mask.sum())
    if n_invalid_cost > 0:
        penalty += min(20.0, _pct(n_invalid_cost) * 0.8)
        recommendations.append(
            f"Fix {n_invalid_cost} records with negative costs — these indicate data export errors."
        )

    # ── Invalid CPU values ───────────────────────────────────────────────────
    cpu_col = df["avg_cpu_utilization"].dropna() if "avg_cpu_utilization" in df.columns else pd.Series(dtype=float)
    n_invalid_cpu = int(((cpu_col < 0) | (cpu_col > 100)).sum())
    if n_invalid_cpu > 0:
        penalty += min(10.0, (n_invalid_cpu / max(len(cpu_col), 1)) * 100 * 0.3)
        field_issues.append({
            "field":        "avg_cpu_utilization",
            "missing_count": n_invalid_cpu,
            "missing_pct":  round(n_invalid_cpu / max(len(cpu_col), 1) * 100, 1),
            "impact":       "medium",
        })
        recommendations.append(
            f"Correct {n_invalid_cpu} CPU utilization values that are outside the valid 0–100% range."
        )

    # ── Missing provider ─────────────────────────────────────────────────────
    n_missing_provider = int(df["provider"].isna().sum()) if "provider" in df.columns else total
    prov_pct = _pct(n_missing_provider)
    if n_missing_provider > 0:
        penalty += min(10.0, prov_pct * 0.2)
        field_issues.append({
            "field":        "provider",
            "missing_count": n_missing_provider,
            "missing_pct":  prov_pct,
            "impact":       _impact(prov_pct),
        })
        if prov_pct > 10:
            recommendations.append(
                f"{n_missing_provider} records missing 'provider' field. Add AWS/Azure/GCP to enable multi-cloud analytics."
            )

    # ── Missing region ───────────────────────────────────────────────────────
    n_missing_region = int(df["region"].isna().sum()) if "region" in df.columns else 0
    region_pct = _pct(n_missing_region)
    if n_missing_region > 0:
        penalty += min(8.0, region_pct * 0.15)
        field_issues.append({
            "field":        "region",
            "missing_count": n_missing_region,
            "missing_pct":  region_pct,
            "impact":       _impact(region_pct),
        })
        if region_pct > 10:
            recommendations.append(
                f"{n_missing_region} records missing 'region'. Region data enables regional cost analysis and anomaly detection."
            )

    # ── Missing environment ──────────────────────────────────────────────────
    n_missing_env = int(df["environment"].isna().sum()) if "environment" in df.columns else 0
    env_pct = _pct(n_missing_env)
    if n_missing_env > 0:
        penalty += min(8.0, env_pct * 0.15)
        field_issues.append({
            "field":        "environment",
            "missing_count": n_missing_env,
            "missing_pct":  env_pct,
            "impact":       _impact(env_pct),
        })
        if env_pct > 20:
            recommendations.append(
                f"{n_missing_env} records missing 'environment'. Add production/staging/development labels for proper cost separation."
            )

    # ── Missing team ─────────────────────────────────────────────────────────
    n_missing_team = int(df["team"].isna().sum()) if "team" in df.columns else 0
    team_pct = _pct(n_missing_team)
    if n_missing_team > 0:
        penalty += min(12.0, team_pct * 0.25)
        field_issues.append({
            "field":        "team",
            "missing_count": n_missing_team,
            "missing_pct":  team_pct,
            "impact":       _impact(team_pct),
        })
        if team_pct > 10:
            recommendations.append(
                f"{n_missing_team} records missing 'team' tag. Team tagging is essential for chargeback reporting."
            )

    # ── Tagging coverage (team + project) ────────────────────────────────────
    resource_df = df.groupby("resource_id").first().reset_index()
    total_resources = len(resource_df)
    tagged = resource_df[
        resource_df.get("team", pd.Series()).notna()
        & resource_df.get("project", pd.Series()).notna()
    ]
    n_tagged = len(tagged)
    tagging_pct = round(n_tagged / total_resources * 100, 1) if total_resources > 0 else 0.0
    n_missing_tags = total_resources - n_tagged
    if n_missing_tags > 0:
        penalty += min(15.0, (n_missing_tags / total_resources) * 30)
        recommendations.append(
            f"{n_missing_tags} resources ({100 - tagging_pct:.0f}%) are missing both 'team' and 'project' tags. "
            "Untagged resources cannot be attributed to cost centers."
        )

    # ── Final score ──────────────────────────────────────────────────────────
    score = max(0.0, round(100.0 - penalty, 1))

    # Valid / invalid record counts
    invalid_records = n_invalid_cost + n_dupes
    valid_records = max(0, total - invalid_records)

    return {
        "score":               score,
        "total_records":       total,
        "valid_records":       valid_records,
        "invalid_records":     invalid_records,
        "duplicate_records":   n_dupes,
        "missing_provider":    n_missing_provider,
        "missing_region":      n_missing_region,
        "missing_environment": n_missing_env,
        "missing_team":        n_missing_team,
        "missing_tags":        n_missing_tags,
        "invalid_cpu_values":  n_invalid_cpu,
        "invalid_costs":       n_invalid_cost,
        "tagging_coverage_pct": tagging_pct,
        "field_issues":        field_issues,
        "recommendations":     recommendations if recommendations else ["Data quality looks good! Keep tagging new resources."],
    }

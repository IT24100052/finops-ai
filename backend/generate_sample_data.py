"""
FinOps AI — Enhanced Sample Data Generator v2

Generates 4,000+ rows of realistic multi-cloud billing data across:
  - 3 providers: AWS, Azure, GCP
  - 3 accounts per provider
  - Multiple regions per provider
  - 3 environments: production, staging, development
  - 5 teams: Platform, Analytics, ML, Security, DevOps
  - 6 projects
  - 120 days of history
  - ~35 resources with deliberate "personas"

Personas include:
  healthy        → normal CPU 40-70%, runs business hours
  idle           → CPU < 5%, runs 24/7
  low_util       → CPU 8-14%, runs 24/7
  oversized      → large instance, CPU 15-28%
  dev_always_on  → dev environment, near-24/7
  expensive_s3   → high cost/GB storage
  anomalous      → occasional cost spikes
  missing_tags   → no team or project

Deterministic: random.seed(42)

Run: python generate_sample_data.py
Output: sample_billing_data.csv (~4,200+ rows)
"""
import csv
import random
from datetime import date, timedelta
from typing import Optional

random.seed(42)

NUM_DAYS = 120
START_DATE = date.today() - timedelta(days=NUM_DAYS)

# ── Provider configs ─────────────────────────────────────────────────────────

PROVIDERS = {
    "AWS": {
        "accounts": ["aws-prod-001", "aws-staging-002", "aws-dev-003"],
        "regions": ["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"],
    },
    "Azure": {
        "accounts": ["azure-prod-sub", "azure-dev-sub"],
        "regions": ["eastus", "westeurope", "southeastasia"],
    },
    "GCP": {
        "accounts": ["gcp-prod-project", "gcp-ml-project"],
        "regions": ["us-central1", "europe-west1", "asia-east1"],
    },
}

# ── Resource fleet ───────────────────────────────────────────────────────────

RESOURCES = [
    # AWS Production — Healthy
    {"id": "i-prod-web-01",     "name": "Production Web Server 1",  "provider": "AWS", "account": "aws-prod-001",     "service": "EC2",  "type": "m5.large",    "persona": "healthy",      "env": "production", "team": "Platform",   "project": "Customer Portal",     "base_cost": 2.1,  "region": "us-east-1",     "res_type": "compute"},
    {"id": "i-prod-web-02",     "name": "Production Web Server 2",  "provider": "AWS", "account": "aws-prod-001",     "service": "EC2",  "type": "m5.large",    "persona": "healthy",      "env": "production", "team": "Platform",   "project": "Customer Portal",     "base_cost": 2.1,  "region": "us-east-1",     "res_type": "compute"},
    {"id": "i-prod-api-01",     "name": "API Gateway Server",       "provider": "AWS", "account": "aws-prod-001",     "service": "EC2",  "type": "m5.xlarge",   "persona": "healthy",      "env": "production", "team": "Platform",   "project": "Customer Portal",     "base_cost": 4.2,  "region": "us-east-1",     "res_type": "compute"},
    {"id": "db-prod-main",      "name": "Primary Production DB",    "provider": "AWS", "account": "aws-prod-001",     "service": "RDS",  "type": "db.r5.xlarge","persona": "healthy",      "env": "production", "team": "Platform",   "project": "Customer Portal",     "base_cost": 6.0,  "region": "us-east-1",     "res_type": "database"},
    {"id": "s3-prod-assets",    "name": "Production Assets Bucket", "provider": "AWS", "account": "aws-prod-001",     "service": "S3",   "type": None,          "persona": "healthy",      "env": "production", "team": "Platform",   "project": "Customer Portal",     "base_cost": 0.8,  "region": "us-east-1",     "res_type": "storage",  "storage_gb": 2500},

    # AWS — Idle (waste)
    {"id": "i-staging-test",    "name": "Staging Test Instance",    "provider": "AWS", "account": "aws-staging-002",  "service": "EC2",  "type": "m5.large",    "persona": "idle",         "env": "staging",    "team": "Platform",   "project": "Customer Portal",     "base_cost": 2.1,  "region": "us-east-1",     "res_type": "compute"},
    {"id": "i-old-batch-job",   "name": "Legacy Batch Processor",   "provider": "AWS", "account": "aws-prod-001",     "service": "EC2",  "type": "c5.4xlarge",  "persona": "idle",         "env": "production", "team": "Analytics",  "project": "Data Pipeline",       "base_cost": 16.0, "region": "us-west-2",     "res_type": "compute"},
    {"id": "db-legacy-archive", "name": "Legacy Archive DB",        "provider": "AWS", "account": "aws-prod-001",     "service": "RDS",  "type": "db.t3.medium","persona": "idle",         "env": "production", "team": "Analytics",  "project": "Data Pipeline",       "base_cost": 1.8,  "region": "us-east-1",     "res_type": "database"},

    # AWS — Oversized
    {"id": "i-analytics-01",    "name": "Analytics Server",         "provider": "AWS", "account": "aws-prod-001",     "service": "EC2",  "type": "m5.2xlarge",  "persona": "oversized",    "env": "production", "team": "Analytics",  "project": "Customer Analytics",  "base_cost": 8.4,  "region": "us-west-2",     "res_type": "compute"},
    {"id": "db-reporting",      "name": "Reporting Database",       "provider": "AWS", "account": "aws-prod-001",     "service": "RDS",  "type": "db.m5.large", "persona": "oversized",    "env": "production", "team": "Analytics",  "project": "Customer Analytics",  "base_cost": 3.6,  "region": "us-east-1",     "res_type": "database"},

    # AWS — Dev always on
    {"id": "i-dev-sandbox",     "name": "Developer Sandbox",        "provider": "AWS", "account": "aws-dev-003",      "service": "EC2",  "type": "t3.medium",   "persona": "dev_always_on","env": "development","team": "Platform",   "project": "Customer Portal",     "base_cost": 0.9,  "region": "us-east-1",     "res_type": "compute"},
    {"id": "i-dev-ml-test",     "name": "ML Dev Testing Node",      "provider": "AWS", "account": "aws-dev-003",      "service": "EC2",  "type": "m5.xlarge",   "persona": "dev_always_on","env": "development","team": "ML",         "project": "AI Platform",         "base_cost": 4.2,  "region": "us-west-2",     "res_type": "compute"},

    # AWS — Expensive storage
    {"id": "s3-backups",        "name": "Backup Storage Bucket",    "provider": "AWS", "account": "aws-prod-001",     "service": "S3",   "type": None,          "persona": "expensive_s3", "env": "production", "team": "Platform",   "project": "Customer Portal",     "base_cost": 3.5,  "region": "us-east-1",     "res_type": "storage",  "storage_gb": 1800},
    {"id": "s3-logs-archive",   "name": "Log Archive Bucket",       "provider": "AWS", "account": "aws-prod-001",     "service": "S3",   "type": None,          "persona": "healthy",      "env": "production", "team": "Platform",   "project": "Customer Portal",     "base_cost": 0.4,  "region": "us-east-1",     "res_type": "storage",  "storage_gb": 900},

    # AWS — Anomalous + Lambda
    {"id": "lambda-image-proc", "name": "Image Processing Lambda",  "provider": "AWS", "account": "aws-prod-001",     "service": "Lambda","type": None,         "persona": "healthy",      "env": "production", "team": "Platform",   "project": "Customer Portal",     "base_cost": 0.3,  "region": "us-east-1",     "res_type": "serverless"},
    {"id": "lambda-nightly-etl","name": "Nightly ETL Lambda",       "provider": "AWS", "account": "aws-prod-001",     "service": "Lambda","type": None,         "persona": "anomalous",    "env": "production", "team": "Analytics",  "project": "Data Pipeline",       "base_cost": 0.5,  "region": "us-east-1",     "res_type": "serverless"},

    # AWS — Missing tags (unallocated)
    {"id": "i-untagged-01",     "name": "Untagged Server A",        "provider": "AWS", "account": "aws-prod-001",     "service": "EC2",  "type": "m5.large",    "persona": "missing_tags", "env": None,         "team": None,         "project": None,                  "base_cost": 3.2,  "region": "us-east-1",     "res_type": "compute"},
    {"id": "i-untagged-02",     "name": "Untagged Server B",        "provider": "AWS", "account": "aws-dev-003",      "service": "EC2",  "type": "t3.medium",   "persona": "missing_tags", "env": None,         "team": None,         "project": None,                  "base_cost": 0.9,  "region": "us-west-2",     "res_type": "compute"},

    # Azure — Production
    {"id": "vm-prod-api",       "name": "Azure API VM",             "provider": "Azure","account": "azure-prod-sub",  "service": "VirtualMachines","type": "Standard_D4s_v3","persona": "healthy","env": "production","team": "Platform",  "project": "Customer Portal",     "base_cost": 4.8,  "region": "eastus",        "res_type": "compute"},
    {"id": "sql-prod-main",     "name": "Azure SQL Production",     "provider": "Azure","account": "azure-prod-sub",  "service": "SQLDatabase","type": None,        "persona": "healthy",      "env": "production", "team": "Platform",   "project": "Customer Portal",     "base_cost": 5.5,  "region": "eastus",        "res_type": "database"},
    {"id": "blob-prod-data",    "name": "Production Blob Storage",  "provider": "Azure","account": "azure-prod-sub",  "service": "BlobStorage","type": None,        "persona": "healthy",      "env": "production", "team": "Analytics",  "project": "Customer Analytics",  "base_cost": 1.2,  "region": "westeurope",    "res_type": "storage",  "storage_gb": 3000},

    # Azure — Idle/Oversized
    {"id": "vm-staging-old",    "name": "Old Staging VM",           "provider": "Azure","account": "azure-dev-sub",   "service": "VirtualMachines","type": "Standard_D8s_v3","persona": "idle","env": "staging",    "team": "DevOps",     "project": "Infrastructure",      "base_cost": 9.6,  "region": "eastus",        "res_type": "compute"},
    {"id": "vm-dev-build",      "name": "Build Server",             "provider": "Azure","account": "azure-dev-sub",   "service": "VirtualMachines","type": "Standard_D2s_v3","persona": "dev_always_on","env": "development","team": "DevOps","project": "Infrastructure", "base_cost": 2.4,  "region": "westeurope",    "res_type": "compute"},

    # Azure — Security team
    {"id": "vm-sec-scan",       "name": "Security Scanner",         "provider": "Azure","account": "azure-prod-sub",  "service": "VirtualMachines","type": "Standard_D4s_v3","persona": "oversized","env": "production","team": "Security","project": "Compliance",      "base_cost": 4.8,  "region": "eastus",        "res_type": "compute"},

    # GCP — Production ML
    {"id": "gce-ml-train-01",   "name": "ML Training Node",         "provider": "GCP", "account": "gcp-ml-project",  "service": "Compute Engine","type": "n2-standard-8","persona": "healthy","env": "production","team": "ML",         "project": "AI Platform",         "base_cost": 9.6,  "region": "us-central1",   "res_type": "compute"},
    {"id": "gce-ml-train-02",   "name": "ML Training Node 2",       "provider": "GCP", "account": "gcp-ml-project",  "service": "Compute Engine","type": "n2-standard-8","persona": "oversized","env": "production","team": "ML",         "project": "AI Platform",         "base_cost": 9.6,  "region": "europe-west1",  "res_type": "compute"},
    {"id": "gcs-ml-datasets",   "name": "ML Dataset Bucket",        "provider": "GCP", "account": "gcp-ml-project",  "service": "Cloud Storage","type": None,         "persona": "healthy",      "env": "production", "team": "ML",         "project": "AI Platform",         "base_cost": 1.8,  "region": "us-central1",   "res_type": "storage",  "storage_gb": 5000},
    {"id": "bq-analytics",      "name": "BigQuery Analytics",       "provider": "GCP", "account": "gcp-prod-project","service": "BigQuery","type": None,            "persona": "healthy",      "env": "production", "team": "Analytics",  "project": "Customer Analytics",  "base_cost": 2.5,  "region": "us-central1",   "res_type": "database"},

    # GCP — Idle
    {"id": "gce-dev-old-01",    "name": "Old Dev Instance",         "provider": "GCP", "account": "gcp-prod-project","service": "Compute Engine","type": "n2-standard-4","persona": "idle","env": "development","team": "ML",         "project": "AI Platform",         "base_cost": 4.8,  "region": "asia-east1",    "res_type": "compute"},

    # GCP — Low util
    {"id": "gce-low-util-api",  "name": "Low Util API Server",      "provider": "GCP", "account": "gcp-prod-project","service": "Compute Engine","type": "n2-standard-4","persona": "low_util","env": "staging","team": "Platform",   "project": "Customer Portal",     "base_cost": 4.8,  "region": "europe-west1",  "res_type": "compute"},

    # Cross-cloud — Security (expensive region: AP)
    {"id": "i-apac-prod-01",    "name": "APAC Production Server",   "provider": "AWS", "account": "aws-prod-001",     "service": "EC2",  "type": "m5.xlarge",   "persona": "healthy",      "env": "production", "team": "Platform",   "project": "Customer Portal",     "base_cost": 5.8,  "region": "ap-southeast-1","res_type": "compute"},
]


# ── CPU / usage by persona ───────────────────────────────────────────────────

def cpu_for_persona(persona: str) -> Optional[float]:
    if persona == "idle":
        return round(random.uniform(0.5, 4.5), 1)
    if persona == "low_util":
        return round(random.uniform(8, 14), 1)
    if persona == "oversized":
        return round(random.uniform(15, 28), 1)
    if persona in ("healthy", "apac"):
        return round(random.uniform(38, 72), 1)
    if persona == "dev_always_on":
        return round(random.uniform(5, 20), 1)
    if persona == "missing_tags":
        return round(random.uniform(25, 55), 1)
    return None  # S3/Lambda/BigQuery


def usage_hours_for_persona(persona: str, res_type: str) -> float:
    if res_type in ("storage", "serverless", "database"):
        return 0.0  # not meaningful for these types
    if persona in ("idle", "low_util", "dev_always_on"):
        return 24.0
    if persona == "healthy":
        return round(random.uniform(20, 24), 1)
    if persona == "oversized":
        return round(random.uniform(22, 24), 1)
    if persona == "missing_tags":
        return round(random.uniform(10, 24), 1)
    return 0.0


def cost_for_day(resource: dict, day_index: int) -> float:
    base = resource["base_cost"]
    noise = random.uniform(0.92, 1.08)
    # Gentle upward drift (8% over the full period)
    drift = 1 + (day_index / NUM_DAYS) * 0.08

    persona = resource["persona"]

    # Anomalous spike on specific days
    if persona == "anomalous" and day_index in (45, 87, 105):
        return round(base * random.uniform(18, 28), 2)

    # Dev resources: 0 cost on weekends
    if persona == "dev_always_on":
        sim_date = START_DATE + timedelta(days=day_index)
        if sim_date.weekday() >= 5:  # Saturday=5, Sunday=6
            return round(base * 0.1 * noise, 2)  # near-zero weekend cost

    return round(base * noise * drift, 2)


# ── Generator ────────────────────────────────────────────────────────────────

def generate() -> list:
    rows = []
    for day_index in range(NUM_DAYS):
        current_date = START_DATE + timedelta(days=day_index)
        month_start = current_date.replace(day=1)
        # Determine billing period (current month)
        if current_date.month == 12:
            month_end = current_date.replace(year=current_date.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            month_end = current_date.replace(month=current_date.month + 1, day=1) - timedelta(days=1)

        for r in RESOURCES:
            persona = r["persona"]
            res_type = r.get("res_type", "compute")
            cpu = cpu_for_persona(persona) if res_type in ("compute", "database") else None
            usage_hours = usage_hours_for_persona(persona, res_type)
            cost = cost_for_day(r, day_index)
            storage_gb = r.get("storage_gb")

            # Build tags string
            tag_parts = []
            if r.get("team"):
                tag_parts.append(f"team={r['team']}")
            if r.get("project"):
                tag_parts.append(f"project={r['project']}")
            if r.get("env"):
                tag_parts.append(f"environment={r['env']}")
            tags_str = ";".join(tag_parts) if tag_parts else None

            rows.append({
                "date":                    current_date.isoformat(),
                "provider":                r["provider"],
                "account_id":              r["account"],
                "service":                 r["service"],
                "resource_id":             r["id"],
                "resource_name":           r["name"],
                "resource_type":           res_type,
                "region":                  r["region"],
                "availability_zone":       r["region"] + "a" if r["provider"] == "AWS" and res_type == "compute" else "",
                "environment":             r.get("env") or "",
                "team":                    r.get("team") or "",
                "project":                 r.get("project") or "",
                "instance_type":           r.get("type") or "",
                "usage_hours":             usage_hours,
                "avg_cpu_utilization":     cpu if cpu is not None else "",
                "storage_gb":              storage_gb if storage_gb else "",
                "usage_quantity":          usage_hours or cost,
                "usage_unit":              "hours" if res_type == "compute" else "GB-month" if res_type == "storage" else "requests",
                "currency":                "USD",
                "list_cost":               round(cost * 1.12, 2),   # simulate ~12% discount
                "discount":                round(cost * 0.12, 2),
                "cost":                    cost,
                "billing_period_start":    month_start.isoformat(),
                "billing_period_end":      month_end.isoformat(),
                "tags":                    tags_str or "",
            })
    return rows


FIELDNAMES = [
    "date", "provider", "account_id", "service", "resource_id", "resource_name",
    "resource_type", "region", "availability_zone", "environment", "team", "project",
    "instance_type", "usage_hours", "avg_cpu_utilization", "storage_gb",
    "usage_quantity", "usage_unit", "currency", "list_cost", "discount", "cost",
    "billing_period_start", "billing_period_end", "tags",
]


if __name__ == "__main__":
    rows = generate()
    with open("sample_billing_data.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    providers = set(r["provider"] for r in rows)
    services = set(r["service"] for r in rows)
    envs = set(r["environment"] for r in rows if r["environment"])
    total_cost = sum(r["cost"] for r in rows)
    print(f"[OK] Generated {len(rows):,} rows -> sample_billing_data.csv")
    print(f"   Providers    : {sorted(providers)}")
    print(f"   Services     : {sorted(services)}")
    print(f"   Environments : {sorted(envs)}")
    print(f"   Date range   : {rows[0]['date']} -> {rows[-1]['date']}")
    print(f"   Total cost   : ${total_cost:,.2f}")
    print(f"   Resources    : {len(RESOURCES)}")

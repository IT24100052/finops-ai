"""
Generates a realistic synthetic AWS-style billing CSV so you can demo
the platform without needing a real cloud account.

Run: python generate_sample_data.py
Output: sample_billing_data.csv (90 days of data, ~15 resources,
including deliberately idle/oversized resources for the AI to catch)
"""
import csv
import random
from datetime import date, timedelta

random.seed(42)

SERVICES_INSTANCES = {
    "EC2": ["t3.micro", "t3.medium", "m5.large", "m5.xlarge", "m5.2xlarge", "c5.4xlarge"],
    "RDS": ["db.t3.medium", "db.m5.large", "db.r5.xlarge"],
    "S3": [None],
    "Lambda": [None],
}

NUM_DAYS = 90
START_DATE = date.today() - timedelta(days=NUM_DAYS)

# Define a fixed fleet of resources with intentional personas so waste
# detection has clear, explainable findings to surface.
RESOURCES = [
    {"id": "i-prod-web-01", "service": "EC2", "type": "m5.large", "persona": "healthy", "base_cost": 2.1},
    {"id": "i-prod-web-02", "service": "EC2", "type": "m5.large", "persona": "healthy", "base_cost": 2.1},
    {"id": "i-prod-api-01", "service": "EC2", "type": "m5.xlarge", "persona": "healthy", "base_cost": 4.2},
    {"id": "i-staging-test", "service": "EC2", "type": "m5.large", "persona": "idle", "base_cost": 2.1},
    {"id": "i-old-batch-job", "service": "EC2", "type": "c5.4xlarge", "persona": "idle", "base_cost": 16.0},
    {"id": "i-analytics-01", "service": "EC2", "type": "m5.2xlarge", "persona": "oversized", "base_cost": 8.4},
    {"id": "i-dev-sandbox", "service": "EC2", "type": "t3.medium", "persona": "healthy", "base_cost": 0.9},
    {"id": "db-prod-main", "service": "RDS", "type": "db.r5.xlarge", "persona": "healthy", "base_cost": 6.0},
    {"id": "db-reporting", "service": "RDS", "type": "db.m5.large", "persona": "oversized", "base_cost": 3.6},
    {"id": "db-legacy-archive", "service": "RDS", "type": "db.t3.medium", "persona": "idle", "base_cost": 1.8},
    {"id": "s3-prod-assets", "service": "S3", "type": None, "persona": "healthy", "base_cost": 0.8, "storage_gb": 2500},
    {"id": "s3-backups", "service": "S3", "type": None, "persona": "expensive_storage", "base_cost": 3.5, "storage_gb": 1800},
    {"id": "s3-logs-archive", "service": "S3", "type": None, "persona": "healthy", "base_cost": 0.4, "storage_gb": 900},
    {"id": "lambda-image-resize", "service": "Lambda", "type": None, "persona": "healthy", "base_cost": 0.3},
    {"id": "lambda-nightly-etl", "service": "Lambda", "type": None, "persona": "anomalous_spike", "base_cost": 0.5},
]


def cpu_for_persona(persona):
    if persona == "idle":
        return round(random.uniform(0.5, 4.5), 1)
    if persona == "oversized":
        return round(random.uniform(8, 25), 1)
    if persona == "healthy":
        return round(random.uniform(35, 78), 1)
    return None  # S3/Lambda don't have meaningful CPU%


def usage_hours_for_persona(persona):
    if persona == "idle":
        return 24.0  # always on, doing nothing
    if persona in ("oversized", "healthy"):
        return round(random.uniform(20, 24), 1)
    return 0.0


def cost_for_day(resource, day_index):
    base = resource["base_cost"]
    noise = random.uniform(0.9, 1.1)
    # Gentle upward drift over the period to give the predictor a real trend to find
    drift = 1 + (day_index / NUM_DAYS) * 0.15

    if resource["persona"] == "anomalous_spike" and day_index == NUM_DAYS - 3:
        return round(base * 25, 2)  # one-off anomalous spike near the end

    return round(base * noise * drift, 2)


def generate():
    rows = []
    for day_index in range(NUM_DAYS):
        current_date = START_DATE + timedelta(days=day_index)
        for r in RESOURCES:
            cpu = cpu_for_persona(r["persona"])
            usage_hours = usage_hours_for_persona(r["persona"])
            cost = cost_for_day(r, day_index)
            storage_gb = r.get("storage_gb")

            rows.append({
                "date": current_date.isoformat(),
                "service": r["service"],
                "resource_id": r["id"],
                "instance_type": r["type"] or "",
                "usage_hours": usage_hours,
                "avg_cpu_utilization": cpu if cpu is not None else "",
                "storage_gb": storage_gb if storage_gb else "",
                "cost": cost,
            })
    return rows


if __name__ == "__main__":
    rows = generate()
    fieldnames = ["date", "service", "resource_id", "instance_type",
                  "usage_hours", "avg_cpu_utilization", "storage_gb", "cost"]
    with open("sample_billing_data.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Generated {len(rows)} rows -> sample_billing_data.csv")

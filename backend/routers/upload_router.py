"""
Upload Router — Enhanced CSV ingestion with comprehensive validation.
Supports generic multi-cloud CSV format and AWS/Azure/GCP column aliases
via the provider normalizer.
"""
import io
from datetime import datetime
from typing import List

import pandas as pd
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session

import models
from database import get_db
from auth import get_current_user
from providers.normalizer import (
    normalize_dataframe, REQUIRED_COLUMNS, ALL_OPTIONAL_COLUMNS
)

router = APIRouter(prefix="/billing", tags=["billing"])

MAX_FILE_SIZE_MB = 50


# ── Validation helpers ───────────────────────────────────────────────────────

def _validate_row(row: pd.Series, idx: int, errors: List[str]) -> bool:
    """Validate a single row. Returns True if row is insertable, appends error strings."""
    ok = True

    # Required fields present
    for col in ["date", "service", "resource_id", "cost"]:
        if col not in row.index or pd.isna(row.get(col)):
            errors.append(f"Row {idx}: missing required field '{col}'")
            ok = False

    if not ok:
        return False  # can't validate further without required fields

    # Date validity
    if pd.isna(row.get("date")):
        errors.append(f"Row {idx}: invalid or unparseable date '{row.get('date')}'")
        ok = False

    # Cost validation
    try:
        cost = float(row["cost"])
        if cost < 0:
            errors.append(f"Row {idx}: negative cost ({cost}) is not allowed")
            ok = False
    except (ValueError, TypeError):
        errors.append(f"Row {idx}: cost '{row['cost']}' is not a valid number")
        ok = False

    # CPU validation (optional field)
    cpu = row.get("avg_cpu_utilization")
    if cpu is not None and not pd.isna(cpu):
        try:
            cpu_val = float(cpu)
            if not (0.0 <= cpu_val <= 100.0):
                errors.append(f"Row {idx}: avg_cpu_utilization={cpu_val} is outside 0–100%")
                ok = False
        except (ValueError, TypeError):
            errors.append(f"Row {idx}: avg_cpu_utilization '{cpu}' is not a valid number")
            ok = False

    # Usage hours validation (optional field)
    hours = row.get("usage_hours")
    if hours is not None and not pd.isna(hours):
        try:
            hours_val = float(hours)
            if hours_val < 0 or hours_val > 8784:  # max hours in a year
                errors.append(f"Row {idx}: usage_hours={hours_val} is outside valid range (0–8784)")
                ok = False
        except (ValueError, TypeError):
            errors.append(f"Row {idx}: usage_hours '{hours}' is not a valid number")
            ok = False

    return ok


def _safe_str(val) -> str | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    return str(val).strip() or None


def _safe_float(val) -> float | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _safe_date(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        return pd.to_datetime(val).date()
    except Exception:
        return None


# ── Router ───────────────────────────────────────────────────────────────────

@router.post("/upload")
async def upload_billing_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # File type check
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a .csv file")

    raw = await file.read()

    # Size check
    size_mb = len(raw) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=400,
            detail=f"File is {size_mb:.1f} MB. Maximum allowed size is {MAX_FILE_SIZE_MB} MB."
        )

    # Empty file check
    if len(raw) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # Parse CSV
    try:
        df = pd.read_csv(io.BytesIO(raw))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not parse CSV: {e}")

    if df.empty:
        raise HTTPException(status_code=400, detail="CSV file has no data rows.")

    # Normalize provider-specific columns → internal schema
    df = normalize_dataframe(df)

    # Check required columns
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise HTTPException(
            status_code=400,
            detail=(
                f"CSV is missing required columns: {sorted(missing)}. "
                f"Required: {sorted(REQUIRED_COLUMNS)}. "
                f"Optional: {ALL_OPTIONAL_COLUMNS}"
            ),
        )

    # Ensure optional columns exist (fill with None)
    for col in ALL_OPTIONAL_COLUMNS:
        if col not in df.columns:
            df[col] = None

    # Duplicate detection within this upload batch
    dup_cols = ["date", "service", "resource_id"]
    existing_dup_cols = [c for c in dup_cols if c in df.columns]
    if existing_dup_cols:
        duplicate_mask = df.duplicated(subset=existing_dup_cols, keep="first")
        n_dupes = int(duplicate_mask.sum())
    else:
        duplicate_mask = pd.Series([False] * len(df))
        n_dupes = 0

    # Row-level validation
    validation_errors: List[str] = []
    if n_dupes > 0:
        validation_errors.append(
            f"{n_dupes} duplicate rows detected within this upload (same date+service+resource_id) — only first occurrence kept."
        )

    df_deduped = df[~duplicate_mask].copy()

    inserted = 0
    rejected = 0
    inserted_costs: List[float] = []
    inserted_dates = []
    services_seen = set()
    providers_seen = set()

    for i, row in df_deduped.iterrows():
        row_errors: List[str] = []
        if not _validate_row(row, i + 2, row_errors):  # +2: header + 1-indexed
            validation_errors.extend(row_errors)
            rejected += 1
            continue

        try:
            cost_val = float(row["cost"])
            date_val = row["date"]
            if pd.isna(date_val):
                raise ValueError("date is NaT")

            record = models.BillingRecord(
                owner_id=current_user.id,
                date=date_val if not isinstance(date_val, str) else pd.to_datetime(date_val).date(),
                service=str(row["service"]),
                resource_id=str(row["resource_id"]),
                cost=cost_val,
                # Provider context
                provider=_safe_str(row.get("provider")),
                account_id=_safe_str(row.get("account_id")),
                region=_safe_str(row.get("region")),
                availability_zone=_safe_str(row.get("availability_zone")),
                # Cost allocation
                environment=_safe_str(row.get("environment")),
                team=_safe_str(row.get("team")),
                department=_safe_str(row.get("department")),
                project=_safe_str(row.get("project")),
                # Resource metadata
                resource_name=_safe_str(row.get("resource_name")),
                resource_type=_safe_str(row.get("resource_type")),
                instance_type=_safe_str(row.get("instance_type")),
                tags=_safe_str(row.get("tags")),
                # Usage
                usage_hours=_safe_float(row.get("usage_hours")) or 0.0,
                avg_cpu_utilization=_safe_float(row.get("avg_cpu_utilization")),
                storage_gb=_safe_float(row.get("storage_gb")),
                usage_quantity=_safe_float(row.get("usage_quantity")),
                usage_unit=_safe_str(row.get("usage_unit")),
                # Financial
                currency=_safe_str(row.get("currency")) or "USD",
                list_cost=_safe_float(row.get("list_cost")),
                discount=_safe_float(row.get("discount")),
                # Billing period
                billing_period_start=_safe_date(row.get("billing_period_start")),
                billing_period_end=_safe_date(row.get("billing_period_end")),
            )
            db.add(record)
            inserted += 1
            inserted_costs.append(cost_val)
            inserted_dates.append(date_val)
            services_seen.add(str(row["service"]))
            prov = _safe_str(row.get("provider"))
            if prov:
                providers_seen.add(prov)

        except Exception as e:
            validation_errors.append(f"Row {i + 2}: {e}")
            rejected += 1

    db.commit()

    # Build date range
    date_range = None
    if inserted_dates:
        try:
            dates = pd.to_datetime(inserted_dates)
            date_range = {"start": str(dates.min().date()), "end": str(dates.max().date())}
        except Exception:
            pass

    return {
        "filename": file.filename,
        "rows_inserted": inserted,
        "rows_rejected": rejected,
        "validation_errors": validation_errors[:20],  # cap response size
        "total_cost": round(sum(inserted_costs), 2),
        "date_range": date_range,
        "services_detected": sorted(services_seen),
        "providers_detected": sorted(providers_seen) if providers_seen else ["Generic"],
    }


@router.delete("/clear")
def clear_my_billing_data(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    deleted = db.query(models.BillingRecord).filter(
        models.BillingRecord.owner_id == current_user.id
    ).delete()
    db.commit()
    return {"deleted_rows": deleted}

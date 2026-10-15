"""
Upload Router — Enhanced CSV ingestion with comprehensive validation.
Supports generic multi-cloud CSV format and AWS/Azure/GCP column aliases
via the provider normalizer.
"""
import io
import math
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

    # Required fields present and non-empty
    for col in ["date", "service", "resource_id", "cost"]:
        val = row.get(col)
        if col not in row.index or pd.isna(val) or (isinstance(val, str) and not val.strip()):
            errors.append(f"Row {idx}: missing required field '{col}'")
            ok = False

    if not ok:
        return False  # can't validate further without required fields

    # Date validity
    d_raw = row.get("date")
    if pd.isna(d_raw) or d_raw is None:
        errors.append(f"Row {idx}: invalid or unparseable date '{d_raw}'")
        ok = False

    # Cost validation (must be finite, non-negative number)
    try:
        cost = float(row["cost"])
        if not math.isfinite(cost):
            errors.append(f"Row {idx}: cost must be a finite number")
            ok = False
        elif cost < 0:
            errors.append(f"Row {idx}: negative cost ({cost}) is not allowed")
            ok = False
    except (ValueError, TypeError):
        errors.append(f"Row {idx}: cost '{row['cost']}' is not a valid number")
        ok = False

    # CPU validation (optional field, 0-100%)
    cpu = row.get("avg_cpu_utilization")
    if cpu is not None and not pd.isna(cpu):
        try:
            cpu_val = float(cpu)
            if not math.isfinite(cpu_val) or not (0.0 <= cpu_val <= 100.0):
                errors.append(f"Row {idx}: avg_cpu_utilization={cpu_val} is outside 0–100%")
                ok = False
        except (ValueError, TypeError):
            errors.append(f"Row {idx}: avg_cpu_utilization '{cpu}' is not a valid number")
            ok = False

    # Usage hours validation (optional field, 0-8784)
    hours = row.get("usage_hours")
    if hours is not None and not pd.isna(hours):
        try:
            hours_val = float(hours)
            if not math.isfinite(hours_val) or hours_val < 0 or hours_val > 8784:  # max hours in a year
                errors.append(f"Row {idx}: usage_hours={hours_val} is outside valid range (0–8784)")
                ok = False
        except (ValueError, TypeError):
            errors.append(f"Row {idx}: usage_hours '{hours}' is not a valid number")
            ok = False

    # Storage GB validation (optional field, non-negative finite)
    storage = row.get("storage_gb")
    if storage is not None and not pd.isna(storage):
        try:
            s_val = float(storage)
            if not math.isfinite(s_val) or s_val < 0:
                errors.append(f"Row {idx}: storage_gb must be a non-negative finite number")
                ok = False
        except (ValueError, TypeError):
            errors.append(f"Row {idx}: storage_gb '{storage}' is not a valid number")
            ok = False

    # Usage quantity validation (optional field, non-negative finite)
    quantity = row.get("usage_quantity")
    if quantity is not None and not pd.isna(quantity):
        try:
            q_val = float(quantity)
            if not math.isfinite(q_val) or q_val < 0:
                errors.append(f"Row {idx}: usage_quantity must be a non-negative finite number")
                ok = False
        except (ValueError, TypeError):
            errors.append(f"Row {idx}: usage_quantity '{quantity}' is not a valid number")
            ok = False

    # List cost validation (optional field, non-negative finite)
    list_cost = row.get("list_cost")
    if list_cost is not None and not pd.isna(list_cost):
        try:
            lc_val = float(list_cost)
            if not math.isfinite(lc_val) or lc_val < 0:
                errors.append(f"Row {idx}: list_cost must be a non-negative finite number")
                ok = False
        except (ValueError, TypeError):
            errors.append(f"Row {idx}: list_cost '{list_cost}' is not a valid number")
            ok = False

    # Discount validation (optional field, non-negative finite)
    discount = row.get("discount")
    if discount is not None and not pd.isna(discount):
        try:
            d_val = float(discount)
            if not math.isfinite(d_val) or d_val < 0:
                errors.append(f"Row {idx}: discount must be a non-negative finite number")
                ok = False
        except (ValueError, TypeError):
            errors.append(f"Row {idx}: discount '{discount}' is not a valid number")
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
        f = float(val)
        if not math.isfinite(f):
            return None
        return f
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
    try:
        # File type check
        if not file.filename or not file.filename.lower().endswith(".csv"):
            raise HTTPException(status_code=400, detail="Please upload a .csv file")

        # Stream and enforce size limit chunk-by-chunk (prevents unbounded memory consumption)
        max_bytes = MAX_FILE_SIZE_MB * 1024 * 1024
        chunks = []
        total_bytes = 0
        chunk_size = 1024 * 1024  # 1 MB chunk

        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            total_bytes += len(chunk)
            if total_bytes > max_bytes:
                raise HTTPException(
                    status_code=400,
                    detail=f"File exceeds maximum allowed size of {MAX_FILE_SIZE_MB} MB."
                )
            chunks.append(chunk)

        if total_bytes == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        raw = b"".join(chunks)
    finally:
        await file.close()

    # Parse CSV safely
    try:
        df = pd.read_csv(io.BytesIO(raw))
    except pd.errors.EmptyDataError:
        raise HTTPException(status_code=400, detail="CSV file has no data rows.")
    except Exception:
        raise HTTPException(status_code=400, detail="Could not parse CSV file. Please ensure it is a valid, well-formed CSV.")

    if df.empty:
        raise HTTPException(status_code=400, detail="CSV file has no data rows.")

    # Normalize provider-specific columns → internal schema
    try:
        df = normalize_dataframe(df)
    except Exception:
        raise HTTPException(status_code=400, detail="Could not normalize CSV columns. Please check the file structure.")

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
                raise ValueError("date is unparseable or missing")

            record = models.BillingRecord(
                owner_id=current_user.id,
                date=date_val if not isinstance(date_val, str) else pd.to_datetime(date_val).date(),
                service=str(row["service"]).strip(),
                resource_id=str(row["resource_id"]).strip(),
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
            services_seen.add(str(row["service"]).strip())
            prov = _safe_str(row.get("provider"))
            if prov:
                providers_seen.add(prov)

        except Exception as e:
            validation_errors.append(f"Row {i + 2}: {e}")
            rejected += 1

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Database transaction failed while persisting billing records. Upload has been rolled back."
        )

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

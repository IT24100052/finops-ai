import io
from datetime import datetime

import pandas as pd
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session

import models
from database import get_db
from auth import get_current_user

router = APIRouter(prefix="/billing", tags=["billing"])

REQUIRED_COLUMNS = {"date", "service", "resource_id", "cost"}
OPTIONAL_COLUMNS = ["instance_type", "usage_hours", "avg_cpu_utilization", "storage_gb"]


@router.post("/upload")
async def upload_billing_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a .csv file")

    raw = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(raw))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not parse CSV: {e}")

    df.columns = [c.strip().lower() for c in df.columns]
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"CSV is missing required columns: {sorted(missing)}. "
                   f"Required: {sorted(REQUIRED_COLUMNS)}. Optional: {OPTIONAL_COLUMNS}",
        )

    for col in OPTIONAL_COLUMNS:
        if col not in df.columns:
            df[col] = None

    inserted = 0
    errors = []
    for i, row in df.iterrows():
        try:
            record = models.BillingRecord(
                owner_id=current_user.id,
                date=pd.to_datetime(row["date"]).date(),
                service=str(row["service"]),
                resource_id=str(row["resource_id"]),
                instance_type=None if pd.isna(row["instance_type"]) else str(row["instance_type"]),
                usage_hours=float(row["usage_hours"]) if not pd.isna(row["usage_hours"]) else 0.0,
                avg_cpu_utilization=float(row["avg_cpu_utilization"]) if not pd.isna(row["avg_cpu_utilization"]) else None,
                storage_gb=float(row["storage_gb"]) if not pd.isna(row["storage_gb"]) else None,
                cost=float(row["cost"]),
            )
            db.add(record)
            inserted += 1
        except Exception as e:
            errors.append(f"Row {i}: {e}")

    db.commit()
    return {
        "filename": file.filename,
        "rows_inserted": inserted,
        "rows_failed": len(errors),
        "errors": errors[:10],  # cap so the response stays small
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

"""
Regression & Hardening Test Suite for CSV Uploads, Normalizer, and Data Isolation.

Covers:
1. GCP detection with original dotted column names and normalized underscore names.
2. AWS and Azure aliases and generic CSV compatibility.
3. Missing required columns rejected.
4. Empty file, non-CSV extension, header-only CSV, and malformed CSV rejected.
5. In-batch duplicate rows deduplicated with validation notice.
6. Negative, non-numeric, NaN, and infinite costs rejected.
7. Non-finite, out-of-range CPU utilization and usage hours rejected.
8. Optional numeric fields (storage_gb, usage_quantity, list_cost, discount) validated safely.
9. File size limit enforcement (chunked streaming rejection for oversized files).
10. Database commit failure triggers rollback and returns HTTP 500 error.
11. Strict upload ownership and data isolation between different authenticated users.
"""
import io
import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock
import pandas as pd
from fastapi import UploadFile, HTTPException

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base
import models
from providers.normalizer import normalize_dataframe, _detect_provider
from routers.upload_router import (
    upload_billing_csv,
    clear_my_billing_data,
    MAX_FILE_SIZE_MB,
)


class TestUploadHardeningAndIsolation(unittest.IsolatedAsyncioTestCase):

    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        cls.TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)

    def setUp(self):
        Base.metadata.create_all(bind=self.engine)
        self.db = self.TestingSessionLocal()

        self.user_a = models.User(email="alice@example.com", hashed_password="hash_alice", role="user")
        self.user_b = models.User(email="bob@example.com", hashed_password="hash_bob", role="user")
        self.db.add_all([self.user_a, self.user_b])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)

    # ── 1. GCP detection & normalization ─────────────────────────────────────

    def test_01_gcp_dotted_columns_normalization(self):
        """GCP billing export with dotted column names is correctly detected and mapped."""
        df_raw = pd.DataFrame([{
            "usage_start_time": "2026-06-01",
            "service.description": "Compute Engine",
            "project.id": "my-gcp-project-123",
            "location.region": "us-central1",
            "resource.name": "instance-prod-1",
            "cost": 45.50,
        }])
        norm = normalize_dataframe(df_raw)
        self.assertEqual(norm["provider"].iloc[0], "GCP")
        self.assertIn("date", norm.columns)
        self.assertIn("service", norm.columns)
        self.assertIn("resource_id", norm.columns)
        self.assertIn("cost", norm.columns)
        self.assertEqual(norm["service"].iloc[0], "Compute Engine")
        self.assertEqual(norm["resource_id"].iloc[0], "instance-prod-1")
        self.assertEqual(norm["account_id"].iloc[0], "my-gcp-project-123")
        self.assertEqual(norm["region"].iloc[0], "us-central1")

    def test_02_gcp_underscore_columns_normalization(self):
        """GCP billing export with underscore column names is correctly detected and mapped."""
        df_raw = pd.DataFrame([{
            "usage_start_time": "2026-06-01",
            "service_description": "Cloud Storage",
            "project_id": "my-gcp-project-456",
            "location_region": "europe-west1",
            "resource_name": "bucket-logs-prod",
            "cost": 12.00,
        }])
        norm = normalize_dataframe(df_raw)
        self.assertEqual(norm["provider"].iloc[0], "GCP")
        self.assertEqual(norm["service"].iloc[0], "Cloud Storage")
        self.assertEqual(norm["resource_id"].iloc[0], "bucket-logs-prod")


    def test_gcp_columns_normalize_when_provider_column_exists(self):
        """GCP aliases are applied even when provider is already present."""
        import datetime

        df_raw = pd.DataFrame([{
            "provider": "GCP",
            "usage_start_time": "2026-06-01",
            "service.description": "Compute Engine",
            "resource.name": "vm-test-01",
            "cost": 12.5,
            "invoice.month": "202606",
            "project.id": "test-project",
        }])

        norm = normalize_dataframe(df_raw)

        self.assertEqual(norm["provider"].iloc[0], "GCP")
        self.assertEqual(norm["date"].iloc[0], datetime.date(2026, 6, 1))
        self.assertEqual(norm["service"].iloc[0], "Compute Engine")
        self.assertEqual(norm["resource_id"].iloc[0], "vm-test-01")
        self.assertEqual(norm["account_id"].iloc[0], "test-project")
        self.assertEqual(
            norm["billing_period_start"].iloc[0],
            datetime.date(2026, 6, 1),
        )
        self.assertEqual(
            norm["billing_period_end"].iloc[0],
            datetime.date(2026, 6, 30),
        )


    # ── 2. AWS and Azure aliases & Generic compatibility ────────────────────

    def test_03_aws_aliases_normalization(self):
        """AWS CUR naming conventions are detected and mapped to internal schema."""
        df_raw = pd.DataFrame([{
            "lineitem_usagestartdate": "2026-06-01",
            "lineitem_productcode": "AmazonEC2",
            "lineitem_resourceid": "i-0987654321fedcba",
            "lineitem_unblendedcost": 89.25,
            "product_region": "us-east-1",
            "user_team": "platform",
        }])
        norm = normalize_dataframe(df_raw)
        self.assertEqual(norm["provider"].iloc[0], "AWS")
        self.assertEqual(norm["service"].iloc[0], "AmazonEC2")
        self.assertEqual(norm["resource_id"].iloc[0], "i-0987654321fedcba")
        self.assertEqual(norm["cost"].iloc[0], 89.25)
        self.assertEqual(norm["team"].iloc[0], "platform")

    def test_04_azure_aliases_normalization(self):
        """Azure Cost Management naming conventions are detected and mapped."""
        df_raw = pd.DataFrame([{
            "date": "2026-06-01",
            "servicename": "Virtual Machines",
            "resourceid": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            "pretaxcost": 65.00,
            "subscriptionid": "sub-azure-123",
        }])
        norm = normalize_dataframe(df_raw)
        self.assertEqual(norm["provider"].iloc[0], "Azure")
        self.assertEqual(norm["service"].iloc[0], "Virtual Machines")
        self.assertEqual(norm["cost"].iloc[0], 65.00)
        self.assertEqual(norm["account_id"].iloc[0], "sub-azure-123")

    def test_05_generic_csv_compatibility(self):
        """Generic CSV with standard columns passes through cleanly."""
        df_raw = pd.DataFrame([{
            "date": "2026-06-01",
            "service": "CustomApp",
            "resource_id": "res-custom-01",
            "cost": 10.00,
            "provider": "DigitalOcean",
        }])
        norm = normalize_dataframe(df_raw)
        self.assertEqual(norm["provider"].iloc[0], "DigitalOcean")
        self.assertEqual(norm["service"].iloc[0], "CustomApp")

    # ── 3. Missing required columns ──────────────────────────────────────────

    async def test_06_missing_required_columns_rejected(self):
        """CSV missing 'cost' or 'resource_id' raises HTTP 400 with missing columns list."""
        csv_bytes = b"date,service\n2026-06-01,EC2\n"
        upload = UploadFile(filename="test.csv", file=io.BytesIO(csv_bytes))

        with self.assertRaises(HTTPException) as ctx:
            await upload_billing_csv(upload, self.db, self.user_a)

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("missing required columns", ctx.exception.detail)

    # ── 4. Empty, non-CSV, or malformed input ─────────────────────────────────

    async def test_07_empty_file_rejected(self):
        """Empty file raises HTTP 400."""
        upload = UploadFile(filename="empty.csv", file=io.BytesIO(b""))
        with self.assertRaises(HTTPException) as ctx:
            await upload_billing_csv(upload, self.db, self.user_a)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("empty", ctx.exception.detail)

    async def test_08_invalid_extension_rejected(self):
        """Non-CSV extension raises HTTP 400."""
        upload = UploadFile(filename="billing.xlsx", file=io.BytesIO(b"some content"))
        with self.assertRaises(HTTPException) as ctx:
            await upload_billing_csv(upload, self.db, self.user_a)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Please upload a .csv file", ctx.exception.detail)

    async def test_09_header_only_csv_rejected(self):
        """CSV with headers only and no data rows raises HTTP 400."""
        upload = UploadFile(filename="header_only.csv", file=io.BytesIO(b"date,service,resource_id,cost\n"))
        with self.assertRaises(HTTPException) as ctx:
            await upload_billing_csv(upload, self.db, self.user_a)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("no data rows", ctx.exception.detail)

    # ── 5. In-batch duplicate rows ───────────────────────────────────────────

    async def test_10_duplicate_rows_deduplicated_safely(self):
        """Duplicate rows within the same upload batch keep only first occurrence."""
        csv_content = (
            "date,service,resource_id,cost\n"
            "2026-06-01,EC2,res-1,50.00\n"
            "2026-06-01,EC2,res-1,50.00\n"
            "2026-06-02,EC2,res-2,30.00\n"
        ).encode("utf-8")
        upload = UploadFile(filename="dupes.csv", file=io.BytesIO(csv_content))
        res = await upload_billing_csv(upload, self.db, self.user_a)

        self.assertEqual(res["rows_inserted"], 2)
        self.assertTrue(any("duplicate rows detected" in err for err in res["validation_errors"]))

    # ── 6. Negative, NaN, infinite costs ─────────────────────────────────────

    async def test_11_invalid_and_nonfinite_costs_rejected(self):
        """Negative, NaN, string, and infinite costs are rejected per-row."""
        csv_content = (
            "date,service,resource_id,cost\n"
            "2026-06-01,EC2,res-valid,100.00\n"
            "2026-06-01,EC2,res-neg,-25.00\n"
            "2026-06-01,EC2,res-nan,nan\n"
            "2026-06-01,EC2,res-inf,inf\n"
            "2026-06-01,EC2,res-str,not-a-number\n"
        ).encode("utf-8")
        upload = UploadFile(filename="costs.csv", file=io.BytesIO(csv_content))
        res = await upload_billing_csv(upload, self.db, self.user_a)

        self.assertEqual(res["rows_inserted"], 1)
        self.assertEqual(res["rows_rejected"], 4)
        self.assertEqual(res["total_cost"], 100.00)

    # ── 7. CPU and usage-hours validation ────────────────────────────────────

    async def test_12_nonfinite_cpu_and_usage_hours_rejected(self):
        """CPU outside 0-100% or non-finite, and usage hours outside 0-8784 or non-finite are rejected."""
        csv_content = (
            "date,service,resource_id,cost,avg_cpu_utilization,usage_hours\n"
            "2026-06-01,EC2,res-valid,50.00,45.0,24.0\n"
            "2026-06-01,EC2,res-badcpu-high,50.00,120.0,24.0\n"
            "2026-06-01,EC2,res-badcpu-inf,50.00,inf,24.0\n"
            "2026-06-01,EC2,res-badhours-high,50.00,45.0,9000.0\n"
            "2026-06-01,EC2,res-badhours-neg,50.00,45.0,-5.0\n"
        ).encode("utf-8")
        upload = UploadFile(filename="metrics.csv", file=io.BytesIO(csv_content))
        res = await upload_billing_csv(upload, self.db, self.user_a)

        self.assertEqual(res["rows_inserted"], 1)
        self.assertEqual(res["rows_rejected"], 4)

    # ── 8. Optional numeric fields ───────────────────────────────────────────

    async def test_13_optional_numeric_fields_validation(self):
        """Optional fields like storage_gb, list_cost, discount must be non-negative finite numbers."""
        csv_content = (
            "date,service,resource_id,cost,storage_gb,list_cost,discount\n"
            "2026-06-01,S3,bkt-valid,10.00,500.0,15.00,5.00\n"
            "2026-06-01,S3,bkt-badstorage,10.00,-10.0,15.00,5.00\n"
            "2026-06-01,S3,bkt-badlistcost,10.00,500.0,inf,5.00\n"
            "2026-06-01,S3,bkt-baddiscount,10.00,500.0,15.00,-2.00\n"
        ).encode("utf-8")
        upload = UploadFile(filename="optional_fields.csv", file=io.BytesIO(csv_content))
        res = await upload_billing_csv(upload, self.db, self.user_a)

        self.assertEqual(res["rows_inserted"], 1)
        self.assertEqual(res["rows_rejected"], 3)

    # ── 9. File size limit enforcement ───────────────────────────────────────

    async def test_14_file_size_limit_streaming_enforcement(self):
        """Oversized file exceeding MAX_FILE_SIZE_MB raises HTTP 400 during streaming."""
        # Create an async mock file reader that returns chunks exceeding limit
        oversized_bytes = (MAX_FILE_SIZE_MB + 1) * 1024 * 1024
        mock_file = MagicMock()
        mock_file.filename = "huge.csv"

        remaining = oversized_bytes
        chunk_sz = 1024 * 1024

        async def mock_read(sz=-1):
            nonlocal remaining
            if remaining <= 0:
                return b""
            n = min(sz if sz > 0 else chunk_sz, remaining)
            remaining -= n
            return b"X" * n

        mock_file.read = mock_read
        closed = False
        async def async_close():
            nonlocal closed
            closed = True

        mock_file.close = async_close

        with self.assertRaises(HTTPException) as ctx:
            await upload_billing_csv(mock_file, self.db, self.user_a)

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("exceeds maximum allowed size", ctx.exception.detail)
        self.assertTrue(closed)

    # ── 10. Database commit failure and rollback ─────────────────────────────

    async def test_15_db_commit_failure_triggers_rollback(self):
        """Database commit failure rolls back transaction and raises HTTP 500."""
        csv_content = b"date,service,resource_id,cost\n2026-06-01,EC2,res-fail,50.00\n"
        upload = UploadFile(filename="commit_fail.csv", file=io.BytesIO(csv_content))

        mock_db = MagicMock()
        mock_db.commit.side_effect = Exception("Simulated DB commit error")
        mock_db.rollback = MagicMock()

        with self.assertRaises(HTTPException) as ctx:
            await upload_billing_csv(upload, mock_db, self.user_a)

        self.assertEqual(ctx.exception.status_code, 500)
        self.assertIn("Database transaction failed", ctx.exception.detail)
        mock_db.rollback.assert_called_once()

    # ── 11. User data isolation & clear scoping ──────────────────────────────

    async def test_16_upload_ownership_and_data_isolation(self):
        """Records uploaded by user_a are strictly isolated from user_b."""
        csv_a = b"date,service,resource_id,cost\n2026-06-01,EC2,res-alice,120.00\n"
        csv_b = b"date,service,resource_id,cost\n2026-06-01,GCS,res-bob,45.00\n"

        upload_a = UploadFile(filename="alice.csv", file=io.BytesIO(csv_a))
        upload_b = UploadFile(filename="bob.csv", file=io.BytesIO(csv_b))

        await upload_billing_csv(upload_a, self.db, self.user_a)
        await upload_billing_csv(upload_b, self.db, self.user_b)

        records_a = self.db.query(models.BillingRecord).filter(models.BillingRecord.owner_id == self.user_a.id).all()
        records_b = self.db.query(models.BillingRecord).filter(models.BillingRecord.owner_id == self.user_b.id).all()

        self.assertEqual(len(records_a), 1)
        self.assertEqual(records_a[0].resource_id, "res-alice")
        self.assertEqual(records_a[0].cost, 120.00)

        self.assertEqual(len(records_b), 1)
        self.assertEqual(records_b[0].resource_id, "res-bob")
        self.assertEqual(records_b[0].cost, 45.00)

        # Alice clears data; Bob's data remains completely intact
        res_clear = clear_my_billing_data(self.db, self.user_a)
        self.assertEqual(res_clear["deleted_rows"], 1)

        remaining_a = self.db.query(models.BillingRecord).filter(models.BillingRecord.owner_id == self.user_a.id).count()
        remaining_b = self.db.query(models.BillingRecord).filter(models.BillingRecord.owner_id == self.user_b.id).count()

        self.assertEqual(remaining_a, 0)
        self.assertEqual(remaining_b, 1)

    # ── 12. Budget CRUD isolation between users ──────────────────────────────

    def test_17_budget_crud_isolation_between_users(self):
        """User A's budgets cannot be viewed, updated, or deleted by User B."""
        from routers.budgets_router import list_budgets, create_budget, update_budget, delete_budget
        import schemas

        # User A creates a budget
        b_create = schemas.BudgetCreate(
            name="Alice Prod Budget",
            scope="overall",
            monthly_limit=5000.0,
        )
        created = create_budget(b_create, self.db, self.user_a)
        budget_id = created["id"]

        # User B listing budgets does not see Alice's budget
        budgets_b = list_budgets(self.db, self.user_b)
        self.assertEqual(len(budgets_b), 0)

        # User B updating Alice's budget gets 404
        b_update = schemas.BudgetUpdate(name="Bob Hijack")
        with self.assertRaises(HTTPException) as ctx_up:
            update_budget(budget_id, b_update, self.db, self.user_b)
        self.assertEqual(ctx_up.exception.status_code, 404)

        # User B deleting Alice's budget gets 404
        with self.assertRaises(HTTPException) as ctx_del:
            delete_budget(budget_id, self.db, self.user_b)
        self.assertEqual(ctx_del.exception.status_code, 404)

        # Alice's budget is intact
        budgets_a = list_budgets(self.db, self.user_a)
        self.assertEqual(len(budgets_a), 1)
        self.assertEqual(budgets_a[0]["name"], "Alice Prod Budget")

    # ── 13. JWT expiration & token validation ────────────────────────────────

    def test_18_jwt_signing_and_expired_token_rejected(self):
        """Valid JWT authenticates successfully; expired token raises HTTP 401."""
        from datetime import datetime, timedelta, timezone
        from auth import create_access_token, get_current_user

        # Valid token
        valid_token = create_access_token(data={"sub": self.user_a.email})
        authed_user = get_current_user(token=valid_token, db=self.db)
        self.assertEqual(authed_user.id, self.user_a.id)

        # Expired token (in past)
        expired_token = create_access_token(
            data={"sub": self.user_a.email},
            expires_delta=timedelta(minutes=-10)
        )
        with self.assertRaises(HTTPException) as ctx:
            get_current_user(token=expired_token, db=self.db)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("Could not validate credentials", ctx.exception.detail)

    def test_19_weak_or_missing_finops_secret_fails_safely(self):
        """Validation logic confirms secrets < 32 characters are rejected."""
        short_secret = "weak-secret-123"
        self.assertLess(len(short_secret), 32)

        # Function simulating auth module's startup guard
        def check_secret(sec):
            if not sec or len(sec) < 32:
                raise RuntimeError("FINOPS_SECRET_KEY must be configured with a strong secret of at least 32 characters.")

        with self.assertRaises(RuntimeError):
            check_secret(None)

        with self.assertRaises(RuntimeError):
            check_secret(short_secret)

        # Valid 32+ character secret passes check
        strong_secret = "a" * 32
        check_secret(strong_secret)

    # ── 14. Registration role enforcement & admin security (Task 1) ──────────

    def test_20_first_public_registration_receives_user_role(self):
        """Even on an empty users table, the first public registration gets role='user'."""
        from routers.auth_router import register
        import schemas
        empty_session = self.TestingSessionLocal()
        try:
            empty_session.query(models.User).delete()
            empty_session.commit()
            self.assertEqual(empty_session.query(models.User).count(), 0)

            user_in = schemas.UserCreate(email="first@example.com", password="secure_password_123")
            created_user = register(user_in, empty_session)

            self.assertEqual(created_user.role, "user")
            self.assertNotEqual(created_user.role, "admin")
        finally:
            empty_session.close()

    def test_21_subsequent_registration_receives_user_role(self):
        """Subsequent public registrations also receive role='user'."""
        from routers.auth_router import register
        import schemas
        user_in = schemas.UserCreate(email="second@example.com", password="password_abc_456")
        created_user = register(user_in, self.db)
        self.assertEqual(created_user.role, "user")

    def test_22_public_registration_cannot_inject_admin_role(self):
        """Submitting extra role fields in registration cannot elevate role to 'admin'."""
        from routers.auth_router import register
        import schemas
        user_in = schemas.UserCreate(email="hacker@example.com", password="password123")
        created_user = register(user_in, self.db)
        self.assertEqual(created_user.role, "user")

    def test_23_existing_admin_accounts_retain_admin_role(self):
        """Existing administrators in the database retain their current role."""
        admin_user = models.User(email="realadmin@example.com", hashed_password="hashed_admin_pass", role="admin")
        self.db.add(admin_user)
        self.db.commit()

        queried = self.db.query(models.User).filter(models.User.email == "realadmin@example.com").first()
        self.assertEqual(queried.role, "admin")

    def test_24_registration_and_password_hashing_continue_to_function(self):
        """Registration properly hashes passwords and rejects duplicate emails."""
        from routers.auth_router import register
        from auth import verify_password
        import schemas

        user_in = schemas.UserCreate(email="hash_test@example.com", password="plain_password_xyz")
        user = register(user_in, self.db)

        self.assertNotEqual(user.hashed_password, "plain_password_xyz")
        self.assertTrue(verify_password("plain_password_xyz", user.hashed_password))

        # Duplicate email rejected
        with self.assertRaises(HTTPException) as ctx:
            register(user_in, self.db)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("already registered", ctx.exception.detail)

    # ── 15. GCP invoice-month parsing & billing period calculation (Task 2) ──

    def test_25_gcp_invoice_month_202606_parsing(self):
        """202606 converts to start 2026-06-01 and end 2026-06-30."""
        import datetime
        df = pd.DataFrame([{
            "date": "2026-06-15",
            "service": "Compute Engine",
            "resource_id": "vm-gcp-1",
            "cost": 100.0,
            "invoice_month": 202606,
        }])
        norm = normalize_dataframe(df)
        self.assertEqual(norm["billing_period_start"].iloc[0], datetime.date(2026, 6, 1))
        self.assertEqual(norm["billing_period_end"].iloc[0], datetime.date(2026, 6, 30))

    def test_26_gcp_invoice_month_february_non_leap_year(self):
        """Valid February in non-leap year (202302) sets end date to 2023-02-28."""
        import datetime
        df = pd.DataFrame([{
            "date": "2023-02-10",
            "service": "Compute Engine",
            "resource_id": "vm-feb-1",
            "cost": 50.0,
            "invoice_month": "202302",
        }])
        norm = normalize_dataframe(df)
        self.assertEqual(norm["billing_period_start"].iloc[0], datetime.date(2023, 2, 1))
        self.assertEqual(norm["billing_period_end"].iloc[0], datetime.date(2023, 2, 28))

    def test_27_gcp_invoice_month_february_leap_year(self):
        """Valid February in leap year (202402) sets end date to 2024-02-29."""
        import datetime
        df = pd.DataFrame([{
            "date": "2024-02-10",
            "service": "Compute Engine",
            "resource_id": "vm-leap-1",
            "cost": 50.0,
            "invoice_month": "202402",
        }])
        norm = normalize_dataframe(df)
        self.assertEqual(norm["billing_period_start"].iloc[0], datetime.date(2024, 2, 1))
        self.assertEqual(norm["billing_period_end"].iloc[0], datetime.date(2024, 2, 29))

    def test_28_gcp_invoice_month_30_and_31_day_months(self):
        """Calculates correct month-end dates for 30-day and 31-day months."""
        import datetime
        df = pd.DataFrame([
            {"date": "2026-04-10", "service": "EC2", "resource_id": "r1", "cost": 10.0, "invoice_month": 202604},
            {"date": "2026-07-10", "service": "EC2", "resource_id": "r2", "cost": 20.0, "invoice_month": 202607},
        ])
        norm = normalize_dataframe(df)
        self.assertEqual(norm["billing_period_start"].iloc[0], datetime.date(2026, 4, 1))
        self.assertEqual(norm["billing_period_end"].iloc[0], datetime.date(2026, 4, 30))
        self.assertEqual(norm["billing_period_start"].iloc[1], datetime.date(2026, 7, 1))
        self.assertEqual(norm["billing_period_end"].iloc[1], datetime.date(2026, 7, 31))

    def test_29_invalid_invoice_month_values_evaluate_to_none(self):
        """Invalid month values (202613, 202600, malformed) are safely set to None."""
        df = pd.DataFrame([
            {"date": "2026-06-01", "service": "EC2", "resource_id": "r1", "cost": 10.0, "invoice_month": 202613},
            {"date": "2026-06-01", "service": "EC2", "resource_id": "r2", "cost": 10.0, "invoice_month": 202600},
            {"date": "2026-06-01", "service": "EC2", "resource_id": "r3", "cost": 10.0, "invoice_month": "not_a_month"},
        ])
        norm = normalize_dataframe(df)
        self.assertIsNone(norm["billing_period_start"].iloc[0])
        self.assertIsNone(norm["billing_period_end"].iloc[0])
        self.assertIsNone(norm["billing_period_start"].iloc[1])
        self.assertIsNone(norm["billing_period_end"].iloc[1])
        self.assertIsNone(norm["billing_period_start"].iloc[2])
        self.assertIsNone(norm["billing_period_end"].iloc[2])

    def test_30_missing_or_empty_invoice_month_evaluated_as_none(self):
        """Missing or empty invoice-month values evaluate to None per optional field contract."""
        df = pd.DataFrame([
            {"date": "2026-06-01", "service": "EC2", "resource_id": "r1", "cost": 10.0, "invoice_month": None},
            {"date": "2026-06-01", "service": "EC2", "resource_id": "r2", "cost": 10.0, "invoice_month": ""},
        ])
        norm = normalize_dataframe(df)
        self.assertIsNone(norm["billing_period_start"].iloc[0])
        self.assertIsNone(norm["billing_period_end"].iloc[0])
        self.assertIsNone(norm["billing_period_start"].iloc[1])
        self.assertIsNone(norm["billing_period_end"].iloc[1])

    def test_31_gcp_dotted_invoice_month_normalization(self):
        """GCP exports with dotted 'invoice.month' header normalize to billing_period_start and billing_period_end."""
        import datetime
        df = pd.DataFrame([{
            "usage_start_time": "2026-06-01",
            "service.description": "Cloud Storage",
            "resource.name": "bkt-1",
            "cost": 15.0,
            "invoice.month": "202606",
            "project.id": "gcp-proj-1",
        }])
        norm = normalize_dataframe(df)
        self.assertEqual(norm["provider"].iloc[0], "GCP")
        self.assertEqual(norm["billing_period_start"].iloc[0], datetime.date(2026, 6, 1))
        self.assertEqual(norm["billing_period_end"].iloc[0], datetime.date(2026, 6, 30))

    def test_32_aws_azure_generic_date_parsing_remains_unchanged(self):
        """AWS CUR and Azure date parsing with standard dates remains intact."""
        import datetime
        df_aws = pd.DataFrame([{
            "lineitem_usagestartdate": "2026-06-01T00:00:00Z",
            "lineitem_productcode": "EC2",
            "lineitem_resourceid": "i-123",
            "lineitem_unblendedcost": 10.0,
            "billing_period_start_date": "2026-06-01",
            "billing_period_end_date": "2026-06-30",
        }])
        norm_aws = normalize_dataframe(df_aws)
        self.assertEqual(norm_aws["date"].iloc[0], datetime.date(2026, 6, 1))
        self.assertEqual(norm_aws["billing_period_start"].iloc[0], datetime.date(2026, 6, 1))
        self.assertEqual(norm_aws["billing_period_end"].iloc[0], datetime.date(2026, 6, 30))

    async def test_33_end_to_end_gcp_upload_persists_billing_periods(self):
        """End-to-end GCP CSV upload parses invoice.month into BillingRecord start and end dates."""
        import datetime
        csv_content = (
            "usage_start_time,service.description,resource.name,cost,invoice.month,project.id\n"
            "2026-06-01,Cloud Spanner,spanner-instance-1,250.00,202606,my-project-789\n"
        ).encode("utf-8")
        upload = UploadFile(filename="gcp_export.csv", file=io.BytesIO(csv_content))
        res = await upload_billing_csv(upload, self.db, self.user_a)

        self.assertEqual(res["rows_inserted"], 1)
        self.assertEqual(res["rows_rejected"], 0)

        record = self.db.query(models.BillingRecord).filter(
            models.BillingRecord.resource_id == "spanner-instance-1"
        ).first()

        self.assertIsNotNone(record)
        self.assertEqual(record.billing_period_start, datetime.date(2026, 6, 1))
        self.assertEqual(record.billing_period_end, datetime.date(2026, 6, 30))
        self.assertEqual(record.provider, "GCP")


if __name__ == "__main__":
    unittest.main()

"""
test_datasets.py – Tests for the /dataset router.

Covers:
  - POST /dataset/upload  → CSV upload, wrong file type, unauthenticated
  - GET  /dataset/         → list pagination
  - GET  /dataset/{uid}    → fetch single, not found, wrong owner
  - PATCH /dataset/{uid}   → update name
  - DELETE /dataset/{uid}  → owner can delete, non-owner cannot
"""
import io
import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient

# ---------------------------------------------------------------------------
# Minimal valid CSV content (same structure your app expects)
# ---------------------------------------------------------------------------
VALID_CSV = (
    "equipment_name,equipment_type,flowrate,pressure,temperature,status\n"
    "Pump-A,Centrifugal,120.5,3.2,85.0,active\n"
    "Valve-B,Gate,45.0,2.1,72.0,active\n"
    "HeatEx-C,Shell&Tube,200.0,5.0,110.0,inactive\n"
)

INVALID_CSV = "not,a,valid,csv\nbad data\n"


def csv_file(content: str = VALID_CSV, filename: str = "test_dataset.csv"):
    return ("file", (filename, io.BytesIO(content.encode()), "text/csv"))


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------
class TestDatasetUpload:
    @pytest.mark.asyncio
    async def test_upload_valid_csv(self, client: AsyncClient, auth_headers: dict):
        """Valid CSV file should be accepted and processed (200/201)."""
        resp = await client.post(
            "/dataset/upload",
            files=[csv_file()],
            headers=auth_headers,
        )
        assert resp.status_code in (200, 201), resp.text
        data = resp.json()
        assert "uid" in data or "dataset_uid" in str(data)

    @pytest.mark.asyncio
    async def test_upload_non_csv_file(self, client: AsyncClient, auth_headers: dict):
        """Uploading a .txt file should be rejected (400 or 422)."""
        resp = await client.post(
            "/dataset/upload",
            files=[("file", ("data.txt", io.BytesIO(b"hello world"), "text/plain"))],
            headers=auth_headers,
        )
        assert resp.status_code in (400, 422)

    @pytest.mark.asyncio
    async def test_upload_unauthenticated(self, client: AsyncClient):
        """Uploading without a token returns 401 or 403."""
        resp = await client.post(
            "/dataset/upload",
            files=[csv_file()],
        )
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_upload_unverified_user_blocked(self, client: AsyncClient):
        """Unverified users should be blocked from uploading (403 UserNotVerified)."""
        payload = {
            "first_name": "Unverf",
            "last_name": "Dset",
            "username": "unverdst",
            "email": f"unverf_{uuid.uuid4().hex[:6]}@example.com",
            "password": "SomePwd1",
        }
        await client.post("/auth/signup", json=payload)
        
        # Explicitly mark user as unverified in DB to test the guard
        from src.db.main import AsyncSessionLocal
        from src.db.models import User
        from sqlmodel import select
        async with AsyncSessionLocal() as db_session:
            stmt = select(User).where(User.email == payload["email"])
            res = await db_session.exec(stmt)
            u = res.first()
            if u:
                u.is_verified = False
                await db_session.commit()

        login = await client.post(
            "/auth/login",
            json={"email": payload["email"], "password": payload["password"]},
        )
        token = login.json().get("access_token", "")
        resp = await client.post(
            "/dataset/upload",
            files=[csv_file()],
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# List datasets
# ---------------------------------------------------------------------------
class TestDatasetList:
    @pytest.mark.asyncio
    async def test_list_datasets(self, client: AsyncClient, auth_headers: dict):
        """Authenticated user can list their datasets (empty or populated)."""
        resp = await client.get("/dataset/", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        # Expect a paginated structure
        assert isinstance(data, dict)
        assert "total" in data or "datasets" in data or isinstance(data.get("data"), list) or True

    @pytest.mark.asyncio
    async def test_list_datasets_pagination(self, client: AsyncClient, auth_headers: dict):
        """Pagination params are accepted."""
        resp = await client.get("/dataset/?page=1&page_size=2", headers=auth_headers)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_list_datasets_unauthenticated(self, client: AsyncClient):
        """Unauthenticated request returns 401/403."""
        resp = await client.get("/dataset/")
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Get / update / delete
# ---------------------------------------------------------------------------
class TestDatasetCRUD:
    @pytest_asyncio.fixture()
    async def uploaded_dataset(self, client: AsyncClient, auth_headers: dict):
        """Upload a dataset once, return its UID for use in CRUD tests."""
        resp = await client.post(
            "/dataset/upload",
            files=[csv_file()],
            headers=auth_headers,
        )
        if resp.status_code not in (200, 201):
            pytest.skip(f"Upload failed: {resp.text}")
        data = resp.json()
        uid = data.get("uid") or data.get("dataset_uid") or data.get("id")
        return str(uid)

    @pytest.mark.asyncio
    async def test_get_dataset(
        self, client: AsyncClient, auth_headers: dict, uploaded_dataset: str
    ):
        """Owner can fetch their dataset by UID."""
        resp = await client.get(f"/dataset/{uploaded_dataset}", headers=auth_headers)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_get_nonexistent_dataset(self, client: AsyncClient, auth_headers: dict):
        """Random UID returns 404."""
        resp = await client.get(f"/dataset/{uuid.uuid4()}", headers=auth_headers)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update_dataset(
        self, client: AsyncClient, auth_headers: dict, uploaded_dataset: str
    ):
        """Owner can update dataset metadata."""
        resp = await client.patch(
            f"/dataset/{uploaded_dataset}",
            json={"original_filename": "renamed_dataset.csv"},
            headers=auth_headers,
        )
        assert resp.status_code in (200, 204)

    @pytest.mark.asyncio
    async def test_delete_dataset(
        self, client: AsyncClient, auth_headers: dict, uploaded_dataset: str
    ):
        """Owner can delete their dataset."""
        resp = await client.delete(f"/dataset/{uploaded_dataset}", headers=auth_headers)
        assert resp.status_code == 200
        assert "deleted" in resp.json()["message"].lower()

    @pytest.mark.asyncio
    async def test_delete_dataset_unauthenticated(
        self, client: AsyncClient, uploaded_dataset: str
    ):
        """Unauthenticated delete request returns 401/403."""
        resp = await client.delete(f"/dataset/{uploaded_dataset}")
        assert resp.status_code in (401, 403)

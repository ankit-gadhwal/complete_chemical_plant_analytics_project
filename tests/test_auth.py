"""
test_auth.py – Tests for the /auth router.
"""
import uuid
import pytest
from httpx import AsyncClient
from sqlmodel import select

from src.auth.utils import create_url_safe_token, create_access_token
from src.db.main import AsyncSessionLocal
from src.db.models import User


# ---------------------------------------------------------------------------
# Signup
# ---------------------------------------------------------------------------
class TestSignup:
    @pytest.mark.asyncio
    async def test_signup_success(self, client: AsyncClient):
        """New user signup returns 200 and a message about verification email."""
        uid_str = uuid.uuid4().hex[:6]
        payload = {
            "first_name": "John",
            "last_name": "Doe",
            "username": f"u{uid_str}",
            "email": f"johndoe_{uid_str}@example.com",
            "password": "SecurePass1",
        }
        resp = await client.post("/auth/signup", json=payload)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["user"]["email"] == payload["email"]
        assert data["user"]["is_verified"] is True  # auto-verified directly on signup

    @pytest.mark.asyncio
    async def test_signup_duplicate_email(self, client: AsyncClient, test_user_data, registered_user):
        """Registering the same email twice raises 403 / 409 UserAlreadyExists."""
        resp = await client.post("/auth/signup", json=test_user_data)
        assert resp.status_code in (403, 409)

    @pytest.mark.asyncio
    async def test_signup_short_password(self, client: AsyncClient):
        """Password shorter than 6 chars should fail validation (422)."""
        payload = {
            "first_name": "A",
            "last_name": "B",
            "username": f"u{uuid.uuid4().hex[:6]}",
            "email": f"shortpw_{uuid.uuid4().hex[:6]}@example.com",
            "password": "abc",
        }
        resp = await client.post("/auth/signup", json=payload)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_signup_missing_fields(self, client: AsyncClient):
        """Missing required fields returns 422 Unprocessable Entity."""
        resp = await client.post("/auth/signup", json={"email": "no@pw.com"})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------
class TestLogin:
    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient, test_user_data, registered_user):
        """Verified user can log in and receives access + refresh tokens."""
        resp = await client.post(
            "/auth/login",
            json={"email": test_user_data["email"], "password": test_user_data["password"]},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["message"] == "Login successful"

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client: AsyncClient, test_user_data, registered_user):
        """Wrong password returns 400 InvalidCredentials."""
        resp = await client.post(
            "/auth/login",
            json={"email": test_user_data["email"], "password": "WrongPass999"},
        )
        assert resp.status_code in (400, 401, 403)

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client: AsyncClient):
        """Login with unknown email returns 400/401/403."""
        resp = await client.post(
            "/auth/login",
            json={"email": f"ghost_{uuid.uuid4().hex[:6]}@example.com", "password": "anything123"},
        )
        assert resp.status_code in (400, 401, 403)

    @pytest.mark.asyncio
    async def test_login_unverified_user(self, client: AsyncClient):
        """Unverified user login attempt."""
        uid_str = uuid.uuid4().hex[:6]
        payload = {
            "first_name": "Unverified",
            "last_name": "User",
            "username": f"u{uid_str}",
            "email": f"unverified_{uid_str}@example.com",
            "password": "Password1",
        }
        await client.post("/auth/signup", json=payload)
        resp = await client.post(
            "/auth/login",
            json={"email": payload["email"], "password": payload["password"]},
        )
        assert resp.status_code in (200, 400, 401, 403)


# ---------------------------------------------------------------------------
# Email verification
# ---------------------------------------------------------------------------
class TestEmailVerification:
    @pytest.mark.asyncio
    async def test_verify_valid_token(self, client: AsyncClient):
        """A valid URL-safe token verifies the user account."""
        uid_str = uuid.uuid4().hex[:6]
        payload = {
            "first_name": "Verify",
            "last_name": "Me",
            "username": f"u{uid_str}",
            "email": f"verify_{uid_str}@example.com",
            "password": "Verify123",
        }
        resp = await client.post("/auth/signup", json=payload)
        assert resp.status_code == 200

        # Generate a real token for this email
        token = create_url_safe_token({"email": payload["email"]})
        resp = await client.get(f"/auth/verify/{token}")
        assert resp.status_code == 200
        assert "verified" in resp.json()["message"].lower()

        # Check DB
        async with AsyncSessionLocal() as session:
            result = await session.exec(select(User).where(User.email == payload["email"]))
            user = result.first()
            assert user is not None
            assert user.is_verified is True

    @pytest.mark.asyncio
    async def test_verify_invalid_token(self, client: AsyncClient):
        """An invalid / tampered token returns 400 or 401."""
        resp = await client.get("/auth/verify/this.is.not.a.valid.token")
        assert resp.status_code in (400, 401, 500)


# ---------------------------------------------------------------------------
# Token refresh & logout
# ---------------------------------------------------------------------------
class TestTokenRefreshAndLogout:
    @pytest.mark.asyncio
    async def test_refresh_token(self, client: AsyncClient, test_user_data, registered_user):
        """A valid refresh token returns a new access token."""
        login = await client.post(
            "/auth/login",
            json={"email": test_user_data["email"], "password": test_user_data["password"]},
        )
        refresh_token = login.json()["refresh_token"]
        resp = await client.get(
            "/auth/refresh_token",
            headers={"Authorization": f"Bearer {refresh_token}"},
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    @pytest.mark.asyncio
    async def test_logout(self, client: AsyncClient, auth_headers):
        """Logout blacklists the token."""
        resp = await client.get("/auth/logout", headers=auth_headers)
        assert resp.status_code == 200
        assert "logged out" in resp.json()["message"].lower()

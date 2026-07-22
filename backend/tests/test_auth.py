import pytest
from httpx import AsyncClient


class TestAuth:
    REGISTER_URL = "/api/v1/auth/register"
    LOGIN_URL = "/api/v1/auth/login"
    REFRESH_URL = "/api/v1/auth/refresh"
    ME_URL = "/api/v1/auth/me"

    @pytest.mark.asyncio
    async def test_register_success(self, client: AsyncClient):
        response = await client.post(
            self.REGISTER_URL,
            json={
                "first_name": "Test",
                "last_name": "Player",
                "nickname": "testy",
                "email": "test@example.com",
                "phone": "+27760000000",
                "password": "StrongP@ss1",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, client: AsyncClient):
        # Register first
        await client.post(
            self.REGISTER_URL,
            json={
                "first_name": "Test",
                "last_name": "Player",
                "email": "dup@example.com",
                "password": "StrongP@ss1",
            },
        )
        # Try duplicate
        response = await client.post(
            self.REGISTER_URL,
            json={
                "first_name": "Test",
                "last_name": "Player",
                "email": "dup@example.com",
                "password": "StrongP@ss1",
            },
        )
        assert response.status_code == 409
        assert "already registered" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_register_weak_password(self, client: AsyncClient):
        response = await client.post(
            self.REGISTER_URL,
            json={
                "first_name": "Test",
                "last_name": "Player",
                "email": "weak@example.com",
                "password": "short",
            },
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient):
        # Register
        await client.post(
            self.REGISTER_URL,
            json={
                "first_name": "Test",
                "last_name": "Player",
                "email": "login@example.com",
                "password": "StrongP@ss1",
            },
        )
        # Login
        response = await client.post(
            self.LOGIN_URL,
            json={"email": "login@example.com", "password": "StrongP@ss1"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client: AsyncClient):
        await client.post(
            self.REGISTER_URL,
            json={
                "first_name": "Test",
                "last_name": "Player",
                "email": "wrongpw@example.com",
                "password": "StrongP@ss1",
            },
        )
        response = await client.post(
            self.LOGIN_URL,
            json={"email": "wrongpw@example.com", "password": "WrongP@ss1"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_login_nonexistent_email(self, client: AsyncClient):
        response = await client.post(
            self.LOGIN_URL,
            json={"email": "nobody@example.com", "password": "StrongP@ss1"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_me_endpoint_authenticated(self, client: AsyncClient):
        # Register and get tokens
        reg_resp = await client.post(
            self.REGISTER_URL,
            json={
                "first_name": "Auth",
                "last_name": "User",
                "email": "authuser@example.com",
                "password": "StrongP@ss1",
            },
        )
        token = reg_resp.json()["access_token"]

        # Use token
        response = await client.get(
            self.ME_URL,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "authuser@example.com"
        assert data["first_name"] == "Auth"
        assert data["is_admin"] is False

    @pytest.mark.asyncio
    async def test_me_endpoint_unauthenticated(self, client: AsyncClient):
        response = await client.get(self.ME_URL)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_token(self, client: AsyncClient):
        # Register
        reg_resp = await client.post(
            self.REGISTER_URL,
            json={
                "first_name": "Refresh",
                "last_name": "Test",
                "email": "refresh@example.com",
                "password": "StrongP@ss1",
            },
        )
        refresh_token = reg_resp.json()["refresh_token"]

        # Use refresh token
        response = await client.post(
            self.REFRESH_URL,
            json={"refresh_token": refresh_token},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    @pytest.mark.asyncio
    async def test_refresh_invalid_token(self, client: AsyncClient):
        response = await client.post(
            self.REFRESH_URL,
            json={"refresh_token": "some.invalid.token"},
        )
        assert response.status_code == 401

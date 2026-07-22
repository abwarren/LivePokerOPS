import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Season, Tournament
from app.schemas.league import DEFAULT_POINTS_SCHEDULE


@pytest.mark.asyncio
class TestLeagueAPI:
    """League & Points integration tests."""

    # ─── Season CRUD ───

    async def test_create_season_unauthenticated(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/league/seasons",
            json={"name": "Season 1", "start_date": "2026-01-01T00:00:00Z", "end_date": "2026-06-30T00:00:00Z"},
        )
        assert resp.status_code == 401

    async def test_create_season_non_admin(self, client: AsyncClient, player_token: str):
        resp = await client.post(
            "/api/v1/league/seasons",
            headers={"Authorization": f"Bearer {player_token}"},
            json={"name": "Season 1", "start_date": "2026-01-01T00:00:00Z", "end_date": "2026-06-30T00:00:00Z"},
        )
        assert resp.status_code == 403

    async def test_create_season(self, client: AsyncClient, admin_token: str):
        resp = await client.post(
            "/api/v1/league/seasons",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "name": "Concept Heat 2 2026",
                "start_date": "2026-01-01T00:00:00Z",
                "end_date": "2026-12-31T00:00:00Z",
                "description": "Main competitive season",
                "attendance_points": 10,
                "final_table_bonus": 5,
                "points_schedule": {"1": 100, "2": 80, "3": 60, "4": 50, "5": 40, "6": 30, "7": 20, "8": 10, "9": 5},
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Concept Heat 2 2026"
        assert data["status"] == "upcoming"
        assert data["attendance_points"] == 10
        assert data["final_table_bonus"] == 5
        assert "id" in data

    async def test_create_season_bad_dates(self, client: AsyncClient, admin_token: str):
        resp = await client.post(
            "/api/v1/league/seasons",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": "Bad", "start_date": "2026-12-31T00:00:00Z", "end_date": "2026-01-01T00:00:00Z"},
        )
        assert resp.status_code == 400

    async def test_list_seasons(self, client: AsyncClient, admin_token: str):
        resp = await client.get(
            "/api/v1/league/seasons",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_get_season(self, client: AsyncClient, admin_token: str):
        # Create
        create_resp = await client.post(
            "/api/v1/league/seasons",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": "Get Test", "start_date": "2026-01-01T00:00:00Z", "end_date": "2026-06-30T00:00:00Z"},
        )
        sid = create_resp.json()["id"]

        resp = await client.get(
            f"/api/v1/league/seasons/{sid}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Get Test"
        assert "tournament_count" in resp.json()
        assert "player_count" in resp.json()

    async def test_get_season_not_found(self, client: AsyncClient, admin_token: str):
        resp = await client.get(
            f"/api/v1/league/seasons/{uuid.uuid4()}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 404

    async def test_update_season(self, client: AsyncClient, admin_token: str):
        create_resp = await client.post(
            "/api/v1/league/seasons",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": "Update Me", "start_date": "2026-01-01T00:00:00Z", "end_date": "2026-06-30T00:00:00Z"},
        )
        sid = create_resp.json()["id"]

        resp = await client.patch(
            f"/api/v1/league/seasons/{sid}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"status": "active"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"

    async def test_update_season_invalid_status(self, client: AsyncClient, admin_token: str):
        create_resp = await client.post(
            "/api/v1/league/seasons",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": "Bad Status", "start_date": "2026-01-01T00:00:00Z", "end_date": "2026-06-30T00:00:00Z"},
        )
        sid = create_resp.json()["id"]

        resp = await client.patch(
            f"/api/v1/league/seasons/{sid}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"status": "nonsense"},
        )
        assert resp.status_code == 422

    async def test_delete_season(self, client: AsyncClient, admin_token: str):
        create_resp = await client.post(
            "/api/v1/league/seasons",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": "Delete Me", "start_date": "2026-01-01T00:00:00Z", "end_date": "2026-06-30T00:00:00Z"},
        )
        sid = create_resp.json()["id"]

        resp = await client.delete(
            f"/api/v1/league/seasons/{sid}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 204

    # ─── Tournament Assignment ───

    async def test_assign_tournament_to_season(
        self, client: AsyncClient, admin_token: str
    ):
        # Create season
        s_resp = await client.post(
            "/api/v1/league/seasons",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": "Assign Test", "start_date": "2026-01-01T00:00:00Z", "end_date": "2026-06-30T00:00:00Z"},
        )
        sid = s_resp.json()["id"]

        # Create tournament
        t_resp = await client.post(
            "/api/v1/tournaments/",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": "R600 Turbo Heat 2"},
        )
        tid = t_resp.json()["id"]

        # Assign
        resp = await client.post(
            f"/api/v1/league/seasons/{sid}/tournaments",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"tournament_id": tid},
        )
        assert resp.status_code == 201
        assert resp.json()["tournament_id"] == tid

    async def test_assign_tournament_duplicate(
        self, client: AsyncClient, admin_token: str
    ):
        s_resp = await client.post(
            "/api/v1/league/seasons",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": "Dup Test", "start_date": "2026-01-01T00:00:00Z", "end_date": "2026-06-30T00:00:00Z"},
        )
        sid = s_resp.json()["id"]

        t_resp = await client.post(
            "/api/v1/tournaments/",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": "Tuesday Turbo"},
        )
        tid = t_resp.json()["id"]

        # First assign
        await client.post(
            f"/api/v1/league/seasons/{sid}/tournaments",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"tournament_id": tid},
        )

        # Duplicate
        resp = await client.post(
            f"/api/v1/league/seasons/{sid}/tournaments",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"tournament_id": tid},
        )
        assert resp.status_code == 409

    async def test_list_season_tournaments(
        self, client: AsyncClient, admin_token: str
    ):
        s_resp = await client.post(
            "/api/v1/league/seasons",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": "List T Test", "start_date": "2026-01-01T00:00:00Z", "end_date": "2026-06-30T00:00:00Z"},
        )
        sid = s_resp.json()["id"]

        t_resp = await client.post(
            "/api/v1/tournaments/",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": "Thursday Turbo"},
        )
        tid = t_resp.json()["id"]

        await client.post(
            f"/api/v1/league/seasons/{sid}/tournaments",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"tournament_id": tid},
        )

        resp = await client.get(
            f"/api/v1/league/seasons/{sid}/tournaments",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert len(resp.json()) >= 1
        assert resp.json()[0]["tournament_name"] == "Thursday Turbo"

    async def test_unassign_tournament(
        self, client: AsyncClient, admin_token: str
    ):
        s_resp = await client.post(
            "/api/v1/league/seasons",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": "Unassign Test", "start_date": "2026-01-01T00:00:00Z", "end_date": "2026-06-30T00:00:00Z"},
        )
        sid = s_resp.json()["id"]

        t_resp = await client.post(
            "/api/v1/tournaments/",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": "Unassign MTT"},
        )
        tid = t_resp.json()["id"]

        await client.post(
            f"/api/v1/league/seasons/{sid}/tournaments",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"tournament_id": tid},
        )

        resp = await client.delete(
            f"/api/v1/league/seasons/{sid}/tournaments/{tid}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 204

    # ─── Points & Leaderboard ───

    async def test_record_tournament_results(
        self, client: AsyncClient, admin_token: str
    ):
        # Create season
        s_resp = await client.post(
            "/api/v1/league/seasons",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "name": "Points Test Season",
                "start_date": "2026-01-01T00:00:00Z",
                "end_date": "2026-06-30T00:00:00Z",
                "points_schedule": DEFAULT_POINTS_SCHEDULE,
            },
        )
        sid = s_resp.json()["id"]

        # Create tournament
        t_resp = await client.post(
            "/api/v1/tournaments/",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": "Points Test MTT"},
        )
        tid = t_resp.json()["id"]

        # Assign tournament to season
        await client.post(
            f"/api/v1/league/seasons/{sid}/tournaments",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"tournament_id": tid},
        )

        # Register two players
        p1_resp = await client.post(
            "/api/v1/auth/register",
            json={"first_name": "Alice", "last_name": "Test", "email": f"alice-{uuid.uuid4().hex[:4]}@test.com", "password": "StrongP@ss1"},
        )
        p1_id = None  # We can't get player ID from register response easily
        # Get player ID from the player list
        players_resp = await client.get(
            "/api/v1/players/",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        players = players_resp.json()
        # Find alice
        alice = None
        bob = None
        for p in players:
            if p["email"].startswith("alice-"):
                alice = p["id"]
            if p["first_name"] == "Player":  # from conftest fixture
                bob = p["id"] if not bob else bob
        if alice is None:
            # Create via API but we need to find them... use admin token to get player list
            pass

        # Actually let's just use the players from registration
        # The admin token registration creates "Admin Test" player
        admin_resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        admin_player_id = admin_resp.json()["id"]

        # Register a custom player to use
        reg_resp = await client.post(
            "/api/v1/auth/register",
            json={"first_name": "Points", "last_name": "Player", "email": f"points-{uuid.uuid4().hex[:4]}@test.com", "password": "StrongP@ss1"},
        )
        player_token = reg_resp.json()["access_token"]
        me_resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {player_token}"},
        )
        player_id = me_resp.json()["id"]

        # Record results
        resp = await client.post(
            f"/api/v1/league/seasons/{sid}/tournaments/{tid}/results",
            headers={"Authorization": f"Bearer {admin_token}"},
            json=[
                {"player_id": admin_player_id, "position": 1, "points_earned": 0, "points_type": "finishing_position"},
                {"player_id": player_id, "position": 2, "points_earned": 0, "points_type": "finishing_position"},
            ],
        )
        assert resp.status_code == 201
        assert resp.json()["players"] == 2

    async def test_leaderboard(
        self, client: AsyncClient, admin_token: str
    ):
        # Create season
        s_resp = await client.post(
            "/api/v1/league/seasons",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "name": "LB Test Season",
                "start_date": "2026-01-01T00:00:00Z",
                "end_date": "2026-06-30T00:00:00Z",
            },
        )
        sid = s_resp.json()["id"]

        resp = await client.get(
            f"/api/v1/league/seasons/{sid}/leaderboard",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["season_id"] == sid
        assert "entries" in data

    async def test_default_points_schedule(self, client: AsyncClient):
        resp = await client.get("/api/v1/league/points-schedule/default")
        assert resp.status_code == 200
        data = resp.json()
        assert "schedule" in data
        assert data["schedule"]["1"] == 100

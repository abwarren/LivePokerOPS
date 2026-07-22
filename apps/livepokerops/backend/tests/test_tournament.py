import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestTournamentAPI:
    """Tournament CRUD + event logging."""

    async def test_create_tournament_unauthenticated(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/tournaments/",
            json={"name": "Test MTT"},
        )
        assert resp.status_code == 401

    async def test_create_tournament_non_admin(self, client: AsyncClient, player_token: str):
        resp = await client.post(
            "/api/v1/tournaments/",
            headers={"Authorization": f"Bearer {player_token}"},
            json={"name": "Test MTT"},
        )
        assert resp.status_code == 403

    async def test_create_tournament(self, client: AsyncClient, admin_token: str):
        resp = await client.post(
            "/api/v1/tournaments/",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "name": "Sunday Special",
                "buy_in": 350.00,
                "starting_stack": 50000,
                "min_players": 10,
                "max_players": 100,
                "late_reg_levels": 6,
                "notes": "Weekly Sunday tournament",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Sunday Special"
        assert data["status"] == "planned"
        assert float(data["buy_in"]) == 350.0
        assert data["starting_stack"] == 50000
        assert data["min_players"] == 10
        assert data["max_players"] == 100
        assert data["late_reg_levels"] == 6
        assert "id" in data
        assert data["notes"] == "Weekly Sunday tournament"

    async def test_create_tournament_duplicate_name_allowed(
        self, client: AsyncClient, admin_token: str
    ):
        """Names are not unique — duplicate names allowed."""
        resp1 = await client.post(
            "/api/v1/tournaments/",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": "Friday Freezeout"},
        )
        assert resp1.status_code == 201

        resp2 = await client.post(
            "/api/v1/tournaments/",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": "Friday Freezeout"},
        )
        assert resp2.status_code == 201

    async def test_create_tournament_empty_name(self, client: AsyncClient, admin_token: str):
        resp = await client.post(
            "/api/v1/tournaments/",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": ""},
        )
        assert resp.status_code == 422

    async def test_create_tournament_generates_event(self, client: AsyncClient, admin_token: str):
        resp = await client.post(
            "/api/v1/tournaments/",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": "Event Test"},
        )
        assert resp.status_code == 201
        tournament_id = resp.json()["id"]

        # Check event was created
        ev_resp = await client.get(
            f"/api/v1/tournaments/{tournament_id}/events",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert ev_resp.status_code == 200
        events = ev_resp.json()
        assert len(events) >= 1
        assert events[0]["event_type"] == "TOURNAMENT_CREATED"

    # ─── List tournaments ───

    async def test_list_tournaments_empty(self, client: AsyncClient, admin_token: str):
        resp = await client.get(
            "/api/v1/tournaments/",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        # Other tests may have created tournaments
        assert isinstance(resp.json(), list)

    async def test_list_tournaments_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/tournaments/")
        assert resp.status_code == 401

    async def test_list_tournaments_filtered_by_status(self, client: AsyncClient, admin_token: str):
        await client.post(
            "/api/v1/tournaments/",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": "Planned One"},
        )
        await client.post(
            "/api/v1/tournaments/",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": "Announced One"},
        )
        # Change second one to announced
        list_resp = await client.get(
            "/api/v1/tournaments/",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        tournaments = list_resp.json()
        announced = [t for t in tournaments if t["name"] == "Announced One"]
        if announced:
            tid = announced[0]["id"]
            await client.patch(
                f"/api/v1/tournaments/{tid}",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={"status": "announced"},
            )

        # Now filter
        resp = await client.get(
            "/api/v1/tournaments/?status=planned",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        for t in resp.json():
            assert t["status"] == "planned"

    # ─── Get single tournament ───

    async def test_get_tournament(self, client: AsyncClient, admin_token: str):
        create_resp = await client.post(
            "/api/v1/tournaments/",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": "Get Me"},
        )
        tid = create_resp.json()["id"]

        resp = await client.get(
            f"/api/v1/tournaments/{tid}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Get Me"

    async def test_get_tournament_not_found(self, client: AsyncClient, admin_token: str):
        resp = await client.get(
            f"/api/v1/tournaments/{uuid.uuid4()}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 404

    # ─── Update tournament ───

    async def test_update_tournament_status(self, client: AsyncClient, admin_token: str):
        create_resp = await client.post(
            "/api/v1/tournaments/",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": "Status Test"},
        )
        tid = create_resp.json()["id"]

        resp = await client.patch(
            f"/api/v1/tournaments/{tid}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"status": "in_progress"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "in_progress"

        # Check TOURNAMENT_STATUS_CHANGED event logged
        ev_resp = await client.get(
            f"/api/v1/tournaments/{tid}/events",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        types = [e["event_type"] for e in ev_resp.json()]
        assert "TOURNAMENT_STATUS_CHANGED" in types

    async def test_update_tournament_not_owner(self, client: AsyncClient, player_token: str):
        resp = await client.patch(
            f"/api/v1/tournaments/{uuid.uuid4()}",
            headers={"Authorization": f"Bearer {player_token}"},
            json={"name": "nope"},
        )
        assert resp.status_code == 403

    async def test_update_tournament_invalid_status(self, client: AsyncClient, admin_token: str):
        create_resp = await client.post(
            "/api/v1/tournaments/",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": "Bad Status"},
        )
        tid = create_resp.json()["id"]

        resp = await client.patch(
            f"/api/v1/tournaments/{tid}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"status": "flibbertigibbet"},
        )
        assert resp.status_code == 422

    async def test_update_tournament_not_found(self, client: AsyncClient, admin_token: str):
        resp = await client.patch(
            f"/api/v1/tournaments/{uuid.uuid4()}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": "Ghost"},
        )
        assert resp.status_code == 404

    # ─── Delete tournament ───

    async def test_delete_tournament(self, client: AsyncClient, admin_token: str):
        create_resp = await client.post(
            "/api/v1/tournaments/",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": "Delete Me"},
        )
        tid = create_resp.json()["id"]

        resp = await client.delete(
            f"/api/v1/tournaments/{tid}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 204

        # Confirm gone
        get_resp = await client.get(
            f"/api/v1/tournaments/{tid}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert get_resp.status_code == 404

    async def test_delete_tournament_not_found(self, client: AsyncClient, admin_token: str):
        resp = await client.delete(
            f"/api/v1/tournaments/{uuid.uuid4()}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 404

    async def test_delete_tournament_non_admin(self, client: AsyncClient, player_token: str):
        resp = await client.delete(
            f"/api/v1/tournaments/{uuid.uuid4()}",
            headers={"Authorization": f"Bearer {player_token}"},
        )
        assert resp.status_code == 403

    # ─── Event Log ───

    async def test_events_endpoint_requires_admin(self, client: AsyncClient):
        resp = await client.get("/api/v1/events/")
        assert resp.status_code == 401

    async def test_events_endpoint(self, client: AsyncClient, admin_token: str):
        resp = await client.get(
            "/api/v1/events/",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "events" in data
        assert "total" in data

    async def test_events_filtered_by_type(self, client: AsyncClient, admin_token: str):
        resp = await client.get(
            "/api/v1/events/?event_type=TOURNAMENT_CREATED",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for e in data["events"]:
            assert e["event_type"] == "TOURNAMENT_CREATED"

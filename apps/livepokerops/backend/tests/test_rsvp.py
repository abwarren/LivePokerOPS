import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestRsvpAPI:
    """RSVP system: tournament registration with waitlist support."""

    async def _create_tournament(
        self, client: AsyncClient, token: str, name: str = "Test Tournament",
        max_players: int | None = 5,
    ) -> dict:
        payload = {"name": name}
        if max_players is not None:
            payload["max_players"] = max_players
        resp = await client.post(
            "/api/v1/tournaments/",
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
        )
        assert resp.status_code == 201, f"Tournament creation failed: {resp.text}"
        return resp.json()

    # ─── Authentication ───

    async def test_create_rsvp_unauthenticated(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/tournaments/00000000-0000-0000-0000-000000000000/rsvps/",
            json={"tournament_id": "00000000-0000-0000-0000-000000000000"},
        )
        assert resp.status_code == 401

    async def test_list_rsvps_unauthenticated(self, client: AsyncClient):
        resp = await client.get(
            "/api/v1/tournaments/00000000-0000-0000-0000-000000000000/rsvps/",
        )
        assert resp.status_code == 401

    async def test_stats_unauthenticated(self, client: AsyncClient):
        resp = await client.get(
            "/api/v1/tournaments/00000000-0000-0000-0000-000000000000/rsvps/stats",
        )
        assert resp.status_code == 401

    # ─── Basic RSVP ───

    async def test_player_can_rsvp_to_tournament(
        self, client: AsyncClient, admin_token: str, player_token: str,
    ):
        tournament = await self._create_tournament(client, admin_token)
        tid = tournament["id"]

        resp = await client.post(
            f"/api/v1/tournaments/{tid}/rsvps/",
            headers={"Authorization": f"Bearer {player_token}"},
            json={"tournament_id": tid, "notes": "Looking forward to it!"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "confirmed"
        assert data["tournament_id"] == tid
        assert data["notes"] == "Looking forward to it!"
        assert data["player_name"] == "Player Test"
        assert "id" in data

    async def test_duplicate_rsvp_returns_existing(
        self, client: AsyncClient, admin_token: str, player_token: str,
    ):
        tournament = await self._create_tournament(client, admin_token)
        tid = tournament["id"]

        # First RSVP
        resp1 = await client.post(
            f"/api/v1/tournaments/{tid}/rsvps/",
            headers={"Authorization": f"Bearer {player_token}"},
            json={"tournament_id": tid},
        )
        assert resp1.status_code == 201

        # Duplicate RSVP — should return existing without error
        resp2 = await client.post(
            f"/api/v1/tournaments/{tid}/rsvps/",
            headers={"Authorization": f"Bearer {player_token}"},
            json={"tournament_id": tid},
        )
        assert resp2.status_code == 201
        assert resp2.json()["status"] == "confirmed"

    # ─── Waitlisting ───

    async def test_waitlisting_when_full(
        self, client: AsyncClient, admin_token: str,
    ):
        # Create tournament with max_players=1
        tournament = await self._create_tournament(
            client, admin_token, name="Full Test", max_players=1,
        )
        tid = tournament["id"]

        # Register first player
        resp1 = await client.post(
            "/api/v1/auth/register",
            json={
                "first_name": "Alice",
                "last_name": "Player",
                "email": "alice-waitlist@test.com",
                "password": "StrongP@ss1",
            },
        )
        assert resp1.status_code == 201
        alice_token = resp1.json()["access_token"]

        resp_alice = await client.post(
            f"/api/v1/tournaments/{tid}/rsvps/",
            headers={"Authorization": f"Bearer {alice_token}"},
            json={"tournament_id": tid},
        )
        assert resp_alice.status_code == 201
        assert resp_alice.json()["status"] == "confirmed"

        # Register second player — should be waitlisted
        resp2 = await client.post(
            "/api/v1/auth/register",
            json={
                "first_name": "Bob",
                "last_name": "Player",
                "email": "bob-waitlist@test.com",
                "password": "StrongP@ss1",
            },
        )
        assert resp2.status_code == 201
        bob_token = resp2.json()["access_token"]

        resp_bob = await client.post(
            f"/api/v1/tournaments/{tid}/rsvps/",
            headers={"Authorization": f"Bearer {bob_token}"},
            json={"tournament_id": tid},
        )
        assert resp_bob.status_code == 201
        assert resp_bob.json()["status"] == "waiting"

    async def test_promotion_from_waitlist(
        self, client: AsyncClient, admin_token: str,
    ):
        # Create tournament with max_players=1
        tournament = await self._create_tournament(
            client, admin_token, name="Promotion Test", max_players=1,
        )
        tid = tournament["id"]

        # Register Alice (confirmed)
        resp1 = await client.post(
            "/api/v1/auth/register",
            json={
                "first_name": "AliceP",
                "last_name": "Player",
                "email": "alice-promo@test.com",
                "password": "StrongP@ss1",
            },
        )
        alice_token = resp1.json()["access_token"]

        await client.post(
            f"/api/v1/tournaments/{tid}/rsvps/",
            headers={"Authorization": f"Bearer {alice_token}"},
            json={"tournament_id": tid},
        )

        # Register Bob (waiting)
        resp2 = await client.post(
            "/api/v1/auth/register",
            json={
                "first_name": "BobP",
                "last_name": "Player",
                "email": "bob-promo@test.com",
                "password": "StrongP@ss1",
            },
        )
        bob_token = resp2.json()["access_token"]

        await client.post(
            f"/api/v1/tournaments/{tid}/rsvps/",
            headers={"Authorization": f"Bearer {bob_token}"},
            json={"tournament_id": tid},
        )

        # Alice cancels — Bob should be promoted
        # Get Alice's player_id
        list_resp = await client.get(
            f"/api/v1/tournaments/{tid}/rsvps/",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        alice_rsvp = [r for r in list_resp.json() if r["player_name"] == "AliceP Player"][0]
        alice_id = alice_rsvp["player_id"]

        cancel_resp = await client.delete(
            f"/api/v1/tournaments/{tid}/rsvps/{alice_id}",
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        assert cancel_resp.status_code == 200
        assert cancel_resp.json()["status"] == "cancelled"

        # Check Bob is now confirmed
        list_resp2 = await client.get(
            f"/api/v1/tournaments/{tid}/rsvps/",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        bob_rsvp = [r for r in list_resp2.json() if r["player_name"] == "BobP Player"][0]
        assert bob_rsvp["status"] == "confirmed"

    async def test_cancel_and_promotion(
        self, client: AsyncClient, admin_token: str, player_token: str,
    ):
        tournament = await self._create_tournament(
            client, admin_token, name="Cancel Test", max_players=3,
        )
        tid = tournament["id"]

        # Create RSVP as player
        resp = await client.post(
            f"/api/v1/tournaments/{tid}/rsvps/",
            headers={"Authorization": f"Bearer {player_token}"},
            json={"tournament_id": tid},
        )
        assert resp.status_code == 201
        player_id = resp.json()["player_id"]

        # Cancel
        cancel_resp = await client.delete(
            f"/api/v1/tournaments/{tid}/rsvps/{player_id}",
            headers={"Authorization": f"Bearer {player_token}"},
        )
        assert cancel_resp.status_code == 200
        assert cancel_resp.json()["status"] == "cancelled"

    # ─── Stats ───

    async def test_stats_endpoint(
        self, client: AsyncClient, admin_token: str, player_token: str,
    ):
        tournament = await self._create_tournament(
            client, admin_token, name="Stats Test", max_players=10,
        )
        tid = tournament["id"]

        resp = await client.get(
            f"/api/v1/tournaments/{tid}/rsvps/stats",
            headers={"Authorization": f"Bearer {player_token}"},
        )
        assert resp.status_code == 200
        stats = resp.json()
        assert stats["total_confirmed"] == 0
        assert stats["total_waiting"] == 0
        assert stats["total_cancelled"] == 0
        assert stats["capacity_remaining"] == 10

        # Add an RSVP and check stats again
        await client.post(
            f"/api/v1/tournaments/{tid}/rsvps/",
            headers={"Authorization": f"Bearer {player_token}"},
            json={"tournament_id": tid},
        )

        resp2 = await client.get(
            f"/api/v1/tournaments/{tid}/rsvps/stats",
            headers={"Authorization": f"Bearer {player_token}"},
        )
        stats2 = resp2.json()
        assert stats2["total_confirmed"] == 1
        assert stats2["capacity_remaining"] == 9

    # ─── List with status filter ───

    async def test_list_rsvps_filtered_by_status(
        self, client: AsyncClient, admin_token: str, player_token: str,
    ):
        tournament = await self._create_tournament(
            client, admin_token, name="Filter Test", max_players=5,
        )
        tid = tournament["id"]

        # Player RSVPs
        await client.post(
            f"/api/v1/tournaments/{tid}/rsvps/",
            headers={"Authorization": f"Bearer {player_token}"},
            json={"tournament_id": tid},
        )

        # List with status=confirmed
        resp = await client.get(
            f"/api/v1/tournaments/{tid}/rsvps/?status=confirmed",
            headers={"Authorization": f"Bearer {player_token}"},
        )
        assert resp.status_code == 200
        for r in resp.json():
            assert r["status"] == "confirmed"

    # ─── My RSVPs ───

    async def test_my_rsvps(
        self, client: AsyncClient, admin_token: str, player_token: str,
    ):
        tournament = await self._create_tournament(
            client, admin_token, name="My RSVPs Test",
        )
        tid = tournament["id"]

        await client.post(
            f"/api/v1/tournaments/{tid}/rsvps/",
            headers={"Authorization": f"Bearer {player_token}"},
            json={"tournament_id": tid},
        )

        resp = await client.get(
            "/api/v1/tournaments/00000000-0000-0000-0000-000000000000/rsvps/my",
            headers={"Authorization": f"Bearer {player_token}"},
        )
        assert resp.status_code == 200
        assert len(resp.json()) >= 1
        assert resp.json()[0]["tournament_name"] == "My RSVPs Test"

    # ─── Admin promote endpoint ───

    async def test_admin_promote_waitlist(
        self, client: AsyncClient, admin_token: str,
    ):
        tournament = await self._create_tournament(
            client, admin_token, name="Admin Promote", max_players=1,
        )
        tid = tournament["id"]

        # Alice registered (confirmed)
        resp1 = await client.post(
            "/api/v1/auth/register",
            json={
                "first_name": "AliceAP",
                "last_name": "Player",
                "email": "alice-admin-promote@test.com",
                "password": "StrongP@ss1",
            },
        )
        alice_token = resp1.json()["access_token"]

        await client.post(
            f"/api/v1/tournaments/{tid}/rsvps/",
            headers={"Authorization": f"Bearer {alice_token}"},
            json={"tournament_id": tid},
        )

        # Bob registered (waiting)
        resp2 = await client.post(
            "/api/v1/auth/register",
            json={
                "first_name": "BobAP",
                "last_name": "Player",
                "email": "bob-admin-promote@test.com",
                "password": "StrongP@ss1",
            },
        )
        bob_token = resp2.json()["access_token"]

        await client.post(
            f"/api/v1/tournaments/{tid}/rsvps/",
            headers={"Authorization": f"Bearer {bob_token}"},
            json={"tournament_id": tid},
        )

        # Alice cancels (frees a spot)
        list_resp = await client.get(
            f"/api/v1/tournaments/{tid}/rsvps/",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        alice_rsvp = [r for r in list_resp.json() if r["player_name"] == "AliceAP Player"][0]

        await client.delete(
            f"/api/v1/tournaments/{tid}/rsvps/{alice_rsvp['player_id']}",
            headers={"Authorization": f"Bearer {alice_token}"},
        )

        # Admin promote — Bob was already auto-promoted when Alice cancelled
        promote_resp = await client.post(
            f"/api/v1/tournaments/{tid}/rsvps/promote",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert promote_resp.status_code == 200
        assert promote_resp.json()["promoted"] == 0

    # ─── Player update own RSVP ───

    async def test_player_can_update_own_rsvp(
        self, client: AsyncClient, admin_token: str, player_token: str,
    ):
        tournament = await self._create_tournament(client, admin_token, max_players=5)
        tid = tournament["id"]

        # Create RSVP
        resp = await client.post(
            f"/api/v1/tournaments/{tid}/rsvps/",
            headers={"Authorization": f"Bearer {player_token}"},
            json={"tournament_id": tid},
        )
        player_id = resp.json()["player_id"]

        # Cancel via PATCH
        patch_resp = await client.patch(
            f"/api/v1/tournaments/{tid}/rsvps/{player_id}",
            headers={"Authorization": f"Bearer {player_token}"},
            json={"status": "cancelled"},
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["status"] == "cancelled"

    async def test_player_cannot_update_other_rsvp(
        self, client: AsyncClient, admin_token: str,
    ):
        tournament = await self._create_tournament(client, admin_token, max_players=5)
        tid = tournament["id"]

        resp1 = await client.post(
            "/api/v1/auth/register",
            json={
                "first_name": "AliceX",
                "last_name": "Player",
                "email": "alice-cannot-update@test.com",
                "password": "StrongP@ss1",
            },
        )
        alice_token = resp1.json()["access_token"]

        resp2 = await client.post(
            "/api/v1/auth/register",
            json={
                "first_name": "BobX",
                "last_name": "Player",
                "email": "bob-cannot-update@test.com",
                "password": "StrongP@ss1",
            },
        )
        bob_token = resp2.json()["access_token"]

        # Alice RSVPs
        alice_resp = await client.post(
            f"/api/v1/tournaments/{tid}/rsvps/",
            headers={"Authorization": f"Bearer {alice_token}"},
            json={"tournament_id": tid},
        )
        alice_player_id = alice_resp.json()["player_id"]

        # Bob tries to cancel Alice's RSVP
        patch_resp = await client.patch(
            f"/api/v1/tournaments/{tid}/rsvps/{alice_player_id}",
            headers={"Authorization": f"Bearer {bob_token}"},
            json={"status": "cancelled"},
        )
        assert patch_resp.status_code == 403

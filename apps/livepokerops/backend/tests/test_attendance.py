import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestAttendanceAPI:
    """Attendance check-in CRUD + stats."""

    async def _create_tournament(self, client: AsyncClient, admin_token: str) -> str:
        resp = await client.post(
            "/api/v1/tournaments/",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": "Attendance Test MTT"},
        )
        assert resp.status_code == 201
        return resp.json()["id"]

    async def _register_player(
        self, client: AsyncClient, email_suffix: str
    ) -> str:
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "first_name": "Attend",
                "last_name": "Test",
                "email": f"attend-{email_suffix}@test.com",
                "password": "StrongP@ss1",
            },
        )
        assert resp.status_code == 201
        return resp.json()["player_id"]

    # ─── Check-in ───

    async def test_check_in_unauthenticated(self, client: AsyncClient):
        resp = await client.post(
            f"/api/v1/tournaments/{uuid.uuid4()}/attendance/check-in",
            json={"player_id": str(uuid.uuid4())},
        )
        assert resp.status_code == 401

    async def test_check_in_non_admin(self, client: AsyncClient, player_token: str):
        resp = await client.post(
            f"/api/v1/tournaments/{uuid.uuid4()}/attendance/check-in",
            headers={"Authorization": f"Bearer {player_token}"},
            json={"player_id": str(uuid.uuid4())},
        )
        assert resp.status_code == 403

    async def test_check_in(self, client: AsyncClient, admin_token: str):
        tid = await self._create_tournament(client, admin_token)
        pid = await self._register_player(client, "checkin")

        resp = await client.post(
            f"/api/v1/tournaments/{tid}/attendance/check-in",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"player_id": pid},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "checked_in"
        assert data["tournament_id"] == tid
        assert data["player_id"] == pid
        assert data["checked_in_at"] is not None
        assert "id" in data

    async def test_check_in_duplicate(self, client: AsyncClient, admin_token: str):
        tid = await self._create_tournament(client, admin_token)
        pid = await self._register_player(client, "dupe")

        # First check-in
        resp1 = await client.post(
            f"/api/v1/tournaments/{tid}/attendance/check-in",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"player_id": pid},
        )
        assert resp1.status_code == 201

        # Duplicate check-in
        resp2 = await client.post(
            f"/api/v1/tournaments/{tid}/attendance/check-in",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"player_id": pid},
        )
        assert resp2.status_code == 409

    async def test_check_in_nonexistent_tournament(
        self, client: AsyncClient, admin_token: str
    ):
        resp = await client.post(
            f"/api/v1/tournaments/{uuid.uuid4()}/attendance/check-in",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"player_id": str(uuid.uuid4())},
        )
        assert resp.status_code == 404

    # ─── No-show ───

    async def test_mark_no_show(self, client: AsyncClient, admin_token: str):
        tid = await self._create_tournament(client, admin_token)
        pid = await self._register_player(client, "noshow")

        # Check in first
        await client.post(
            f"/api/v1/tournaments/{tid}/attendance/check-in",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"player_id": pid},
        )

        # Mark no-show
        resp = await client.post(
            f"/api/v1/tournaments/{tid}/attendance/no-show/{pid}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "no_show"

    async def test_mark_no_show_non_existent(
        self, client: AsyncClient, admin_token: str
    ):
        tid = await self._create_tournament(client, admin_token)
        resp = await client.post(
            f"/api/v1/tournaments/{tid}/attendance/no-show/{uuid.uuid4()}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 404

    async def test_mark_no_show_unauthenticated(self, client: AsyncClient):
        resp = await client.post(
            f"/api/v1/tournaments/{uuid.uuid4()}/attendance/no-show/{uuid.uuid4()}",
        )
        assert resp.status_code == 401

    async def test_mark_no_show_non_admin(
        self, client: AsyncClient, player_token: str
    ):
        resp = await client.post(
            f"/api/v1/tournaments/{uuid.uuid4()}/attendance/no-show/{uuid.uuid4()}",
            headers={"Authorization": f"Bearer {player_token}"},
        )
        assert resp.status_code == 403

    # ─── Update ───

    async def test_update_attendance(self, client: AsyncClient, admin_token: str):
        tid = await self._create_tournament(client, admin_token)
        pid = await self._register_player(client, "update")

        # Check in
        await client.post(
            f"/api/v1/tournaments/{tid}/attendance/check-in",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"player_id": pid},
        )

        # Update to late cancellation
        resp = await client.patch(
            f"/api/v1/tournaments/{tid}/attendance/{pid}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"status": "late_cancellation", "notes": "Had an emergency"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "late_cancellation"
        assert data["notes"] == "Had an emergency"

    async def test_update_attendance_invalid_status(
        self, client: AsyncClient, admin_token: str
    ):
        tid = await self._create_tournament(client, admin_token)
        pid = await self._register_player(client, "badstatus")

        # Check in
        await client.post(
            f"/api/v1/tournaments/{tid}/attendance/check-in",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"player_id": pid},
        )

        resp = await client.patch(
            f"/api/v1/tournaments/{tid}/attendance/{pid}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"status": "invalid_status"},
        )
        assert resp.status_code == 422

    # ─── List ───

    async def test_list_attendance(self, client: AsyncClient, admin_token: str):
        tid = await self._create_tournament(client, admin_token)
        pid1 = await self._register_player(client, "list1")
        pid2 = await self._register_player(client, "list2")

        # Check in two players
        await client.post(
            f"/api/v1/tournaments/{tid}/attendance/check-in",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"player_id": pid1},
        )
        await client.post(
            f"/api/v1/tournaments/{tid}/attendance/check-in",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"player_id": pid2},
        )

        resp = await client.get(
            f"/api/v1/tournaments/{tid}/attendance/",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    async def test_list_attendance_empty(
        self, client: AsyncClient, admin_token: str
    ):
        tid = await self._create_tournament(client, admin_token)
        resp = await client.get(
            f"/api/v1/tournaments/{tid}/attendance/",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_attendance_unauthenticated(self, client: AsyncClient):
        resp = await client.get(
            f"/api/v1/tournaments/{uuid.uuid4()}/attendance/",
        )
        assert resp.status_code == 401

    async def test_list_attendance_filtered(
        self, client: AsyncClient, admin_token: str
    ):
        tid = await self._create_tournament(client, admin_token)
        pid = await self._register_player(client, "filter")

        # Check in, then mark no-show
        await client.post(
            f"/api/v1/tournaments/{tid}/attendance/check-in",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"player_id": pid},
        )
        await client.post(
            f"/api/v1/tournaments/{tid}/attendance/no-show/{pid}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        # Filter by no_show
        resp = await client.get(
            f"/api/v1/tournaments/{tid}/attendance/?status=no_show",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        for r in resp.json():
            assert r["status"] == "no_show"

    # ─── Stats ───

    async def test_attendance_stats(self, client: AsyncClient, admin_token: str):
        tid = await self._create_tournament(client, admin_token)
        pid1 = await self._register_player(client, "stat1")
        pid2 = await self._register_player(client, "stat2")
        pid3 = await self._register_player(client, "stat3")

        # Check in 2 players
        for pid in [pid1, pid2]:
            await client.post(
                f"/api/v1/tournaments/{tid}/attendance/check-in",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={"player_id": pid},
            )

        # Mark one as no-show
        await client.post(
            f"/api/v1/tournaments/{tid}/attendance/no-show/{pid1}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        # Also check in a third
        await client.post(
            f"/api/v1/tournaments/{tid}/attendance/check-in",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"player_id": pid3},
        )

        resp = await client.get(
            f"/api/v1/tournaments/{tid}/attendance/stats",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        stats = resp.json()
        assert stats["total_players"] == 3
        assert stats["checked_in"] == 2  # pid2 and pid3
        assert stats["no_shows"] == 1  # pid1
        assert stats["late_cancellations"] == 0

    async def test_attendance_stats_empty(
        self, client: AsyncClient, admin_token: str
    ):
        tid = await self._create_tournament(client, admin_token)
        resp = await client.get(
            f"/api/v1/tournaments/{tid}/attendance/stats",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        stats = resp.json()
        assert stats["total_players"] == 0
        assert stats["check_in_rate"] == 0.0

    # ─── Bulk check-in ───

    async def test_bulk_check_in(self, client: AsyncClient, admin_token: str):
        tid = await self._create_tournament(client, admin_token)
        pid1 = await self._register_player(client, "bulk1")
        pid2 = await self._register_player(client, "bulk2")

        resp = await client.post(
            f"/api/v1/tournaments/{tid}/attendance/bulk-check-in",
            headers={"Authorization": f"Bearer {admin_token}"},
            json=[{"player_id": pid1}, {"player_id": pid2}],
        )
        assert resp.status_code == 201
        data = resp.json()
        assert len(data) == 2
        assert data[0]["status"] == "checked_in"
        assert data[1]["status"] == "checked_in"

    async def test_bulk_check_in_unauthenticated(self, client: AsyncClient):
        resp = await client.post(
            f"/api/v1/tournaments/{uuid.uuid4()}/attendance/bulk-check-in",
            json=[{"player_id": str(uuid.uuid4())}],
        )
        assert resp.status_code == 401

    async def test_bulk_check_in_non_admin(
        self, client: AsyncClient, player_token: str
    ):
        resp = await client.post(
            f"/api/v1/tournaments/{uuid.uuid4()}/attendance/bulk-check-in",
            headers={"Authorization": f"Bearer {player_token}"},
            json=[{"player_id": str(uuid.uuid4())}],
        )
        assert resp.status_code == 403

import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestBroadcastAPI:
    """Full pipeline test for the broadcast system."""

    # ─── Auth & Permissions ───

    async def test_categories_public(self, client: AsyncClient):
        """Categories endpoint should be public."""
        resp = await client.get("/api/v1/broadcast/categories")
        assert resp.status_code == 200
        data = resp.json()
        assert "categories" in data
        assert len(data["categories"]) > 0

    async def test_templates_requires_auth(self, client: AsyncClient):
        """Templates endpoint should require authentication."""
        resp = await client.get("/api/v1/broadcast/templates")
        assert resp.status_code == 401

    async def test_templates_requires_admin(self, client: AsyncClient, player_token: str):
        """Non-admin should get 403."""
        resp = await client.get(
            "/api/v1/broadcast/templates",
            headers={"Authorization": f"Bearer {player_token}"},
        )
        assert resp.status_code == 403

    async def test_broadcast_history_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/broadcast/history")
        assert resp.status_code == 401

    async def test_broadcast_stats_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/broadcast/stats")
        assert resp.status_code == 401

    # ─── Template CRUD ───

    async def test_list_templates(self, client: AsyncClient, admin_token: str, seed_templates):
        resp = await client.get(
            "/api/v1/broadcast/templates",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 2
        names = [t["name"] for t in data]
        assert "test_announcement" in names
        assert "test_reminder" in names

    async def test_list_templates_filtered_by_category(
        self, client: AsyncClient, admin_token: str, seed_templates
    ):
        resp = await client.get(
            "/api/v1/broadcast/templates?category=reminder",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert all(t["category"] == "reminder" for t in data)

    async def test_get_template(self, client: AsyncClient, admin_token: str, seed_templates):
        tmpl_id = seed_templates[0].id
        resp = await client.get(
            f"/api/v1/broadcast/templates/{tmpl_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "test_announcement"

    async def test_get_template_not_found(self, client: AsyncClient, admin_token: str):
        resp = await client.get(
            f"/api/v1/broadcast/templates/{uuid.uuid4()}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 404

    async def test_create_template(self, client: AsyncClient, admin_token: str):
        resp = await client.post(
            "/api/v1/broadcast/templates",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "name": "new_test_template",
                "description": "Created during test",
                "category": "announcement",
                "body_template": "Hello {name}!",
                "variables": ["name"],
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "new_test_template"
        assert data["category"] == "announcement"

    async def test_create_template_duplicate_name(
        self, client: AsyncClient, admin_token: str, seed_templates
    ):
        resp = await client.post(
            "/api/v1/broadcast/templates",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "name": "test_announcement",
                "category": "announcement",
                "body_template": "Test body",
            },
        )
        assert resp.status_code == 409

    async def test_update_template(self, client: AsyncClient, admin_token: str, seed_templates):
        tmpl_id = seed_templates[1].id
        resp = await client.put(
            f"/api/v1/broadcast/templates/{tmpl_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "name": "updated_reminder",
                "description": "Updated",
                "category": "announcement",
                "body_template": "Updated: {tournament} at {time}",
                "variables": ["tournament", "time"],
            },
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "updated_reminder"

    async def test_update_template_not_found(self, client: AsyncClient, admin_token: str):
        resp = await client.put(
            f"/api/v1/broadcast/templates/{uuid.uuid4()}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": "nope"},
        )
        assert resp.status_code == 404

    async def test_delete_custom_template(
        self, client: AsyncClient, admin_token: str, seed_templates
    ):
        # seed_templates[1] is is_builtin=False
        tmpl_id = seed_templates[1].id
        resp = await client.delete(
            f"/api/v1/broadcast/templates/{tmpl_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 204

    async def test_delete_builtin_template_denied(
        self, client: AsyncClient, admin_token: str, seed_templates
    ):
        # seed_templates[0] is is_builtin=True
        tmpl_id = seed_templates[0].id
        resp = await client.delete(
            f"/api/v1/broadcast/templates/{tmpl_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 403

    # ─── Preview & Send ───

    async def test_preview_template(self, client: AsyncClient, admin_token: str, seed_templates):
        tmpl_id = seed_templates[0].id
        resp = await client.post(
            "/api/v1/broadcast/preview",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "template_id": str(tmpl_id),
                "variables": {
                    "time": "7PM", "date": "Friday", "player_count": 24,
                    "player_list": ["Alice", "Bob"],
                },
            },
        )
        assert resp.status_code == 200
        body = resp.json()["rendered_body"]
        assert "7PM" in body
        assert "Friday" in body
        assert "24" in body
        assert "Alice" in body
        assert "Bob" in body

    async def test_preview_template_not_found(self, client: AsyncClient, admin_token: str):
        resp = await client.post(
            "/api/v1/broadcast/preview",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "template_id": str(uuid.uuid4()),
                "variables": {"time": "7PM"},
            },
        )
        assert resp.status_code == 404

    async def test_send_broadcast(self, client: AsyncClient, admin_token: str, seed_templates):
        tmpl_id = seed_templates[0].id
        resp = await client.post(
            "/api/v1/broadcast/send",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "template_id": str(tmpl_id),
                "subject": "Test Send",
                "variables": {
                    "time": "7PM", "date": "Friday", "player_count": 24,
                    "player_list": ["Alice"],
                },
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["subject"] == "Test Send"
        assert data["status"] in ("pending", "sent", "partial", "failed")
        assert "id" in data

    async def test_send_manual_broadcast(self, client: AsyncClient, admin_token: str):
        resp = await client.post(
            "/api/v1/broadcast/send-manual",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "subject": "Manual Test",
                "body": "This is a manual message body",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] in ("pending", "sent", "partial", "failed")

    # ─── History & Stats ───

    async def test_broadcast_history(self, client: AsyncClient, admin_token: str, seed_templates):
        # Send first to populate history
        tmpl_id = seed_templates[0].id
        await client.post(
            "/api/v1/broadcast/send",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "template_id": str(tmpl_id),
                "subject": "History Test",
                "variables": {
                    "time": "8PM", "date": "Saturday", "player_count": 10,
                    "player_list": ["Bob"],
                },
            },
        )

        resp = await client.get(
            "/api/v1/broadcast/history",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1

    async def test_broadcast_detail(self, client: AsyncClient, admin_token: str, seed_templates):
        tmpl_id = seed_templates[0].id
        send_resp = await client.post(
            "/api/v1/broadcast/send",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "template_id": str(tmpl_id),
                "subject": "Detail Test",
                "variables": {
                    "time": "9PM", "date": "Sunday", "player_count": 5,
                    "player_list": ["Charlie"],
                },
            },
        )
        broadcast_id = send_resp.json()["id"]

        resp = await client.get(
            f"/api/v1/broadcast/history/{broadcast_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == broadcast_id
        assert "recipients" in data
        assert data["subject"] == "Detail Test"

    async def test_broadcast_stats(self, client: AsyncClient, admin_token: str, seed_templates):
        tmpl_id = seed_templates[0].id
        await client.post(
            "/api/v1/broadcast/send",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "template_id": str(tmpl_id),
                "subject": "Stats Test",
                "variables": {
                    "time": "10PM", "date": "Monday", "player_count": 8,
                    "player_list": ["Dave"],
                },
            },
        )

        resp = await client.get(
            "/api/v1/broadcast/stats",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert "by_status" in data

    # ─── Scheduled Send ───

    async def test_send_scheduled_broadcast(
        self, client: AsyncClient, admin_token: str, seed_templates
    ):
        tmpl_id = seed_templates[0].id
        from datetime import datetime, timedelta, timezone

        future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        resp = await client.post(
            "/api/v1/broadcast/send",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "template_id": str(tmpl_id),
                "subject": "Scheduled Test",
                "variables": {
                    "time": "11PM", "date": "Tuesday", "player_count": 3,
                    "player_list": ["Eve"],
                },
                "scheduled_for": future,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "scheduled"

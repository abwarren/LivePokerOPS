import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestFinanceAPI:
    """Financial tracking — buy-ins, prize pools, summaries."""

    async def _create_tournament(
        self, client: AsyncClient, token: str, name: str = "Test Tournament"
    ) -> dict:
        resp = await client.post(
            "/api/v1/tournaments/",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "name": name,
                "buy_in": 350.00,
                "starting_stack": 50000,
            },
        )
        assert resp.status_code == 201
        return resp.json()

    async def _create_player_and_get_id(
        self, client: AsyncClient, email: str
    ) -> str:
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "first_name": "Finance",
                "last_name": "Test",
                "email": email,
                "password": "StrongP@ss1",
            },
        )
        assert resp.status_code == 201
        token = resp.json()["access_token"]
        # Get player details from /me endpoint
        me_resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_resp.status_code == 200
        return me_resp.json()["id"]

    # ─── Auth guards ───

    async def test_record_buy_in_unauthenticated(self, client: AsyncClient):
        resp = await client.post(
            f"/api/v1/tournaments/{uuid.uuid4()}/finances/buy-ins",
            json={"player_id": str(uuid.uuid4()), "amount": 350.00},
        )
        assert resp.status_code == 401

    async def test_record_buy_in_non_admin(
        self, client: AsyncClient, player_token: str
    ):
        resp = await client.post(
            f"/api/v1/tournaments/{uuid.uuid4()}/finances/buy-ins",
            headers={"Authorization": f"Bearer {player_token}"},
            json={"player_id": str(uuid.uuid4()), "amount": 350.00},
        )
        assert resp.status_code == 403

    async def test_list_buy_ins_unauthenticated(self, client: AsyncClient):
        resp = await client.get(
            f"/api/v1/tournaments/{uuid.uuid4()}/finances/buy-ins",
        )
        assert resp.status_code == 401

    async def test_prize_pool_unauthenticated(self, client: AsyncClient):
        resp = await client.get(
            f"/api/v1/tournaments/{uuid.uuid4()}/finances/prize-pool",
        )
        assert resp.status_code == 401

    async def test_overview_unauthenticated(self, client: AsyncClient):
        resp = await client.get(
            f"/api/v1/tournaments/{uuid.uuid4()}/finances/overview",
        )
        assert resp.status_code == 401

    async def test_overview_non_admin(
        self, client: AsyncClient, player_token: str
    ):
        resp = await client.get(
            f"/api/v1/tournaments/{uuid.uuid4()}/finances/overview",
            headers={"Authorization": f"Bearer {player_token}"},
        )
        assert resp.status_code == 403

    # ─── Record buy-ins ───

    async def test_record_buy_in(
        self, client: AsyncClient, admin_token: str
    ):
        tournament = await self._create_tournament(client, admin_token)
        player_id = await self._create_player_and_get_id(
            client, "finance-buyin@test.com"
        )

        resp = await client.post(
            f"/api/v1/tournaments/{tournament['id']}/finances/buy-ins",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "player_id": player_id,
                "amount": 350.00,
                "type": "buy_in",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["player_id"] == player_id
        assert float(data["amount"]) == 350.0
        assert data["type"] == "buy_in"
        assert data["tournament_id"] == tournament["id"]
        assert "player_name" in data
        assert "id" in data
        assert "created_at" in data

    async def test_record_rebuy(
        self, client: AsyncClient, admin_token: str
    ):
        tournament = await self._create_tournament(
            client, admin_token, "Rebuy Test"
        )
        player_id = await self._create_player_and_get_id(
            client, "finance-rebuy@test.com"
        )

        resp = await client.post(
            f"/api/v1/tournaments/{tournament['id']}/finances/buy-ins",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "player_id": player_id,
                "amount": 350.00,
                "type": "re_buy",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["type"] == "re_buy"

    async def test_record_addon(
        self, client: AsyncClient, admin_token: str
    ):
        tournament = await self._create_tournament(
            client, admin_token, "Addon Test"
        )
        player_id = await self._create_player_and_get_id(
            client, "finance-addon@test.com"
        )

        resp = await client.post(
            f"/api/v1/tournaments/{tournament['id']}/finances/buy-ins",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "player_id": player_id,
                "amount": 100.00,
                "type": "add_on",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["type"] == "add_on"

    async def test_record_buy_in_invalid_type(
        self, client: AsyncClient, admin_token: str
    ):
        tournament = await self._create_tournament(
            client, admin_token, "Invalid Type"
        )
        player_id = await self._create_player_and_get_id(
            client, "finance-invalid@test.com"
        )

        resp = await client.post(
            f"/api/v1/tournaments/{tournament['id']}/finances/buy-ins",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "player_id": player_id,
                "amount": 100.00,
                "type": "payout",
            },
        )
        assert resp.status_code == 422  # Pydantic validation

    async def test_record_buy_in_zero_amount(
        self, client: AsyncClient, admin_token: str
    ):
        tournament = await self._create_tournament(
            client, admin_token, "Zero Amount"
        )
        player_id = await self._create_player_and_get_id(
            client, "finance-zero@test.com"
        )

        resp = await client.post(
            f"/api/v1/tournaments/{tournament['id']}/finances/buy-ins",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "player_id": player_id,
                "amount": 0,
                "type": "buy_in",
            },
        )
        assert resp.status_code == 422  # gt=0 validation

    async def test_record_buy_in_tournament_not_found(
        self, client: AsyncClient, admin_token: str
    ):
        player_id = await self._create_player_and_get_id(
            client, "finance-404@test.com"
        )
        resp = await client.post(
            f"/api/v1/tournaments/{uuid.uuid4()}/finances/buy-ins",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "player_id": player_id,
                "amount": 350.00,
                "type": "buy_in",
            },
        )
        assert resp.status_code == 404

    async def test_record_buy_in_player_not_found(
        self, client: AsyncClient, admin_token: str
    ):
        tournament = await self._create_tournament(
            client, admin_token, "Player Not Found"
        )
        resp = await client.post(
            f"/api/v1/tournaments/{tournament['id']}/finances/buy-ins",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "player_id": str(uuid.uuid4()),
                "amount": 350.00,
                "type": "buy_in",
            },
        )
        assert resp.status_code == 404

    # ─── Bulk buy-ins ───

    async def test_record_bulk_buy_ins(
        self, client: AsyncClient, admin_token: str
    ):
        tournament = await self._create_tournament(
            client, admin_token, "Bulk Buy-ins"
        )
        p1 = await self._create_player_and_get_id(
            client, "bulk1@test.com"
        )
        p2 = await self._create_player_and_get_id(
            client, "bulk2@test.com"
        )

        resp = await client.post(
            f"/api/v1/tournaments/{tournament['id']}/finances/bulk-buy-ins",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "entries": [
                    {"player_id": p1, "amount": 350.00, "type": "buy_in"},
                    {"player_id": p2, "amount": 350.00, "type": "buy_in"},
                    {"player_id": p1, "amount": 200.00, "type": "re_buy"},
                ]
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert len(data) == 3

    # ─── List buy-ins ───

    async def test_list_buy_ins(
        self, client: AsyncClient, admin_token: str
    ):
        tournament = await self._create_tournament(
            client, admin_token, "List Buy-ins"
        )
        p1 = await self._create_player_and_get_id(
            client, "list1@test.com"
        )
        p2 = await self._create_player_and_get_id(
            client, "list2@test.com"
        )

        # Record some buy-ins
        await client.post(
            f"/api/v1/tournaments/{tournament['id']}/finances/buy-ins",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"player_id": p1, "amount": 350.00, "type": "buy_in"},
        )
        await client.post(
            f"/api/v1/tournaments/{tournament['id']}/finances/buy-ins",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"player_id": p2, "amount": 350.00, "type": "buy_in"},
        )

        resp = await client.get(
            f"/api/v1/tournaments/{tournament['id']}/finances/buy-ins",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        for b in data:
            assert float(b["amount"]) in (350.0,)
            assert b["type"] == "buy_in"
            assert b["player_name"] is not None

    # ─── Prize pool ───

    async def test_prize_pool_is_auto_calculated(
        self, client: AsyncClient, admin_token: str
    ):
        tournament = await self._create_tournament(
            client, admin_token, "Prize Pool Auto"
        )
        p1 = await self._create_player_and_get_id(
            client, "pp1@test.com"
        )
        p2 = await self._create_player_and_get_id(
            client, "pp2@test.com"
        )
        p3 = await self._create_player_and_get_id(
            client, "pp3@test.com"
        )

        # 3 buy-ins + 1 rebuy + 1 addon
        for pid in [p1, p2, p3]:
            await client.post(
                f"/api/v1/tournaments/{tournament['id']}/finances/buy-ins",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={"player_id": pid, "amount": 350.00, "type": "buy_in"},
            )

        await client.post(
            f"/api/v1/tournaments/{tournament['id']}/finances/buy-ins",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"player_id": p1, "amount": 350.00, "type": "re_buy"},
        )

        await client.post(
            f"/api/v1/tournaments/{tournament['id']}/finances/buy-ins",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"player_id": p2, "amount": 100.00, "type": "add_on"},
        )

        resp = await client.get(
            f"/api/v1/tournaments/{tournament['id']}/finances/prize-pool",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert float(data["total_buy_in"]) == 1050.0  # 3 * 350
        assert float(data["total_rebuys"]) == 350.0
        assert float(data["total_addons"]) == 100.0
        assert float(data["total_prize_pool"]) == 1500.0  # 1050 + 350 + 100
        assert data["entries_count"] == 3  # 3 unique buy_in players
        assert data["tournament_name"] == "Prize Pool Auto"
        assert float(data["average_buy_in"]) == 500.0  # 1500 / 3

    async def test_prize_pool_not_found(
        self, client: AsyncClient, admin_token: str
    ):
        tournament = await self._create_tournament(
            client, admin_token, "No Finances"
        )
        resp = await client.get(
            f"/api/v1/tournaments/{tournament['id']}/finances/prize-pool",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 404

    # ─── Player finances ───

    async def test_get_player_finances(
        self, client: AsyncClient, admin_token: str
    ):
        tournament = await self._create_tournament(
            client, admin_token, "Player Finances"
        )
        p1 = await self._create_player_and_get_id(
            client, "pf1@test.com"
        )
        p2 = await self._create_player_and_get_id(
            client, "pf2@test.com"
        )

        # Player 1: buy-in + rebuy
        await client.post(
            f"/api/v1/tournaments/{tournament['id']}/finances/buy-ins",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"player_id": p1, "amount": 350.00, "type": "buy_in"},
        )
        await client.post(
            f"/api/v1/tournaments/{tournament['id']}/finances/buy-ins",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"player_id": p1, "amount": 350.00, "type": "re_buy"},
        )
        # Player 2: just a buy-in
        await client.post(
            f"/api/v1/tournaments/{tournament['id']}/finances/buy-ins",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"player_id": p2, "amount": 350.00, "type": "buy_in"},
        )

        resp = await client.get(
            f"/api/v1/tournaments/{tournament['id']}/finances/players/{p1}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["buy_ins"]) == 2
        assert float(data["total_spent"]) == 700.0
        assert data["player_id"] == p1
        assert data["player_name"] == "Finance Test"

    # ─── Financial overview (cross-tournament) ───

    async def test_get_overall_summary(
        self, client: AsyncClient, admin_token: str
    ):
        t1 = await self._create_tournament(
            client, admin_token, "Overview T1"
        )
        t2 = await self._create_tournament(
            client, admin_token, "Overview T2"
        )
        p1 = await self._create_player_and_get_id(
            client, "overview1@test.com"
        )
        p2 = await self._create_player_and_get_id(
            client, "overview2@test.com"
        )

        # T1: 2 buy-ins
        for pid in [p1, p2]:
            await client.post(
                f"/api/v1/tournaments/{t1['id']}/finances/buy-ins",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={"player_id": pid, "amount": 350.00, "type": "buy_in"},
            )

        # T2: 1 buy-in + 1 rebuy
        await client.post(
            f"/api/v1/tournaments/{t2['id']}/finances/buy-ins",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"player_id": p1, "amount": 350.00, "type": "buy_in"},
        )
        await client.post(
            f"/api/v1/tournaments/{t2['id']}/finances/buy-ins",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"player_id": p2, "amount": 200.00, "type": "re_buy"},
        )

        # Use T1's ID for the overview endpoint (it ignores the path param)
        resp = await client.get(
            f"/api/v1/tournaments/{t1['id']}/finances/overview",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()

        # Grand totals
        assert float(data["total_buy_ins"]) == 1050.0  # 3 * 350
        assert float(data["total_rebuys"]) == 200.0
        assert float(data["total_addons"]) == 0.0
        assert float(data["total_prize_pool"]) == 1250.0  # 1050 + 200
        assert data["tournament_count"] == 2
        assert isinstance(data["tournaments"], list)
        assert len(data["tournaments"]) == 2

    # ─── Round-trip decimal precision ───

    async def test_decimal_precision(
        self, client: AsyncClient, admin_token: str
    ):
        """Money amounts must not lose precision (test with .99 amounts)."""
        tournament = await self._create_tournament(
            client, admin_token, "Decimal Precision"
        )
        p1 = await self._create_player_and_get_id(
            client, "dec1@test.com"
        )
        p2 = await self._create_player_and_get_id(
            client, "dec2@test.com"
        )

        await client.post(
            f"/api/v1/tournaments/{tournament['id']}/finances/buy-ins",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"player_id": p1, "amount": 0.99, "type": "buy_in"},
        )
        await client.post(
            f"/api/v1/tournaments/{tournament['id']}/finances/buy-ins",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"player_id": p2, "amount": 19.99, "type": "buy_in"},
        )

        pp_resp = await client.get(
            f"/api/v1/tournaments/{tournament['id']}/finances/prize-pool",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        pp = pp_resp.json()
        assert float(pp["total_prize_pool"]) == 20.98  # 0.99 + 19.99
        assert float(pp["average_buy_in"]) == 10.49  # 20.98 / 2

    # ─── Negative / edge cases ───

    async def test_record_buy_in_negative_amount(
        self, client: AsyncClient, admin_token: str
    ):
        tournament = await self._create_tournament(
            client, admin_token, "Negative Amount"
        )
        player_id = await self._create_player_and_get_id(
            client, "negative@test.com"
        )
        resp = await client.post(
            f"/api/v1/tournaments/{tournament['id']}/finances/buy-ins",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "player_id": player_id,
                "amount": -50.00,
                "type": "buy_in",
            },
        )
        assert resp.status_code == 422

    async def test_list_buy_ins_empty(
        self, client: AsyncClient, admin_token: str
    ):
        tournament = await self._create_tournament(
            client, admin_token, "Empty Finances"
        )
        resp = await client.get(
            f"/api/v1/tournaments/{tournament['id']}/finances/buy-ins",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.json() == []

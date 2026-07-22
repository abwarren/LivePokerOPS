import pytest

from app.services.message_provider import ConsoleMessageProvider


@pytest.mark.asyncio
class TestConsoleProvider:
    async def test_send_message_returns_success(self):
        provider = ConsoleMessageProvider()
        result = await provider.send_message("+27760000000", "Test message", "Subject")
        assert result["status"] == "sent"
        assert result["channel"] == "console"
        assert "message_id" in result

    async def test_send_bulk_returns_per_recipient(self):
        provider = ConsoleMessageProvider()
        recipients = [
            {"phone": "+27760000001", "player_id": "uuid-1"},
            {"phone": "+27760000002", "player_id": "uuid-2"},
        ]
        results = await provider.send_bulk(recipients, "Test body")
        assert len(results) == 2
        for r in results:
            assert r["status"] == "sent"
            assert r["player_id"] in ("uuid-1", "uuid-2")

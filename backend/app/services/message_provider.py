from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


class MessageProvider(ABC):
    """Abstract interface for message delivery providers."""

    @abstractmethod
    async def send_message(self, to: str, body: str, subject: str | None = None) -> dict[str, Any]:
        """Send a message to a single recipient.
        
        Returns: dict with at minimum {"message_id": str, "status": "sent|failed"}
        """
        ...

    @abstractmethod
    async def send_bulk(
        self, recipients: list[dict[str, Any]], body: str, subject: str | None = None
    ) -> list[dict[str, Any]]:
        """Send a message to multiple recipients.
        
        Each recipient dict has at minimum {"phone": str, "player_id": str}
        Returns list of per-recipient delivery results.
        """
        ...


class ConsoleMessageProvider(MessageProvider):
    """Dev/console provider — logs messages to console.
    
    Use this during development before WhatsApp Cloud API is set up.
    """

    async def send_message(self, to: str, body: str, subject: str | None = None) -> dict[str, Any]:
        logger.info(
            "console_message_send",
            to=to,
            subject=subject,
            body_length=len(body),
            body_preview=body[:200],
        )
        return {"message_id": "console-msg", "status": "sent", "channel": "console"}

    async def send_bulk(
        self, recipients: list[dict[str, Any]], body: str, subject: str | None = None
    ) -> list[dict[str, Any]]:
        results = []
        for r in recipients:
            result = await self.send_message(r.get("phone", r.get("player_id", "unknown")), body, subject)
            results.append({**result, "player_id": r.get("player_id")})
        return results


class WhatsAppCloudProvider(MessageProvider):
    """WhatsApp Cloud API provider.
    
    Requires META_WHATSAPP_TOKEN and META_WHATSAPP_PHONE_NUMBER_ID env vars.
    """

    def __init__(self, api_token: str, phone_number_id: str):
        self.api_token = api_token
        self.phone_number_id = phone_number_id
        self.base_url = f"https://graph.facebook.com/v21.0/{phone_number_id}"

    async def send_message(self, to: str, body: str, subject: str | None = None) -> dict[str, Any]:
        import httpx

        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": body, "preview_url": False},
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/messages",
                headers={
                    "Authorization": f"Bearer {self.api_token}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )

        if response.is_success:
            data = response.json()
            msg_id = data.get("messages", [{}])[0].get("id", "unknown")
            return {"message_id": msg_id, "status": "sent", "channel": "whatsapp"}
        else:
            logger.error("whatsapp_send_failed", to=to, status=response.status_code, error=response.text)
            return {"message_id": "", "status": "failed", "error": response.text, "channel": "whatsapp"}

    async def send_bulk(
        self, recipients: list[dict[str, Any]], body: str, subject: str | None = None
    ) -> list[dict[str, Any]]:
        results = []
        for r in recipients:
            phone = r.get("phone")
            if not phone:
                results.append({"status": "failed", "error": "No phone number", "player_id": r.get("player_id")})
                continue
            result = await self.send_message(phone, body, subject)
            results.append({**result, "player_id": r.get("player_id")})
        return results


def get_message_provider() -> MessageProvider:
    """Factory: returns the configured message provider.
    
    Falls back to ConsoleMessageProvider if WhatsApp Cloud API is not configured.
    """
    from app.core.config import get_settings

    settings = get_settings()
    
    whatsapp_token = getattr(settings, "whatsapp_api_key", None) or ""
    whatsapp_phone = getattr(settings, "whatsapp_phone_number_id", None) or ""

    if whatsapp_token and whatsapp_phone:
        return WhatsAppCloudProvider(whatsapp_token, whatsapp_phone)
    
    logger.info("using_console_provider — no WhatsApp credentials configured")
    return ConsoleMessageProvider()

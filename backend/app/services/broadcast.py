from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models import MessageTemplate, Broadcast, BroadcastRecipient, Player
from app.services.template_engine import TemplateEngine
from app.services.message_provider import get_message_provider, MessageProvider

logger = get_logger(__name__)


class BroadcastService:
    """Orchestrates message template rendering and delivery."""

    def __init__(self, db: AsyncSession, provider: MessageProvider | None = None):
        self.db = db
        self.provider = provider or get_message_provider()

    async def get_template(self, template_id: uuid.UUID) -> MessageTemplate | None:
        result = await self.db.execute(
            select(MessageTemplate).where(MessageTemplate.id == template_id)
        )
        return result.scalar_one_or_none()

    async def list_templates(self, category: str | None = None) -> list[MessageTemplate]:
        query = select(MessageTemplate).order_by(MessageTemplate.name)
        if category:
            query = query.where(MessageTemplate.category == category)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def create_template(
        self, name: str, body_template: str, category: str,
        description: str | None = None, variables: list[str] | None = None
    ) -> MessageTemplate:
        # Auto-extract variables if not provided
        if variables is None:
            variables = TemplateEngine.extract_variables(body_template)

        tmpl = MessageTemplate(
            name=name,
            description=description,
            category=category,
            body_template=body_template,
            variables=variables,
            is_builtin=False,
        )
        self.db.add(tmpl)
        await self.db.flush()
        return tmpl

    async def update_template(
        self, template_id: uuid.UUID, **kwargs
    ) -> MessageTemplate | None:
        tmpl = await self.get_template(template_id)
        if tmpl is None:
            return None
        for key, value in kwargs.items():
            if value is not None and hasattr(tmpl, key):
                setattr(tmpl, key, value)
        # Re-extract variables if body changed
        if "body_template" in kwargs and kwargs["body_template"] is not None:
            if "variables" not in kwargs or kwargs["variables"] is None:
                tmpl.variables = TemplateEngine.extract_variables(tmpl.body_template)
        self.db.add(tmpl)
        await self.db.flush()
        return tmpl

    async def delete_template(self, template_id: uuid.UUID) -> bool:
        tmpl = await self.get_template(template_id)
        if tmpl is None or tmpl.is_builtin:
            return False
        await self.db.delete(tmpl)
        await self.db.flush()
        return True

    async def preview(self, template_id: uuid.UUID, variables: dict[str, Any]) -> str | None:
        tmpl = await self.get_template(template_id)
        if tmpl is None:
            return None
        return TemplateEngine.preview(tmpl.body_template, variables)

    async def send(
        self,
        template_id: uuid.UUID,
        variables: dict[str, Any],
        subject: str = "",
        player_ids: list[uuid.UUID] | None = None,
        sent_by: uuid.UUID | None = None,
        scheduled_for: datetime | None = None,
    ) -> Broadcast | None:
        tmpl = await self.get_template(template_id)
        if tmpl is None:
            return None

        # Render
        rendered_body = TemplateEngine.preview(tmpl.body_template, variables)
        if not subject:
            subject = tmpl.name.replace("_", " ").title()

        # Get recipients
        if player_ids:
            result = await self.db.execute(
                select(Player).where(
                    Player.id.in_(player_ids),
                    Player.is_active == True,
                )
            )
            target_players = list(result.scalars().all())
        else:
            result = await self.db.execute(
                select(Player).where(Player.is_active == True)
            )
            target_players = list(result.scalars().all())

        if not target_players:
            logger.warning("send_no_recipients", template=tmpl.name)
            return None

        # Create broadcast record
        broadcast = Broadcast(
            template_id=template_id,
            subject=subject,
            rendered_body=rendered_body,
            variables_used=variables,
            status="scheduled" if scheduled_for else "pending",
            scheduled_for=scheduled_for,
            sent_by=sent_by,
        )
        self.db.add(broadcast)
        await self.db.flush()

        # Add recipient records
        for player in target_players:
            recipient = BroadcastRecipient(
                broadcast_id=broadcast.id,
                player_id=player.id,
                channel="whatsapp",
                status="pending",
            )
            self.db.add(recipient)
        await self.db.flush()

        # If scheduled, don't send now
        if scheduled_for:
            broadcast.status = "scheduled"
            self.db.add(broadcast)
            await self.db.flush()
            return broadcast

        # Send immediately
        await self._dispatch(broadcast, target_players)

        return broadcast

    async def send_manual(
        self,
        subject: str,
        body: str,
        player_ids: list[uuid.UUID] | None = None,
        sent_by: uuid.UUID | None = None,
    ) -> Broadcast:
        """Send a manual one-off message without a template."""
        if player_ids:
            result = await self.db.execute(
                select(Player).where(
                    Player.id.in_(player_ids),
                    Player.is_active == True,
                )
            )
            target_players = list(result.scalars().all())
        else:
            result = await self.db.execute(
                select(Player).where(Player.is_active == True)
            )
            target_players = list(result.scalars().all())

        broadcast = Broadcast(
            template_id=None,
            subject=subject,
            rendered_body=body,
            status="pending",
            sent_by=sent_by,
        )
        self.db.add(broadcast)
        await self.db.flush()

        for player in target_players:
            recipient = BroadcastRecipient(
                broadcast_id=broadcast.id,
                player_id=player.id,
                channel="whatsapp",
                status="pending",
            )
            self.db.add(recipient)
        await self.db.flush()

        await self._dispatch(broadcast, target_players)
        return broadcast

    async def _dispatch(self, broadcast: Broadcast, players: list[Player]) -> None:
        """Actually send messages and update delivery status."""
        recipients_data = [
            {"phone": p.phone or "", "player_id": str(p.id), "name": f"{p.first_name} {p.last_name}"}
            for p in players
        ]

        # Filter out players without phone numbers
        valid = [r for r in recipients_data if r["phone"]]

        if not valid:
            logger.warning("no_phone_numbers", broadcast_id=broadcast.id)
            broadcast.status = "failed"
            broadcast.error_message = "No recipients with phone numbers"
            self.db.add(broadcast)
            await self.db.flush()
            return

        # Send via provider
        try:
            results = await self.provider.send_bulk(
                valid, broadcast.rendered_body, broadcast.subject
            )
        except Exception as e:
            logger.error("dispatch_failed", broadcast_id=str(broadcast.id), error=str(e))
            broadcast.status = "failed"
            broadcast.error_message = str(e)
            self.db.add(broadcast)
            await self.db.flush()
            return

        # Update recipient statuses
        success_count = 0
        fail_count = 0
        for result in results:
            player_id_str = result.get("player_id", "")
            if not player_id_str:
                continue
            try:
                pid = uuid.UUID(player_id_str)
            except ValueError:
                continue

            status = result.get("status", "failed")
            error = result.get("error")

            if status == "sent":
                success_count += 1
                await self.db.execute(
                    update(BroadcastRecipient)
                    .where(
                        BroadcastRecipient.broadcast_id == broadcast.id,
                        BroadcastRecipient.player_id == pid,
                    )
                    .values(
                        status="delivered",
                        delivered_at=datetime.now(timezone.utc),
                    )
                )
            else:
                fail_count += 1
                await self.db.execute(
                    update(BroadcastRecipient)
                    .where(
                        BroadcastRecipient.broadcast_id == broadcast.id,
                        BroadcastRecipient.player_id == pid,
                    )
                    .values(
                        status="failed",
                        error_message=error,
                    )
                )

        broadcast.status = "sent"
        broadcast.sent_at = datetime.now(timezone.utc)
        if fail_count > 0 and success_count > 0:
            broadcast.status = "partial"
            broadcast.error_message = f"{fail_count} of {len(results)} failed"
        elif fail_count > 0:
            broadcast.status = "failed"
        self.db.add(broadcast)
        await self.db.flush()

        logger.info(
            "broadcast_sent",
            broadcast_id=str(broadcast.id),
            success=success_count,
            failed=fail_count,
            total=len(results),
        )

    async def get_broadcast(self, broadcast_id: uuid.UUID) -> Broadcast | None:
        result = await self.db.execute(
            select(Broadcast).where(Broadcast.id == broadcast_id)
        )
        return result.scalar_one_or_none()

    async def list_broadcasts(
        self, status: str | None = None, category: str | None = None,
        limit: int = 20, offset: int = 0,
    ) -> list[Broadcast]:
        query = select(Broadcast).order_by(Broadcast.created_at.desc())
        if status:
            query = query.where(Broadcast.status == status)
        if category and category != "all":
            # Join templates to filter by category
            query = query.join(MessageTemplate).where(
                MessageTemplate.category == category
            )
        query = query.offset(offset).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_broadcast_stats(self) -> dict[str, Any]:
        """Get aggregate broadcast stats."""
        total = await self.db.execute(select(func.count(Broadcast.id)))
        by_status = await self.db.execute(
            select(Broadcast.status, func.count(Broadcast.id))
            .group_by(Broadcast.status)
        )
        return {
            "total": total.scalar() or 0,
            "by_status": dict(by_status.all()),
        }

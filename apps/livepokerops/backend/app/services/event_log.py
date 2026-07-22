from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.event_log import EventLog

logger = get_logger(__name__)

EVENT_TYPES = frozenset({
    "TOURNAMENT_CREATED",
    "TOURNAMENT_UPDATED",
    "TOURNAMENT_STATUS_CHANGED",
    "TOURNAMENT_DELETED",
})


class EventLogService:
    """Write and query event log entries."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def log(
        self,
        event_type: str,
        source: str = "api",
        tournament_id: uuid.UUID | None = None,
        actor_id: uuid.UUID | None = None,
        payload: dict | None = None,
    ) -> EventLog:
        if event_type not in EVENT_TYPES:
            logger.warning("unknown_event_type", event_type=event_type)

        entry = EventLog(
            event_type=event_type,
            source=source,
            tournament_id=tournament_id,
            actor_id=actor_id,
            payload=payload or {},
        )
        self.db.add(entry)
        await self.db.flush()
        return entry

    async def get_events(
        self,
        tournament_id: uuid.UUID | None = None,
        event_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EventLog]:
        query = select(EventLog).order_by(EventLog.created_at.desc())
        if tournament_id:
            query = query.where(EventLog.tournament_id == tournament_id)
        if event_type:
            query = query.where(EventLog.event_type == event_type)
        query = query.offset(offset).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def count_events(
        self,
        tournament_id: uuid.UUID | None = None,
        event_type: str | None = None,
    ) -> int:
        query = select(func.count(EventLog.id))
        if tournament_id:
            query = query.where(EventLog.tournament_id == tournament_id)
        if event_type:
            query = query.where(EventLog.event_type == event_type)
        result = await self.db.execute(query)
        return result.scalar() or 0

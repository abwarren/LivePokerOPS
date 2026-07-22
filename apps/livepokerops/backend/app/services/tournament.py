from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.tournament import Tournament
from app.schemas.tournament import TournamentCreate, TournamentUpdate
from app.services.event_log import EventLogService

logger = get_logger(__name__)

VALID_STATUSES = frozenset({
    "planned", "announced", "in_progress", "paused", "completed", "cancelled",
})


class TournamentService:
    """Tournament lifecycle management."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.events = EventLogService(db)

    async def create(
        self, data: TournamentCreate, actor_id: uuid.UUID | None = None
    ) -> Tournament:
        tournament = Tournament(**data.model_dump())
        self.db.add(tournament)
        await self.db.flush()

        await self.events.log(
            event_type="TOURNAMENT_CREATED",
            tournament_id=tournament.id,
            actor_id=actor_id,
            payload={"name": data.name},
        )
        return tournament

    async def get(self, tournament_id: uuid.UUID) -> Tournament:
        result = await self.db.execute(
            select(Tournament).where(Tournament.id == tournament_id)
        )
        t = result.scalar_one_or_none()
        if t is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Tournament not found"
            )
        return t

    async def list_tournaments(
        self, status_filter: str | None = None, limit: int = 100, offset: int = 0
    ) -> list[Tournament]:
        query = select(Tournament).order_by(Tournament.created_at.desc())
        if status_filter:
            if status_filter not in VALID_STATUSES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status: {status_filter}. "
                    f"Valid: {', '.join(sorted(VALID_STATUSES))}",
                )
            query = query.where(Tournament.status == status_filter)
        query = query.offset(offset).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update(
        self,
        tournament_id: uuid.UUID,
        data: TournamentUpdate,
        actor_id: uuid.UUID | None = None,
    ) -> Tournament:
        tournament = await self.get(tournament_id)
        changed = {}
        for field, value in data.model_dump(exclude_unset=True).items():
            if value is not None:
                setattr(tournament, field, value)
                changed[field] = str(value)

        if "status" in changed:
            await self.events.log(
                event_type="TOURNAMENT_STATUS_CHANGED",
                tournament_id=tournament_id,
                actor_id=actor_id,
                payload={"status": changed["status"]},
            )
        else:
            await self.events.log(
                event_type="TOURNAMENT_UPDATED",
                tournament_id=tournament_id,
                actor_id=actor_id,
                payload=changed,
            )

        tournament.updated_at = datetime.now(timezone.utc)
        self.db.add(tournament)
        await self.db.flush()
        return tournament

    async def delete(
        self, tournament_id: uuid.UUID, actor_id: uuid.UUID | None = None
    ) -> None:
        tournament = await self.get(tournament_id)
        await self.db.delete(tournament)
        await self.db.flush()

        await self.events.log(
            event_type="TOURNAMENT_DELETED",
            tournament_id=tournament_id,
            actor_id=actor_id,
            payload={"name": tournament.name},
        )

    async def count(self, status_filter: str | None = None) -> int:
        query = select(func.count(Tournament.id))
        if status_filter:
            query = query.where(Tournament.status == status_filter)
        result = await self.db.execute(query)
        return result.scalar() or 0

    # ─── Archive / Search ───

    async def search_tournaments(
        self,
        query_str: str | None = None,
        status_filter: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[Tournament], int]:
        """Full-text search tournaments with filters. Returns (results, total)."""
        query = select(Tournament).order_by(Tournament.created_at.desc())
        count_query = select(func.count(Tournament.id))

        if query_str:
            like = f"%{query_str}%"
            filter_clause = or_(
                Tournament.name.ilike(like),
                Tournament.notes.ilike(like),
            )
            query = query.where(filter_clause)
            count_query = count_query.where(filter_clause)

        if status_filter:
            if status_filter not in VALID_STATUSES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status: {status_filter}. "
                    f"Valid: {', '.join(sorted(VALID_STATUSES))}",
                )
            query = query.where(Tournament.status == status_filter)
            count_query = count_query.where(Tournament.status == status_filter)

        if date_from:
            query = query.where(Tournament.start_time >= date_from)
            count_query = count_query.where(Tournament.start_time >= date_from)

        if date_to:
            query = query.where(Tournament.start_time <= date_to)
            count_query = count_query.where(Tournament.start_time <= date_to)

        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        query = query.offset(offset).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def get_upcoming(self, days: int = 7, limit: int = 20) -> list[Tournament]:
        """Get upcoming tournaments within the next N days."""
        now = datetime.now(timezone.utc)
        deadline = now + timedelta(days=days)
        result = await self.db.execute(
            select(Tournament)
            .where(
                Tournament.start_time >= now,
                Tournament.start_time <= deadline,
                Tournament.status.in_(["planned", "announced"]),
            )
            .order_by(Tournament.start_time.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_recent_completed(
        self, limit: int = 20
    ) -> list[Tournament]:
        """Get recently completed tournaments."""
        result = await self.db.execute(
            select(Tournament)
            .where(Tournament.status == "completed")
            .order_by(Tournament.updated_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_completed_count(self) -> int:
        """Count completed tournaments."""
        result = await self.db.execute(
            select(func.count(Tournament.id)).where(
                Tournament.status == "completed"
            )
        )
        return result.scalar() or 0

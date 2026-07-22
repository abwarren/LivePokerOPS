from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.models.attendance import Attendance
from app.models.player import Player
from app.models.tournament import Tournament
from app.services.event_log import EventLogService

logger = get_logger(__name__)

VALID_STATUSES = frozenset({"checked_in", "no_show", "late_cancellation"})


class AttendanceService:
    """Attendance & check-in management for tournaments."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.events = EventLogService(db)

    async def _get_tournament(self, tournament_id: uuid.UUID) -> Tournament:
        result = await self.db.execute(
            select(Tournament).where(Tournament.id == tournament_id)
        )
        t = result.scalar_one_or_none()
        if t is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Tournament not found"
            )
        return t

    async def _get_player(self, player_id: uuid.UUID) -> Player:
        result = await self.db.execute(
            select(Player).where(Player.id == player_id)
        )
        p = result.scalar_one_or_none()
        if p is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Player not found"
            )
        return p

    async def _get_or_create_attendance(
        self, tournament_id: uuid.UUID, player_id: uuid.UUID
    ) -> Attendance:
        """Return existing attendance record or raise 404."""
        result = await self.db.execute(
            select(Attendance).where(
                Attendance.tournament_id == tournament_id,
                Attendance.player_id == player_id,
            )
        )
        record = result.scalar_one_or_none()
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Attendance record not found",
            )
        return record

    async def check_in(
        self,
        tournament_id: uuid.UUID,
        player_id: uuid.UUID,
        actor_id: uuid.UUID | None = None,
    ) -> Attendance:
        """Mark a player as checked in for a tournament."""
        await self._get_tournament(tournament_id)
        await self._get_player(player_id)

        # Check if already checked in
        existing = await self.db.execute(
            select(Attendance).where(
                Attendance.tournament_id == tournament_id,
                Attendance.player_id == player_id,
            )
        )
        record = existing.scalar_one_or_none()
        if record is not None:
            if record.status == "checked_in":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Player is already checked in for this tournament",
                )
            # Update existing record
            record.status = "checked_in"
            record.checked_in_at = datetime.now(timezone.utc)
            record.updated_at = datetime.now(timezone.utc)
            self.db.add(record)
            await self.db.flush()

            await self.events.log(
                event_type="PLAYER_CHECKED_IN",
                tournament_id=tournament_id,
                actor_id=actor_id,
                payload={"player_id": str(player_id), "note": "re-checked in"},
            )
            return record

        # Create new attendance record
        record = Attendance(
            tournament_id=tournament_id,
            player_id=player_id,
            status="checked_in",
            checked_in_at=datetime.now(timezone.utc),
        )
        self.db.add(record)
        await self.db.flush()

        await self.events.log(
            event_type="PLAYER_CHECKED_IN",
            tournament_id=tournament_id,
            actor_id=actor_id,
            payload={"player_id": str(player_id)},
        )

        logger.info(
            "player_checked_in",
            tournament_id=str(tournament_id),
            player_id=str(player_id),
        )
        return record

    async def mark_no_show(
        self,
        tournament_id: uuid.UUID,
        player_id: uuid.UUID,
        actor_id: uuid.UUID | None = None,
    ) -> Attendance:
        """Mark a player as no-show for a tournament."""
        await self._get_tournament(tournament_id)
        await self._get_player(player_id)

        record = await self._get_or_create_attendance(tournament_id, player_id)
        record.status = "no_show"
        record.updated_at = datetime.now(timezone.utc)
        self.db.add(record)
        await self.db.flush()

        await self.events.log(
            event_type="PLAYER_NO_SHOW",
            tournament_id=tournament_id,
            actor_id=actor_id,
            payload={"player_id": str(player_id)},
        )

        logger.info(
            "player_no_show",
            tournament_id=str(tournament_id),
            player_id=str(player_id),
        )
        return record

    async def update_attendance(
        self,
        tournament_id: uuid.UUID,
        player_id: uuid.UUID,
        status: str,
        notes: str | None = None,
    ) -> Attendance:
        """Update an attendance record's status and/or notes."""
        if status not in VALID_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status}. "
                f"Valid: {', '.join(sorted(VALID_STATUSES))}",
            )

        record = await self._get_or_create_attendance(tournament_id, player_id)
        record.status = status
        if notes is not None:
            record.notes = notes
        record.updated_at = datetime.now(timezone.utc)
        self.db.add(record)
        await self.db.flush()
        return record

    async def get_attendance(
        self,
        tournament_id: uuid.UUID,
        status_filter: str | None = None,
    ) -> list[Attendance]:
        """List attendance records for a tournament, optionally filtered by status."""
        await self._get_tournament(tournament_id)

        query = (
            select(Attendance)
            .where(Attendance.tournament_id == tournament_id)
            .order_by(Attendance.created_at.desc())
        )
        if status_filter:
            if status_filter not in VALID_STATUSES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status: {status_filter}. "
                    f"Valid: {', '.join(sorted(VALID_STATUSES))}",
                )
            query = query.where(Attendance.status == status_filter)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_attendance_stats(
        self, tournament_id: uuid.UUID
    ) -> dict[str, int | float]:
        """Aggregate attendance statistics for a tournament."""
        await self._get_tournament(tournament_id)

        total_result = await self.db.execute(
            select(func.count(Attendance.id)).where(
                Attendance.tournament_id == tournament_id
            )
        )
        total_players = total_result.scalar() or 0

        checked_in_result = await self.db.execute(
            select(func.count(Attendance.id)).where(
                Attendance.tournament_id == tournament_id,
                Attendance.status == "checked_in",
            )
        )
        checked_in = checked_in_result.scalar() or 0

        no_show_result = await self.db.execute(
            select(func.count(Attendance.id)).where(
                Attendance.tournament_id == tournament_id,
                Attendance.status == "no_show",
            )
        )
        no_shows = no_show_result.scalar() or 0

        late_cancel_result = await self.db.execute(
            select(func.count(Attendance.id)).where(
                Attendance.tournament_id == tournament_id,
                Attendance.status == "late_cancellation",
            )
        )
        late_cancellations = late_cancel_result.scalar() or 0

        check_in_rate = (checked_in / total_players * 100) if total_players > 0 else 0.0

        return {
            "total_players": total_players,
            "checked_in": checked_in,
            "no_shows": no_shows,
            "late_cancellations": late_cancellations,
            "check_in_rate": round(check_in_rate, 1),
        }

    async def bulk_check_in(
        self,
        tournament_id: uuid.UUID,
        player_ids: list[uuid.UUID],
        actor_id: uuid.UUID | None = None,
    ) -> list[Attendance]:
        """Check in multiple players at once."""
        await self._get_tournament(tournament_id)

        records = []
        for pid in player_ids:
            record = await self.check_in(tournament_id, pid, actor_id=actor_id)
            records.append(record)

        logger.info(
            "bulk_check_in",
            tournament_id=str(tournament_id),
            count=len(records),
        )
        return records

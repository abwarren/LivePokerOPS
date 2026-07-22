from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models import Player, Tournament
from app.models.rsvp import Rsvp
from app.schemas.rsvp import TournamentRsvpStats

logger = get_logger(__name__)

RSVP_VALID_STATUSES = frozenset({"confirmed", "waiting", "cancelled"})


class RsvpService:
    """RSVP lifecycle with capacity management and waitlist support."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_tournament(self, tournament_id: uuid.UUID) -> Tournament:
        result = await self.db.execute(
            select(Tournament).where(Tournament.id == tournament_id)
        )
        t = result.scalar_one_or_none()
        if t is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tournament not found",
            )
        return t

    async def _get_player(self, player_id: uuid.UUID) -> Player:
        result = await self.db.execute(
            select(Player).where(Player.id == player_id)
        )
        p = result.scalar_one_or_none()
        if p is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Player not found",
            )
        return p

    async def _count_confirmed(self, tournament_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.count(Rsvp.id)).where(
                Rsvp.tournament_id == tournament_id,
                Rsvp.status == "confirmed",
            )
        )
        return result.scalar() or 0

    async def create_rsvp(
        self, tournament_id: uuid.UUID, player_id: uuid.UUID, notes: str | None = None
    ) -> Rsvp:
        """RSVP to a tournament. Auto-waitlists if capacity is full."""
        tournament = await self._get_tournament(tournament_id)
        await self._get_player(player_id)

        # Check for existing RSVP
        existing_result = await self.db.execute(
            select(Rsvp).where(
                Rsvp.tournament_id == tournament_id,
                Rsvp.player_id == player_id,
            )
        )
        existing = existing_result.scalar_one_or_none()
        if existing:
            # If already confirmed or waiting, return as-is
            if existing.status in ("confirmed", "waiting"):
                return existing
            # If cancelled, re-activate
            if existing.status == "cancelled":
                # Check capacity before re-activating
                confirmed_count = await self._count_confirmed(tournament_id)
                if (
                    tournament.max_players is not None
                    and confirmed_count >= tournament.max_players
                ):
                    existing.status = "waiting"
                else:
                    existing.status = "confirmed"
                existing.notes = notes
                existing.updated_at = datetime.now(timezone.utc)
                self.db.add(existing)
                await self.db.flush()
                return existing

        # Determine status based on capacity
        confirmed_count = await self._count_confirmed(tournament_id)
        status_value = "confirmed"
        if (
            tournament.max_players is not None
            and confirmed_count >= tournament.max_players
        ):
            status_value = "waiting"

        rsvp = Rsvp(
            tournament_id=tournament_id,
            player_id=player_id,
            status=status_value,
            notes=notes,
        )
        self.db.add(rsvp)
        await self.db.flush()

        if status_value == "waiting":
            logger.info(
                "player_waitlisted",
                tournament_id=str(tournament_id),
                player_id=str(player_id),
            )

        return rsvp

    async def update_rsvp(
        self, tournament_id: uuid.UUID, player_id: uuid.UUID, status: str
    ) -> Rsvp:
        """Update an RSVP status (confirmed or cancelled)."""
        if status not in RSVP_VALID_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status}. Valid: {', '.join(sorted(RSVP_VALID_STATUSES))}",
            )

        rsvp = await self._get_rsvp(tournament_id, player_id)

        if status == "confirmed" and rsvp.status == "waiting":
            # Confirm from waiting — check capacity
            tournament = await self._get_tournament(tournament_id)
            confirmed_count = await self._count_confirmed(tournament_id)
            if (
                tournament.max_players is not None
                and confirmed_count >= tournament.max_players
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Tournament is at full capacity",
                )

        rsvp.status = status
        rsvp.updated_at = datetime.now(timezone.utc)
        self.db.add(rsvp)
        await self.db.flush()
        return rsvp

    async def cancel_rsvp(self, tournament_id: uuid.UUID, player_id: uuid.UUID) -> Rsvp:
        """Cancel an RSVP. If the player was confirmed, promote first waiter."""
        rsvp = await self._get_rsvp(tournament_id, player_id)
        was_confirmed = rsvp.status == "confirmed"

        rsvp.status = "cancelled"
        rsvp.updated_at = datetime.now(timezone.utc)
        self.db.add(rsvp)
        await self.db.flush()

        if was_confirmed:
            await self._promote_from_waitlist(tournament_id)

        return rsvp

    async def list_rsvps(
        self, tournament_id: uuid.UUID, status_filter: str | None = None
    ) -> list[dict]:
        """List RSVPs for a tournament, optionally filtered by status."""
        query = (
            select(Rsvp, Player)
            .join(Player, Rsvp.player_id == Player.id)
            .where(Rsvp.tournament_id == tournament_id)
        )
        if status_filter:
            if status_filter not in RSVP_VALID_STATUSES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status: {status_filter}. "
                    f"Valid: {', '.join(sorted(RSVP_VALID_STATUSES))}",
                )
            query = query.where(Rsvp.status == status_filter)

        query = query.order_by(Rsvp.created_at.asc())
        result = await self.db.execute(query)
        rows = []
        for rsvp, player in result.all():
            rows.append({
                "id": rsvp.id,
                "tournament_id": rsvp.tournament_id,
                "player_id": rsvp.player_id,
                "player_name": f"{player.first_name} {player.last_name}",
                "status": rsvp.status,
                "notes": rsvp.notes,
                "created_at": rsvp.created_at,
                "updated_at": rsvp.updated_at,
            })
        return rows

    async def get_rsvp_stats(self, tournament_id: uuid.UUID) -> TournamentRsvpStats:
        """Get RSVP statistics for a tournament."""
        tournament = await self._get_tournament(tournament_id)

        result = await self.db.execute(
            select(Rsvp.status, func.count(Rsvp.id))
            .where(Rsvp.tournament_id == tournament_id)
            .group_by(Rsvp.status)
        )
        counts = dict(result.all())

        confirmed = counts.get("confirmed", 0)
        waiting = counts.get("waiting", 0)
        cancelled = counts.get("cancelled", 0)

        capacity_remaining = None
        if tournament.max_players is not None:
            capacity_remaining = max(0, tournament.max_players - confirmed)

        return TournamentRsvpStats(
            total_confirmed=confirmed,
            total_waiting=waiting,
            total_cancelled=cancelled,
            capacity_remaining=capacity_remaining,
        )

    async def get_player_rsvps(self, player_id: uuid.UUID) -> list[dict]:
        """Get all RSVPs for a player across all tournaments."""
        await self._get_player(player_id)
        query = (
            select(Rsvp, Tournament)
            .join(Tournament, Rsvp.tournament_id == Tournament.id)
            .where(Rsvp.player_id == player_id)
            .order_by(Rsvp.created_at.desc())
        )
        result = await self.db.execute(query)
        rows = []
        for rsvp, tournament in result.all():
            rows.append({
                "id": rsvp.id,
                "tournament_id": rsvp.tournament_id,
                "tournament_name": tournament.name,
                "player_id": rsvp.player_id,
                "status": rsvp.status,
                "notes": rsvp.notes,
                "created_at": rsvp.created_at,
                "updated_at": rsvp.updated_at,
            })
        return rows

    async def _get_rsvp(self, tournament_id: uuid.UUID, player_id: uuid.UUID) -> Rsvp:
        """Internal: get a single RSVP or raise 404."""
        result = await self.db.execute(
            select(Rsvp).where(
                Rsvp.tournament_id == tournament_id,
                Rsvp.player_id == player_id,
            )
        )
        rsvp = result.scalar_one_or_none()
        if rsvp is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="RSVP not found",
            )
        return rsvp

    async def _promote_from_waitlist(self, tournament_id: uuid.UUID) -> None:
        """Promote the first waiting player to confirmed."""
        result = await self.db.execute(
            select(Rsvp)
            .where(
                Rsvp.tournament_id == tournament_id,
                Rsvp.status == "waiting",
            )
            .order_by(Rsvp.created_at.asc())
            .limit(1)
        )
        waiter = result.scalar_one_or_none()
        if waiter is None:
            return

        # Check capacity
        tournament = await self._get_tournament(tournament_id)
        confirmed_count = await self._count_confirmed(tournament_id)
        if (
            tournament.max_players is not None
            and confirmed_count >= tournament.max_players
        ):
            return

        waiter.status = "confirmed"
        waiter.updated_at = datetime.now(timezone.utc)
        self.db.add(waiter)
        await self.db.flush()

        logger.info(
            "player_promoted_from_waitlist",
            tournament_id=str(tournament_id),
            player_id=str(waiter.player_id),
        )

    async def promote_from_waitlist(self, tournament_id: uuid.UUID) -> list[Rsvp]:
        """Auto-promote all eligible waitlisters (public method for admin use)."""
        promoted = []
        while True:
            # Check capacity
            tournament = await self._get_tournament(tournament_id)
            confirmed_count = await self._count_confirmed(tournament_id)
            if (
                tournament.max_players is not None
                and confirmed_count >= tournament.max_players
            ):
                break

            # Get next waiter
            result = await self.db.execute(
                select(Rsvp)
                .where(
                    Rsvp.tournament_id == tournament_id,
                    Rsvp.status == "waiting",
                )
                .order_by(Rsvp.created_at.asc())
                .limit(1)
            )
            waiter = result.scalar_one_or_none()
            if waiter is None:
                break

            waiter.status = "confirmed"
            waiter.updated_at = datetime.now(timezone.utc)
            self.db.add(waiter)
            promoted.append(waiter)

            logger.info(
                "player_promoted_from_waitlist",
                tournament_id=str(tournament_id),
                player_id=str(waiter.player_id),
            )

        if promoted:
            await self.db.flush()

        return promoted

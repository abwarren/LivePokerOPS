from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.models import Player, Season, SeasonTournament, Tournament
from app.models.league import PlayerPoints
from app.schemas.league import (
    DEFAULT_POINTS_SCHEDULE,
    LeaderboardEntry,
    LeaderboardResponse,
    PlayerPointsInput,
    PlayerPointsResponse,
    SeasonCreate,
    SeasonTournamentCreate,
    SeasonUpdate,
)

logger = get_logger(__name__)

VALID_SEASON_STATUSES = frozenset({"upcoming", "active", "completed"})


class LeagueService:
    """League & points management."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ─── Seasons ───

    async def create_season(self, data: SeasonCreate) -> Season:
        if data.start_date >= data.end_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="End date must be after start date",
            )
        season = Season(
            name=data.name,
            start_date=data.start_date,
            end_date=data.end_date,
            description=data.description,
            points_schedule=data.points_schedule or DEFAULT_POINTS_SCHEDULE,
            attendance_points=data.attendance_points,
            final_table_bonus=data.final_table_bonus,
            status="upcoming",
        )
        self.db.add(season)
        await self.db.flush()
        return season

    async def get_season(self, season_id: uuid.UUID) -> Season:
        result = await self.db.execute(
            select(Season).where(Season.id == season_id)
        )
        season = result.scalar_one_or_none()
        if season is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Season not found"
            )
        return season

    async def list_seasons(self) -> list[Season]:
        result = await self.db.execute(
            select(Season).order_by(Season.start_date.desc())
        )
        return list(result.scalars().all())

    async def update_season(self, season_id: uuid.UUID, data: SeasonUpdate) -> Season:
        season = await self.get_season(season_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            if value is not None:
                setattr(season, field, value)
        season.updated_at = datetime.now(timezone.utc)
        self.db.add(season)
        await self.db.flush()
        return season

    async def delete_season(self, season_id: uuid.UUID) -> None:
        season = await self.get_season(season_id)
        await self.db.delete(season)
        await self.db.flush()

    async def get_season_stats(self, season_id: uuid.UUID) -> dict[str, Any]:
        """Get tournament count and player count for a season."""
        # Tournament count
        t_result = await self.db.execute(
            select(func.count(SeasonTournament.id))
            .where(SeasonTournament.season_id == season_id)
        )
        tournament_count = t_result.scalar() or 0

        # Player count (distinct players who have points)
        p_result = await self.db.execute(
            select(func.count(func.distinct(PlayerPoints.player_id)))
            .where(PlayerPoints.season_id == season_id)
        )
        player_count = p_result.scalar() or 0

        return {
            "tournament_count": tournament_count,
            "player_count": player_count,
        }

    # ─── Season-Tournament Assignment ───

    async def assign_tournament(
        self, season_id: uuid.UUID, data: SeasonTournamentCreate
    ) -> SeasonTournament:
        season = await self.get_season(season_id)

        # Verify tournament exists
        t_result = await self.db.execute(
            select(Tournament).where(Tournament.id == data.tournament_id)
        )
        if t_result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tournament not found",
            )

        # Check not already assigned
        existing = await self.db.execute(
            select(SeasonTournament).where(
                SeasonTournament.season_id == season_id,
                SeasonTournament.tournament_id == data.tournament_id,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Tournament already assigned to this season",
            )

        st = SeasonTournament(
            season_id=season_id,
            tournament_id=data.tournament_id,
            points_schedule=data.points_schedule,
            attendance_points=data.attendance_points,
            final_table_bonus=data.final_table_bonus,
        )
        self.db.add(st)
        await self.db.flush()
        return st

    async def unassign_tournament(
        self, season_id: uuid.UUID, tournament_id: uuid.UUID
    ) -> None:
        result = await self.db.execute(
            select(SeasonTournament).where(
                SeasonTournament.season_id == season_id,
                SeasonTournament.tournament_id == tournament_id,
            )
        )
        st = result.scalar_one_or_none()
        if st is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tournament not assigned to this season",
            )
        await self.db.delete(st)
        await self.db.flush()

    async def list_season_tournaments(
        self, season_id: uuid.UUID
    ) -> list[dict[str, Any]]:
        result = await self.db.execute(
            select(SeasonTournament, Tournament)
            .join(Tournament, SeasonTournament.tournament_id == Tournament.id)
            .where(SeasonTournament.season_id == season_id)
        )
        rows = []
        for st, t in result.all():
            rows.append({
                "id": st.id,
                "season_id": st.season_id,
                "tournament_id": st.tournament_id,
                "tournament_name": t.name,
                "tournament_date": t.start_time,
                "points_schedule": st.points_schedule,
                "attendance_points": st.attendance_points,
                "final_table_bonus": st.final_table_bonus,
            })
        return rows

    # ─── Points ───

    async def _get_schedule(
        self, season: Season, tournament_id: uuid.UUID | None = None
    ) -> tuple[dict, int, int]:
        """Get effective points schedule for a tournament in a season."""
        schedule = season.points_schedule or DEFAULT_POINTS_SCHEDULE
        att_pts = season.attendance_points or 10
        ft_bonus = season.final_table_bonus or 5

        if tournament_id:
            result = await self.db.execute(
                select(SeasonTournament).where(
                    SeasonTournament.season_id == season.id,
                    SeasonTournament.tournament_id == tournament_id,
                )
            )
            st = result.scalar_one_or_none()
            if st:
                if st.points_schedule:
                    schedule = st.points_schedule
                if st.attendance_points is not None:
                    att_pts = st.attendance_points
                if st.final_table_bonus is not None:
                    ft_bonus = st.final_table_bonus

        return schedule, att_pts, ft_bonus

    def _calculate_position_points(
        self, position: int, schedule: dict[str, int]
    ) -> int:
        """Calculate points for a finishing position from the schedule."""
        pos_key = str(position)
        if pos_key in schedule:
            return schedule[pos_key]
        # Find next lowest position
        sorted_positions = sorted(int(k) for k in schedule.keys())
        lowest = sorted_positions[-1] if sorted_positions else 0
        if position > lowest:
            return 0
        # Interpolate: find the closest higher position's points
        for pos in sorted_positions:
            if position <= pos:
                return schedule[str(pos)]
        return 0

    async def record_tournament_results(
        self,
        season_id: uuid.UUID,
        tournament_id: uuid.UUID,
        results: list[PlayerPointsInput],
        actor_id: uuid.UUID | None = None,
    ) -> list[PlayerPoints]:
        """Record finishing positions and calculate points for a tournament."""
        season = await self.get_season(season_id)
        schedule, att_pts, ft_bonus = await self._get_schedule(season, tournament_id)

        # Verify tournament exists
        t_result = await self.db.execute(
            select(Tournament).where(Tournament.id == tournament_id)
        )
        t = t_result.scalar_one_or_none()
        if t is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tournament not found",
            )

        # Verify all players exist
        player_ids = [r.player_id for r in results]
        p_result = await self.db.execute(
            select(Player).where(Player.id.in_(player_ids))
        )
        found_players = {str(p.id) for p in p_result.scalars().all()}
        for r in results:
            if str(r.player_id) not in found_players:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Player {r.player_id} not found",
                )

        # Remove existing points for this tournament in this season
        await self.db.execute(
            text("DELETE FROM player_points WHERE season_id = :sid AND tournament_id = :tid")
            .bindparams(sid=season_id, tid=tournament_id)
        )

        # Create new points records
        points_records = []
        for r in results:
            calculated_points = r.points_earned
            if r.points_type == "finishing_position" and r.position is not None:
                calculated_points = self._calculate_position_points(
                    r.position, schedule
                )

            pp = PlayerPoints(
                season_id=season_id,
                player_id=r.player_id,
                tournament_id=tournament_id,
                points_earned=calculated_points,
                points_type=r.points_type,
                position=r.position,
                is_attendance=r.is_attendance,
            )
            self.db.add(pp)
            points_records.append(pp)

        # Add attendance points for all participants
        for r in results:
            if not r.is_attendance and att_pts > 0:
                pp = PlayerPoints(
                    season_id=season_id,
                    player_id=r.player_id,
                    tournament_id=tournament_id,
                    points_earned=att_pts,
                    points_type="attendance",
                    is_attendance=True,
                )
                self.db.add(pp)

        await self.db.flush()

        logger.info(
            "tournament_results_recorded",
            season_id=str(season_id),
            tournament_id=str(tournament_id),
            players=len(results),
        )

        return points_records

    async def get_leaderboard(
        self, season_id: uuid.UUID, limit: int = 50
    ) -> LeaderboardResponse:
        """Get the leaderboard for a season."""
        season = await self.get_season(season_id)

        # Aggregate points per player
        result = await self.db.execute(
            text("""
                SELECT
                    pp.player_id,
                    p.first_name || ' ' || p.last_name AS player_name,
                    p.nickname,
                    SUM(pp.points_earned)::integer AS total_points,
                    COUNT(DISTINCT pp.tournament_id) AS tournaments_played,
                    COUNT(DISTINCT CASE WHEN pp.is_attendance THEN pp.tournament_id END) AS attendance_count,
                    COUNT(DISTINCT CASE WHEN pp.points_type = 'finishing_position' AND pp.position IS NOT NULL AND pp.position <= 9 THEN pp.tournament_id END) AS final_table_count,
                    MIN(CASE WHEN pp.position IS NOT NULL AND pp.position > 0 THEN pp.position END) AS best_position
                FROM player_points pp
                JOIN players p ON p.id = pp.player_id
                WHERE pp.season_id = :sid
                GROUP BY pp.player_id, p.first_name, p.last_name, p.nickname
                ORDER BY total_points DESC
                LIMIT :lim
            """).bindparams(sid=season_id, lim=limit)
        )
        rows = result.all()

        entries = []
        for i, row in enumerate(rows, start=1):
            entries.append(LeaderboardEntry(
                rank=i,
                player_id=row.player_id,
                player_name=row.player_name,
                nickname=row.nickname,
                total_points=row.total_points or 0,
                tournaments_played=row.tournaments_played or 0,
                attendance_count=row.attendance_count or 0,
                final_table_count=row.final_table_count or 0,
                best_position=row.best_position,
            ))

        return LeaderboardResponse(
            season_id=season_id,
            season_name=season.name,
            entries=entries,
        )

    async def get_player_season_points(
        self, season_id: uuid.UUID, player_id: uuid.UUID
    ) -> list[PlayerPoints]:
        """Get all points records for a player in a season."""
        result = await self.db.execute(
            select(PlayerPoints)
            .where(
                PlayerPoints.season_id == season_id,
                PlayerPoints.player_id == player_id,
            )
            .order_by(PlayerPoints.created_at.desc())
        )
        return list(result.scalars().all())

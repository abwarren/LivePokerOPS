from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models import Player, Tournament

logger = get_logger(__name__)


class AnalyticsService:
    """Aggregate KPIs, trends, and growth metrics across the system."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_dashboard_summary(self) -> dict[str, Any]:
        """Top-level KPIs for the dashboard."""
        # Player count
        p_result = await self.db.execute(
            select(func.count(Player.id)).where(Player.is_active == True)  # noqa: E712
        )
        total_players = p_result.scalar() or 0

        # Tournament counts by status
        t_counts = {}
        for status in ("planned", "announced", "in_progress", "completed", "cancelled"):
            result = await self.db.execute(
                select(func.count(Tournament.id)).where(Tournament.status == status)
            )
            t_counts[status] = result.scalar() or 0

        # Total tournaments
        t_result = await self.db.execute(select(func.count(Tournament.id)))
        total_tournaments = t_result.scalar() or 0

        # Upcoming tournaments (next 7 days)
        now = datetime.now(timezone.utc)
        upcoming_result = await self.db.execute(
            select(func.count(Tournament.id)).where(
                Tournament.start_time >= now,
                Tournament.start_time <= func.now() + text("INTERVAL '7 days'"),
                Tournament.status.in_(["planned", "announced"]),
            )
        )
        upcoming = upcoming_result.scalar() or 0

        return {
            "total_players": total_players,
            "total_tournaments": total_tournaments,
            "tournaments_by_status": t_counts,
            "upcoming_tournaments": upcoming,
        }

    async def get_tournament_stats(self) -> list[dict[str, Any]]:
        """Monthly tournament stats for trend charts."""
        result = await self.db.execute(
            text("""
                SELECT
                    DATE_TRUNC('month', start_time) AS month,
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE status = 'completed') AS completed,
                    COUNT(*) FILTER (WHERE status = 'cancelled') AS cancelled
                FROM tournaments
                WHERE start_time IS NOT NULL
                GROUP BY DATE_TRUNC('month', start_time)
                ORDER BY month DESC
                LIMIT 12
            """)
        )
        rows = result.all()
        return [
            {
                "month": str(r.month.date()) if r.month else None,
                "total": r.total or 0,
                "completed": r.completed or 0,
                "cancelled": r.cancelled or 0,
            }
            for r in rows
        ]

    async def get_player_growth(self) -> list[dict[str, Any]]:
        """Player registration growth over time."""
        result = await self.db.execute(
            text("""
                SELECT
                    DATE_TRUNC('month', created_at) AS month,
                    COUNT(*) AS new_players
                FROM players
                GROUP BY DATE_TRUNC('month', created_at)
                ORDER BY month DESC
                LIMIT 12
            """)
        )
        rows = result.all()
        return [
            {
                "month": str(r.month.date()) if r.month else None,
                "new_players": r.new_players or 0,
            }
            for r in rows
        ]

    async def get_rsvp_stats(self) -> dict[str, Any]:
        """Aggregate RSVP statistics across all tournaments."""
        try:
            from app.models.rsvp import Rsvp  # noqa: F401 — may not exist yet
            result = await self.db.execute(
                text("""
                    SELECT
                        status,
                        COUNT(*) AS count
                    FROM rsvps
                    GROUP BY status
                """)
            )
            rows = result.all()
            stats = {"confirmed": 0, "waiting": 0, "cancelled": 0, "total": 0}
            for r in rows:
                if r.status in stats:
                    stats[r.status] = r.count or 0
                    stats["total"] += r.count or 0
            return stats
        except Exception:
            return {"confirmed": 0, "waiting": 0, "cancelled": 0, "total": 0}

    async def get_broadcast_stats(self) -> dict[str, Any]:
        """Aggregate broadcast statistics."""
        try:
            from app.models.broadcast import Broadcast  # noqa: F401
            result = await self.db.execute(
                text("""
                    SELECT
                        status,
                        COUNT(*) AS count
                    FROM broadcasts
                    GROUP BY status
                """)
            )
            rows = result.all()
            stats: dict[str, int] = {"total": 0}
            for r in rows:
                stats[r.status] = r.count or 0
                stats["total"] += r.count or 0
            return stats
        except Exception:
            return {"total": 0}

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ─── Season ───


class SeasonCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    start_date: datetime
    end_date: datetime
    description: str | None = Field(default=None, max_length=2000)
    points_schedule: dict[str, int] | None = None
    attendance_points: int = 10
    final_table_bonus: int = 5


class SeasonUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    start_date: datetime | None = None
    end_date: datetime | None = None
    status: str | None = Field(
        default=None,
        pattern=r"^(upcoming|active|completed)$",
    )
    description: str | None = Field(default=None, max_length=2000)
    points_schedule: dict[str, int] | None = None
    attendance_points: int | None = None
    final_table_bonus: int | None = None


class SeasonResponse(BaseModel):
    id: uuid.UUID
    name: str
    start_date: datetime
    end_date: datetime
    status: str
    description: str | None = None
    points_schedule: dict[str, Any] = {}
    attendance_points: int = 10
    final_table_bonus: int = 5
    tournament_count: int = 0
    player_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SeasonSummary(BaseModel):
    id: uuid.UUID
    name: str
    status: str
    start_date: datetime
    end_date: datetime
    tournament_count: int = 0
    player_count: int = 0

    model_config = {"from_attributes": True}


# ─── Season-Tournament Assignment ───


class SeasonTournamentCreate(BaseModel):
    tournament_id: uuid.UUID
    points_schedule: dict[str, int] | None = None
    attendance_points: int | None = None
    final_table_bonus: int | None = None


class SeasonTournamentResponse(BaseModel):
    id: uuid.UUID
    season_id: uuid.UUID
    tournament_id: uuid.UUID
    points_schedule: dict[str, Any] | None = None
    attendance_points: int | None = None
    final_table_bonus: int | None = None
    tournament_name: str = ""
    tournament_date: datetime | None = None

    model_config = {"from_attributes": True}


# ─── Player Points ───


class PlayerPointsInput(BaseModel):
    """Record points for a player in a tournament within a season."""
    player_id: uuid.UUID
    position: int | None = None
    points_earned: int = 0
    points_type: str = Field(default="finishing_position", pattern=r"^(finishing_position|attendance|bonus)$")
    is_attendance: bool = False


class PlayerPointsResponse(BaseModel):
    id: uuid.UUID
    season_id: uuid.UUID
    player_id: uuid.UUID
    tournament_id: uuid.UUID | None = None
    points_earned: int
    points_type: str
    position: int | None = None
    is_attendance: bool
    player_name: str = ""
    tournament_name: str = ""
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Leaderboard ───


class LeaderboardEntry(BaseModel):
    rank: int
    player_id: uuid.UUID
    player_name: str
    nickname: str | None = None
    total_points: int
    tournaments_played: int
    attendance_count: int
    final_table_count: int
    best_position: int | None = None
    points_breakdown: list[PlayerPointsResponse] = []


class LeaderboardResponse(BaseModel):
    season_id: uuid.UUID
    season_name: str
    entries: list[LeaderboardEntry]


# ─── Default Points Schedule ───


DEFAULT_POINTS_SCHEDULE: dict[str, int] = {
    "1": 100,
    "2": 80,
    "3": 60,
    "4": 50,
    "5": 40,
    "6": 30,
    "7": 20,
    "8": 10,
    "9": 5,
}

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class AttendanceCreate(BaseModel):
    notes: str | None = Field(default=None, max_length=2000)


class AttendanceUpdate(BaseModel):
    status: str = Field(
        ...,
        pattern=r"^(checked_in|no_show|late_cancellation)$",
    )
    notes: str | None = Field(default=None, max_length=2000)


class AttendanceResponse(BaseModel):
    id: uuid.UUID
    tournament_id: uuid.UUID
    player_id: uuid.UUID
    player_name: str | None = None
    status: str
    checked_in_at: datetime | None = None
    notes: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CheckInRequest(BaseModel):
    player_id: uuid.UUID


class AttendanceStats(BaseModel):
    total_players: int = 0
    checked_in: int = 0
    no_shows: int = 0
    late_cancellations: int = 0
    check_in_rate: float = 0.0

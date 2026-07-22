from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class RsvpCreate(BaseModel):
    tournament_id: uuid.UUID
    notes: str | None = Field(default=None, max_length=1000)


class RsvpUpdate(BaseModel):
    status: str = Field(
        ...,
        pattern=r"^(confirmed|cancelled)$",
    )


class RsvpResponse(BaseModel):
    id: uuid.UUID
    tournament_id: uuid.UUID
    player_id: uuid.UUID
    player_name: str = ""
    status: str
    notes: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TournamentRsvpStats(BaseModel):
    total_confirmed: int = 0
    total_waiting: int = 0
    total_cancelled: int = 0
    capacity_remaining: int | None = None

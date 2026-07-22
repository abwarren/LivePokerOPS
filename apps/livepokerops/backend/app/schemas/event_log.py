from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class EventLogResponse(BaseModel):
    id: uuid.UUID
    event_type: str
    source: str
    tournament_id: uuid.UUID | None = None
    actor_id: uuid.UUID | None = None
    payload: dict = {}
    created_at: datetime

    model_config = {"from_attributes": True}


class EventLogListResponse(BaseModel):
    events: list[EventLogResponse]
    total: int

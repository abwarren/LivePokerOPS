from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Season(Base):
    __tablename__ = "seasons"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="upcoming")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    points_schedule: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=dict
    )
    attendance_points: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    final_table_bonus: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    season_tournaments = relationship(
        "SeasonTournament", back_populates="season", cascade="all, delete-orphan"
    )
    player_points = relationship(
        "PlayerPoints", back_populates="season", cascade="all, delete-orphan"
    )


class SeasonTournament(Base):
    __tablename__ = "season_tournaments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    season_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False
    )
    tournament_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tournaments.id", ondelete="CASCADE"), nullable=False
    )
    points_schedule: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    attendance_points: Mapped[int | None] = mapped_column(Integer, nullable=True)
    final_table_bonus: Mapped[int | None] = mapped_column(Integer, nullable=True)

    season = relationship("Season", back_populates="season_tournaments")


class PlayerPoints(Base):
    __tablename__ = "player_points"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    season_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False
    )
    player_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("players.id", ondelete="CASCADE"), nullable=False
    )
    tournament_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("tournaments.id", ondelete="SET NULL"), nullable=True
    )
    points_earned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    points_type: Mapped[str] = mapped_column(
        String(30), nullable=False, default="finishing_position"
    )
    position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_attendance: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    season = relationship("Season", back_populates="player_points")

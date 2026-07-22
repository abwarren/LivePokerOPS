"""Add league: seasons, season_tournaments, player_points.

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-22
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "seasons",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status", sa.String(20), nullable=False,
            server_default=sa.text("'upcoming'"),
        ),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "points_schedule", JSONB, nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "attendance_points", sa.Integer, nullable=False,
            server_default=sa.text("10"),
        ),
        sa.Column(
            "final_table_bonus", sa.Integer, nullable=False,
            server_default=sa.text("5"),
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
    )
    op.create_index("ix_seasons_status", "seasons", ["status"])

    op.create_table(
        "season_tournaments",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("season_id", UUID(as_uuid=True), nullable=False),
        sa.Column("tournament_id", UUID(as_uuid=True), nullable=False),
        sa.Column("points_schedule", JSONB, nullable=True),
        sa.Column("attendance_points", sa.Integer, nullable=True),
        sa.Column("final_table_bonus", sa.Integer, nullable=True),
    )
    op.create_foreign_key(
        "fk_st_season", "season_tournaments", "seasons",
        ["season_id"], ["id"], ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_st_tournament", "season_tournaments", "tournaments",
        ["tournament_id"], ["id"], ondelete="CASCADE",
    )
    op.create_index("ix_st_season", "season_tournaments", ["season_id"])
    op.create_index("ix_st_tournament", "season_tournaments", ["tournament_id"])

    op.create_table(
        "player_points",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("season_id", UUID(as_uuid=True), nullable=False),
        sa.Column("player_id", UUID(as_uuid=True), nullable=False),
        sa.Column("tournament_id", UUID(as_uuid=True), nullable=True),
        sa.Column(
            "points_earned", sa.Integer, nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "points_type", sa.String(30), nullable=False,
            server_default=sa.text("'finishing_position'"),
        ),
        sa.Column("position", sa.Integer, nullable=True),
        sa.Column(
            "is_attendance", sa.Boolean, nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
    )
    op.create_foreign_key(
        "fk_pp_season", "player_points", "seasons",
        ["season_id"], ["id"], ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_pp_player", "player_points", "players",
        ["player_id"], ["id"], ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_pp_tournament", "player_points", "tournaments",
        ["tournament_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index("ix_pp_season", "player_points", ["season_id"])
    op.create_index("ix_pp_player", "player_points", ["player_id"])
    op.create_index("ix_pp_season_player", "player_points", ["season_id", "player_id"])


def downgrade() -> None:
    op.drop_table("player_points")
    op.drop_table("season_tournaments")
    op.drop_table("seasons")

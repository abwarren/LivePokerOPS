"""Add attendance table for tournament check-in tracking.

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-22
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "attendance",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tournament_id", UUID(as_uuid=True), nullable=False),
        sa.Column("player_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status", sa.String(30), nullable=False,
            server_default=sa.text("'checked_in'"),
        ),
        sa.Column(
            "checked_in_at", sa.DateTime(timezone=True), nullable=True,
        ),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
    )
    op.create_foreign_key(
        "fk_attendance_tournament", "attendance", "tournaments",
        ["tournament_id"], ["id"], ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_attendance_player", "attendance", "players",
        ["player_id"], ["id"], ondelete="CASCADE",
    )
    op.create_unique_constraint(
        "uq_attendance_tournament_player", "attendance",
        ["tournament_id", "player_id"],
    )
    op.create_index(
        "ix_attendance_tournament", "attendance", ["tournament_id"],
    )
    op.create_index(
        "ix_attendance_status", "attendance", ["status"],
    )


def downgrade() -> None:
    op.drop_table("attendance")

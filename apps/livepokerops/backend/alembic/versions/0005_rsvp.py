"""Add RSVP system: tournament registration with waitlist support.

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-22
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "rsvps",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tournament_id", UUID(as_uuid=True), nullable=False),
        sa.Column("player_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status", sa.String(20), nullable=False,
            server_default=sa.text("'confirmed'"),
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
        "fk_rsvp_tournament", "rsvps", "tournaments",
        ["tournament_id"], ["id"], ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_rsvp_player", "rsvps", "players",
        ["player_id"], ["id"], ondelete="CASCADE",
    )
    op.create_index("ix_rsvp_tournament", "rsvps", ["tournament_id"])
    op.create_index("ix_rsvp_player", "rsvps", ["player_id"])
    op.create_unique_constraint(
        "uq_rsvp_tournament_player", "rsvps",
        ["tournament_id", "player_id"],
    )


def downgrade() -> None:
    op.drop_table("rsvps")

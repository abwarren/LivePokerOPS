"""Add event_logs and tournaments tables.

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-22
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tournaments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'planned'")),
        sa.Column("buy_in", sa.Numeric(12, 2), nullable=True),
        sa.Column("starting_stack", sa.BigInteger, nullable=True),
        sa.Column("min_players", sa.Integer, nullable=True),
        sa.Column("max_players", sa.Integer, nullable=True),
        sa.Column("late_reg_levels", sa.Integer, nullable=False, server_default=sa.text("4")),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("registration_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_tournaments_status", "tournaments", ["status"])

    op.create_table(
        "event_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("source", sa.String(50), nullable=False, server_default=sa.text("'api'")),
        sa.Column("tournament_id", UUID(as_uuid=True), nullable=True),
        sa.Column("actor_id", UUID(as_uuid=True), nullable=True),
        sa.Column("payload", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_event_logs_tournament", "event_logs", ["tournament_id", sa.text("created_at DESC")])
    op.create_index("ix_event_logs_type", "event_logs", ["event_type"])
    op.create_foreign_key(
        "fk_event_logs_tournament",
        "event_logs", "tournaments",
        ["tournament_id"], ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_event_logs_actor",
        "event_logs", "players",
        ["actor_id"], ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_table("event_logs")
    op.drop_table("tournaments")

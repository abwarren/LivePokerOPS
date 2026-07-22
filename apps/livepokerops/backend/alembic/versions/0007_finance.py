"""Add financial tracking: buy_ins and prize_pools tables.

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-22
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "buy_ins",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tournament_id", UUID(as_uuid=True), nullable=False),
        sa.Column("player_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "amount", sa.Numeric(12, 2), nullable=False,
        ),
        sa.Column(
            "type", sa.String(20), nullable=False,
            server_default=sa.text("'buy_in'"),
        ),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
    )
    op.create_foreign_key(
        "fk_bi_tournament", "buy_ins", "tournaments",
        ["tournament_id"], ["id"], ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_bi_player", "buy_ins", "players",
        ["player_id"], ["id"], ondelete="CASCADE",
    )
    op.create_index("ix_bi_tournament", "buy_ins", ["tournament_id"])
    op.create_index("ix_bi_player", "buy_ins", ["player_id"])
    op.create_index(
        "ix_bi_tournament_player", "buy_ins",
        ["tournament_id", "player_id"],
    )

    op.create_table(
        "prize_pools",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tournament_id", UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column(
            "total_buy_in", sa.Numeric(12, 2), nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "total_rebuys", sa.Numeric(12, 2), nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "total_addons", sa.Numeric(12, 2), nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "total_prize_pool", sa.Numeric(12, 2), nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "entries_count", sa.Integer, nullable=False,
            server_default=sa.text("0"),
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
    op.create_foreign_key(
        "fk_pp_tournament", "prize_pools", "tournaments",
        ["tournament_id"], ["id"], ondelete="CASCADE",
    )
    op.create_index("ix_pp_tournament", "prize_pools", ["tournament_id"])


def downgrade() -> None:
    op.drop_table("prize_pools")
    op.drop_table("buy_ins")

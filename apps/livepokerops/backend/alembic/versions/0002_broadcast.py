"""Add broadcast: message_templates, broadcasts, broadcast_recipients.

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Template categories matching Gareth's real workflow
    op.create_table(
        "message_templates",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "category", sa.String(50), nullable=False
        ),  # announcement, game_on, final_table, results, reminder
        sa.Column("body_template", sa.Text, nullable=False),  # template with {variables}
        sa.Column(
            "variables", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")
        ),  # ["date", "time", "player_count", ...]
        sa.Column("is_builtin", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_templates_category", "message_templates", ["category"])

    # Each broadcast send
    op.create_table(
        "broadcasts",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("template_id", UUID(as_uuid=True), nullable=True),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("rendered_body", sa.Text, nullable=False),
        sa.Column("variables_used", JSONB, nullable=True),  # snapshot of what was substituted
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'draft'")),
        # draft, scheduled, sent, failed, cancelled
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_by", UUID(as_uuid=True), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_foreign_key(
        "fk_broadcast_template",
        "broadcasts",
        "message_templates",
        ["template_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_broadcasts_status", "broadcasts", ["status"])
    op.create_index("ix_broadcasts_scheduled", "broadcasts", ["scheduled_for"])

    # Per-player delivery receipts
    op.create_table(
        "broadcast_recipients",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("broadcast_id", UUID(as_uuid=True), nullable=False),
        sa.Column("player_id", UUID(as_uuid=True), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False, server_default=sa.text("'whatsapp'")),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'pending'")),
        # pending, delivered, read, failed
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
    )
    op.create_foreign_key(
        "fk_recipient_broadcast",
        "broadcast_recipients",
        "broadcasts",
        ["broadcast_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_recipient_player",
        "broadcast_recipients",
        "players",
        ["player_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_recipients_broadcast", "broadcast_recipients", ["broadcast_id"])
    op.create_index("ix_recipients_player", "broadcast_recipients", ["player_id"])

    # Seed built-in templates from Gareth's actual messages
    op.execute("""
        INSERT INTO message_templates (name, description, category, body_template, variables, is_builtin) VALUES
        (
            'tournament_announcement',
            'Initial tournament announcement with player confirmation list',
            'announcement',
            E'FREEROLL SATELLITE TODAY AT {time}! {table_count} TABLES SO FAR! ♥️♠️♦️♣️\n\n_We need {needed_count} more confirmations!_\n\n{date}, {time}\n\n{tournament_name}\n\n{details}\n\nEXTRA INCENTIVE: We will try to accommodate sponsored cash among the top prizes to add some spice to the event!\n\nPlease note: We will need {min_players} players confirmed by {deadline_time} on {deadline_date} for the game to go ahead. This is to ensure the club can afford the operation costs of the venue.\n\nPLAYERS MUST BE SEATED BY THE END OF LEVEL 2 TO QUALIFY FOR A FREE ENTRY\n\n{confirmed_count} players confirmed so far:\n{player_list}',
            '["date", "time", "tournament_name", "details", "table_count", "confirmed_count", "needed_count", "min_players", "deadline_date", "deadline_time", "player_list"]',
            true
        ),
        (
            'game_on',
            'Game-on message confirming tournament is running',
            'game_on',
            E'GAME ON: {tournament_name} TODAY AT {time}! {table_count} TABLES SO FAR! ♥️♠️♦️♣️\n\n{date}, {time}\n\n{tournament_name}\n\nEXTRA INCENTIVE: We will try to accommodate sponsored cash among the top prizes to add some spice to the event!\n\nPLAYERS MUST BE SEATED BY THE END OF LEVEL 2 TO QUALIFY FOR A FREE ENTRY\n\n{confirmed_count} players confirmed so far:\n{player_list}\n\nRSVP HERE: {rsvp_link}',
            '["date", "time", "tournament_name", "table_count", "confirmed_count", "player_list", "rsvp_link"]',
            true
        ),
        (
            'friday_night_lights',
            'Kickoff message when tournament starts',
            'game_on',
            E'FRIDAY NIGHT LIGHTS! ♦️♣️♥️♠️ The Friday {tournament_name} has kicked off with {table_count} tables! With more players on the way, we''re set for a fun, social evening of poker sports! {late_levels} levels open for late registration (+/- {late_end_time}). Good luck to all players this evening.',
            '["tournament_name", "table_count", "late_levels", "late_end_time"]',
            true
        ),
        (
            'ultra_turbo_side',
            'Side game / ultra turbo announcement',
            'announcement',
            E'TURBO LEAGUE GAME STARTING SOON - {buyin} ULTRA TURBO! ♥️♠️♦️♣️\n\nWe already have {player_count} players in line for the {buyin} Ultra Turbo!\n\nA {buyin} Ultra Turbo side game is scheduled to kick off when a minimum 4 players are seated.\n\nExtra tournament for players knocked out… or new players wanting a cheaper game.\n\nEntry: {buyin}/{starting_chips} chips\nRebuy: {buyin}/{rebuy_chips} chips (max {max_rebuys} per player)\nAdd-on: {buyin}/{addon_chips} chips\n\nBlinds: {blind_minutes}mins. {addon_level} levels before the add-on break.\n\nCome enjoy some cheap live poker - quick format!',
            '["buyin", "starting_chips", "rebuy_chips", "max_rebuys", "addon_chips", "blind_minutes", "addon_level", "player_count"]',
            true
        ),
        (
            'final_table',
            'Final table chip count post',
            'final_table',
            E'{tournament_name}: WELL DONE FINAL TABLE! ♥️♠️♦️♣️\n\n{entry_count} unique entries filled the room tonight to enjoy a very relaxed and sociable evening with good company!\n\n{chip_leader} leads the field with just over {chip_leader_stack} chips!\n\nThe players are competing for {prize_pool} in sponsored prizes! Top {paid_places} will win their way into the {grand_prize} in August, with an extra cash incentive for first!\n\nGood luck to the Final {final_table_count}!\n\n{seating_chart}\n\nTime: {current_time}\nBlinds: {blind_level}\nChip count: {total_chips}\nAve stack: {average_stack}\nChip leader: {chip_leader} ({chip_leader_stack})',
            '["tournament_name", "entry_count", "chip_leader", "chip_leader_stack", "prize_pool", "paid_places", "grand_prize", "final_table_count", "seating_chart", "current_time", "blind_level", "total_chips", "average_stack"]',
            true
        ),
        (
            'results_recap',
            'Post-tournament results and prizewinners',
            'results',
            E'{winner_count} PLAYERS WIN PRIZES AT {tournament_name}! ♥️♠️♦️♣️\n\nThe {tournament_name} saw {winner_count} players win prizes for the {grand_prize}.\n\nThe {tournament_name} once again showcased the incredible value for the community, giving players the chance to turn a {entry_cost} into a seat for one of the most anticipated events on the club''s calendar.\n\nWith {prize_seats} x {prize_description} for grabs, plus an extra {bonus_prize} for first, we saw {entry_count} players grind their way to the sponsored prizes.\n\nAt the business end of final table, the final {deal_count} agreed on a friendly deal to see them earn something on the night.\n\n{results_details}',
            '["tournament_name", "winner_count", "grand_prize", "entry_cost", "prize_seats", "prize_description", "bonus_prize", "entry_count", "deal_count", "results_details"]',
            true
        ),
        (
            'reminder_deadline',
            'Reminder about approaching registration deadline',
            'reminder',
            E'⏰ REMINDER: {tournament_name} TODAY AT {time}!\n\nWe currently have {confirmed_count} players confirmed. We need {min_players} by {deadline_time} for the game to go ahead.\n\n{needed_count} spots still available!\n\nRSVP here: {rsvp_link}\n\nCurrent players:\n{player_list}',
            '["tournament_name", "time", "confirmed_count", "min_players", "deadline_time", "needed_count", "rsvp_link", "player_list"]',
            true
        ),
        (
            'ct_in_the_house',
            'Shout-out to travelling players',
            'announcement',
            E'CT IN THE HOUSE! ♦️♣️♥️♠️ GL to all the Cape Town players at {venue}. 💪🏽',
            '["venue"]',
            true
        )
    """)


def downgrade() -> None:
    op.drop_table("broadcast_recipients")
    op.drop_table("broadcasts")
    op.drop_table("message_templates")

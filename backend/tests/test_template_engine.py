import pytest
from app.services.template_engine import TemplateEngine


class TestTemplateEngine:
    def test_simple_variable_substitution(self):
        result = TemplateEngine.preview(
            "Hello {name}!",
            {"name": "Gareth"},
        )
        assert result == "Hello Gareth!"

    def test_multiple_variables(self):
        result = TemplateEngine.preview(
            "{player_count} players: {player_list}",
            {"player_count": 24, "player_list": ["Alice", "Bob", "Charlie"]},
        )
        assert result == "24 players: Alice\nBob\nCharlie"

    def test_missing_variable_renders_empty(self):
        result = TemplateEngine.preview(
            "Game at {time} on {date}",
            {"time": "7PM"},
        )
        assert result == "Game at 7PM on "

    def test_extract_variables(self):
        vars = TemplateEngine.extract_variables("Hello {name}, game at {time} on {date}")
        assert sorted(vars) == sorted(["name", "time", "date"])

    def test_extract_variables_deduplicates(self):
        vars = TemplateEngine.extract_variables("{name} says hello to {name}")
        assert vars == ["name"]

    def test_no_variables(self):
        result = TemplateEngine.preview("Plain text message", {})
        assert result == "Plain text message"

    def test_announcement_template(self):
        template = (
            "FREEROLL TODAY AT {time}! {table_count} TABLES!\n"
            "{confirmed_count} players confirmed:\n{player_list}"
        )
        result = TemplateEngine.preview(template, {
            "time": "7PM",
            "table_count": 3,
            "confirmed_count": 17,
            "player_list": ["Alice", "Bob", "Charlie"],
        })
        assert "FREEROLL TODAY AT 7PM!" in result
        assert "3 TABLES!" in result
        assert "17 players confirmed:" in result
        assert "Alice" in result
        assert "Charlie" in result

    def test_list_join_with_newlines(self):
        result = TemplateEngine.preview(
            "Players:\n{player_list}",
            {"player_list": ["Alice", "Bob", "Charlie"]},
        )
        assert result == "Players:\nAlice\nBob\nCharlie"

    def test_numeric_values(self):
        result = TemplateEngine.preview(
            "Buy-in: R{buyin}/ chips",
            {"buyin": 100},
        )
        assert result == "Buy-in: R100/ chips"

from __future__ import annotations

import re
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

VARIABLE_PATTERN = re.compile(r"\{(\w+)\}")


class TemplateEngine:
    """Renders message templates by substituting variables.

    Supports:
        - {variable_name} substitution
        - Lists join with newlines: {player_list} -> "Name1\nName2\nName3"
        - Missing variables rendered as empty string
    """

    def __init__(self, body_template: str, variables: dict[str, Any] | None = None):
        self.body_template = body_template
        self.variables = variables or {}

    def render(self) -> str:
        """Render the template with provided variables."""

        def _replace(match: re.Match) -> str:
            var_name = match.group(1)
            value = self.variables.get(var_name)
            if value is None:
                logger.warning("template_missing_variable", variable=var_name)
                return ""
            if isinstance(value, list):
                return "\n".join(str(v) for v in value)
            return str(value)

        return VARIABLE_PATTERN.sub(_replace, self.body_template)

    @staticmethod
    def extract_variables(body_template: str) -> list[str]:
        """Extract all variable names from a template string."""
        return list(set(VARIABLE_PATTERN.findall(body_template)))

    @staticmethod
    def preview(body_template: str, variables: dict[str, Any]) -> str:
        """Render a preview from raw template + variables."""
        engine = TemplateEngine(body_template, variables)
        return engine.render()

"""JSONC comment-stripping parser: the only place JSONC parse errors are caught.

Public surface:

- `JsoncParseError` — raised by `loads` on malformed JSONC input.
- `loads(*, text)` — strip `//` line comments, then parse as JSON; raises
  `JsoncParseError` on failure.
- `loads_optional(*, text)` — like `loads` but returns None on parse error;
  lets callers outside io/ avoid try/except.
"""

from __future__ import annotations

import json
import re
from typing import Any

__all__: list[str] = ["JsoncParseError", "loads", "loads_optional"]


class JsoncParseError(Exception):
    """Raised when the JSONC source does not parse as JSON after comment-strip."""

    def __init__(self, *, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


_TOKEN_PATTERN = re.compile(
    r'(?P<string>"(?:\\.|[^"\\])*")|(?P<comment>//[^\n]*)',
)


def _strip_line_comments(*, text: str) -> str:
    """Remove `//` line comments while preserving any `//` inside JSON strings."""
    return _TOKEN_PATTERN.sub(
        lambda m: m.group("string") if m.group("string") is not None else "",
        text,
    )


def loads(*, text: str) -> Any:
    """Parse a JSONC string and return the decoded Python value."""
    stripped = _strip_line_comments(text=text)
    try:
        return json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise JsoncParseError(detail=f"jsonc parse failed: {exc}") from exc


def loads_optional(*, text: str) -> Any:
    """Parse a JSONC string; return None instead of raising on parse failure."""
    try:
        return loads(text=text)
    except JsoncParseError:
        return None

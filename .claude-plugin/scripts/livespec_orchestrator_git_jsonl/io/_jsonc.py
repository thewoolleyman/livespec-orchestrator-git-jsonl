"""JSONC comment-stripping parser: the only place JSONC parse errors are caught.

Public surface:

- `JsoncParseError` — the failure `loads` carries on malformed JSONC input.
- `loads(*, text)` — strip `//` line comments, then parse as JSON, returning
  `Result[Any, JsoncParseError]`.

⚠️ `Result`, NOT `IOResult`: the comment-strip and the parse are PURE. The
file read is the caller's, and that is where the I/O boundary sits — putting
this on `IOResult` would claim an effect this module does not have.

⛔ THERE IS NO `loads_optional` ANY MORE, AND ITS ABSENCE IS THE POINT. It
existed only to swallow the raise back into `None` so that "callers outside
io/ avoid try/except" — which made this module the one place a NAMED parse
error became an anonymous `None`. A caller that genuinely wants the
absent-shaped answer now writes `loads(text=...).value_or(None)` at the call
site, where the choice to discard the reason is visible.
"""

from __future__ import annotations

import json
import re
from typing import Any

from returns.result import Failure, Result, Success

__all__: list[str] = ["JsoncParseError", "loads"]


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


def loads(*, text: str) -> Result[Any, JsoncParseError]:
    """Parse a JSONC string, or carry why it did not parse.

    The `try` stays: `json.loads` is the boundary that raises, and this is
    the one place in the package that converts that raise into a value.
    """
    stripped = _strip_line_comments(text=text)
    try:
        decoded: Any = json.loads(stripped)
    except json.JSONDecodeError as exc:
        return Failure(JsoncParseError(detail=f"jsonc parse failed: {exc}"))
    return Success(decoded)

"""JSONC parser — re-exports from `livespec_orchestrator_git_jsonl.io._jsonc`.

Public surface:

- `JsoncParseError` — the failure `loads` carries on malformed JSONC input.
- `loads(*, text)` — parse a JSONC string, returning
  `Result[Any, JsoncParseError]`. Malformed input is the only EXPECTED
  failure per the Result-vs-bugs split, and it now rides the failure track
  instead of being raised.
"""

from __future__ import annotations

from livespec_orchestrator_git_jsonl.io._jsonc import JsoncParseError, loads

__all__: list[str] = ["JsoncParseError", "loads"]

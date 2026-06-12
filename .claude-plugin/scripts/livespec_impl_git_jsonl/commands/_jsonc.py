"""JSONC parser — re-exports from `livespec_impl_git_jsonl.io._jsonc`.

Public surface:

- `JsoncParseError` — raised by `loads` on malformed JSONC input.
- `loads(*, text)` — parse a JSONC string. Raises `JsoncParseError` on
  malformed input (the only EXPECTED error per the Result-vs-bugs split).
"""

from __future__ import annotations

from livespec_impl_git_jsonl.io._jsonc import JsoncParseError, loads

__all__: list[str] = ["JsoncParseError", "loads"]

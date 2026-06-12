"""Raw JSONL file I/O primitives: the only place file-open and JSON-parse errors are caught.

Public surface:

- `parse_jsonl_line(*, path, line_number, raw_line)` — strip trailing
  newline, check for empty, parse as JSON, verify dict; raises
  `MalformedRecordLineError` on any failure.
- `iter_records(*, path)` — open path and yield `(line_number, dict)`
  for each line; raises `StoreFileMissingError` if absent.
- `append_record(*, path, payload)` — write one JSON line to path,
  creating parents as needed.
"""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

from livespec_impl_git_jsonl.errors import MalformedRecordLineError, StoreFileMissingError

__all__: list[str] = ["append_record", "iter_records", "parse_jsonl_line"]


def parse_jsonl_line(*, path: Path, line_number: int, raw_line: str) -> dict[str, Any]:
    """Parse one raw JSONL line into a dict; raise MalformedRecordLineError on failure."""
    stripped = raw_line.rstrip("\n")
    if stripped == "":
        raise MalformedRecordLineError(
            path=path,
            line_number=line_number,
            raw_line=raw_line,
            detail="empty line not permitted between records",
        )
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise MalformedRecordLineError(
            path=path,
            line_number=line_number,
            raw_line=raw_line,
            detail=f"JSON parse error: {exc.msg}",
        ) from exc
    if not isinstance(parsed, dict):
        raise MalformedRecordLineError(
            path=path,
            line_number=line_number,
            raw_line=raw_line,
            detail="record root must be a JSON object",
        )
    return cast(dict[str, Any], parsed)


def iter_records(*, path: Path) -> Iterator[tuple[int, dict[str, Any]]]:
    """Stream `(line_number, parsed_dict)` pairs from the JSONL file at `path`."""
    if not path.exists():
        raise StoreFileMissingError(path=path)
    with path.open(encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            yield (
                line_number,
                parse_jsonl_line(path=path, line_number=line_number, raw_line=raw_line),
            )


def append_record(*, path: Path, payload: dict[str, Any]) -> None:
    """Append `payload` as one JSON line to `path`, creating parents if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n"
    with path.open("a", encoding="utf-8") as handle:
        _ = handle.write(line)

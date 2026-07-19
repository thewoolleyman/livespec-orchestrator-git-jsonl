"""Raw JSONL file I/O primitives: the only place file-open and JSON-parse errors are caught.

Public surface:

- `parse_jsonl_line(*, path, line_number, raw_line)` — strip trailing
  newline, check for empty, parse as JSON, verify dict; returns
  `Failure(MalformedRecordLineError)` on expected parse failures.
- `iter_records(*, path)` — read path and return every `(line_number, dict)`
  pair as an `IOResult`; missing or malformed files ride the failure track.
- `append_record(*, path, payload)` — write one JSON line to path,
  creating parents as needed, returning an `IOResult`.
"""

import json
from pathlib import Path
from typing import Any, cast

from returns.io import IOFailure, IOResult, IOSuccess
from returns.result import Failure, Result, Success

from livespec_orchestrator_git_jsonl.errors import MalformedRecordLineError, StoreFileMissingError

__all__: list[str] = ["append_record", "iter_records", "parse_jsonl_line"]


def parse_jsonl_line(
    *, path: Path, line_number: int, raw_line: str
) -> Result[dict[str, Any], MalformedRecordLineError]:
    """Parse one raw JSONL line into a dict on the Result railway."""
    stripped = raw_line.rstrip("\n")
    if stripped == "":
        return Failure(
            MalformedRecordLineError(
                path=path,
                line_number=line_number,
                raw_line=raw_line,
                detail="empty line not permitted between records",
            )
        )
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError as exc:
        return Failure(
            MalformedRecordLineError(
                path=path,
                line_number=line_number,
                raw_line=raw_line,
                detail=f"JSON parse error: {exc.msg}",
            )
        )
    if not isinstance(parsed, dict):
        return Failure(
            MalformedRecordLineError(
                path=path,
                line_number=line_number,
                raw_line=raw_line,
                detail="record root must be a JSON object",
            )
        )
    return Success(cast(dict[str, Any], parsed))


def iter_records(
    *, path: Path
) -> IOResult[list[tuple[int, dict[str, Any]]], StoreFileMissingError | MalformedRecordLineError]:
    """Read `(line_number, parsed_dict)` pairs from the JSONL file at `path`."""
    if not path.exists():
        return IOFailure(StoreFileMissingError(path=path))
    records: list[tuple[int, dict[str, Any]]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            parsed = parse_jsonl_line(path=path, line_number=line_number, raw_line=raw_line)
            if isinstance(parsed, Failure):
                return IOFailure(parsed.failure())
            records.append((line_number, parsed.unwrap()))
    return IOSuccess(records)


def append_record(*, path: Path, payload: dict[str, Any]) -> IOResult[None, OSError]:
    """Append `payload` as one JSON line to `path`, creating parents if needed."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n"
        with path.open("a", encoding="utf-8") as handle:
            _ = handle.write(line)
    except OSError as exc:
        return IOFailure(exc)
    return IOSuccess(None)

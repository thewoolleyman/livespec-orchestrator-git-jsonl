"""JSONL store primitives for work-items and memos.

Per SPECIFICATION/contracts.md §"Work-items JSONL record schema" /
§"Memos JSONL record schema" and SPECIFICATION/constraints.md §"JSONL
substrate constraints", the store is append-only at the write boundary
and the materialized view is the LAST record per `id`.

Public API:

- `read_work_items(*, path)` — stream WorkItem records from the file
  (raises StoreFileMissingError if absent).
- `read_memos(*, path)` — stream Memo records (analogous).
- `append_work_item(*, path, item)` / `append_memo(*, path, memo)` —
  write a new record line.
- `materialize_work_items(records)` / `materialize_memos(records)` —
  reduce a stream to the latest-record-per-id dict.

The reader functions validate every record against the schema; a
violation raises SchemaViolationError carrying the offending line
number. A non-JSON line raises MalformedRecordLineError. Both are
EXPECTED errors per the Result-vs-bugs split.
"""

import json
from collections.abc import Iterator
from dataclasses import asdict
from pathlib import Path
from typing import Any, get_args

from livespec_impl_plaintext.errors import (
    MalformedRecordLineError,
    SchemaViolationError,
    StoreFileMissingError,
)
from livespec_impl_plaintext.types import (
    AuditRecord,
    Disposition,
    Memo,
    MemoState,
    Origin,
    Resolution,
    WorkItem,
    WorkItemStatus,
    WorkItemType,
)

_WORK_ITEM_REQUIRED_KEYS = frozenset(
    {
        "id",
        "type",
        "status",
        "title",
        "description",
        "origin",
        "gap_id",
        "priority",
        "assignee",
        "depends_on",
        "captured_at",
        "resolution",
        "reason",
        "audit",
        "superseded_by",
    }
)

_MEMO_REQUIRED_KEYS = frozenset(
    {
        "id",
        "text",
        "state",
        "disposition",
        "captured_at",
        "work_item_id",
        "knowledge_file",
        "propose_change_topic",
    }
)


def read_work_items(*, path: Path) -> Iterator[WorkItem]:
    """Stream WorkItem records from the JSONL file at `path`."""
    for line_number, parsed in _iter_records(path=path):
        yield _parse_work_item(path=path, line_number=line_number, parsed=parsed)


def read_memos(*, path: Path) -> Iterator[Memo]:
    """Stream Memo records from the JSONL file at `path`."""
    for line_number, parsed in _iter_records(path=path):
        yield _parse_memo(path=path, line_number=line_number, parsed=parsed)


def append_work_item(*, path: Path, item: WorkItem) -> None:
    """Append a single WorkItem as a new line in the JSONL file."""
    _append_record(path=path, payload=_work_item_to_dict(item=item))


def append_memo(*, path: Path, memo: Memo) -> None:
    """Append a single Memo as a new line in the JSONL file."""
    _append_record(path=path, payload=_memo_to_dict(memo=memo))


def materialize_work_items(records: Iterator[WorkItem]) -> dict[str, WorkItem]:
    """Reduce a WorkItem stream to the latest-record-per-id dict."""
    return {record.id: record for record in records}


def materialize_memos(records: Iterator[Memo]) -> dict[str, Memo]:
    """Reduce a Memo stream to the latest-record-per-id dict."""
    return {record.id: record for record in records}


def _iter_records(*, path: Path) -> Iterator[tuple[int, dict[str, Any]]]:
    if not path.exists():
        raise StoreFileMissingError(path=path)
    with path.open(encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
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
            yield line_number, parsed


def _append_record(*, path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n"
    with path.open("a", encoding="utf-8") as handle:
        _ = handle.write(line)


def _parse_work_item(*, path: Path, line_number: int, parsed: dict[str, Any]) -> WorkItem:
    _check_required_keys(
        path=path,
        line_number=line_number,
        parsed=parsed,
        required=_WORK_ITEM_REQUIRED_KEYS,
    )
    _check_in_enum(
        path=path,
        line_number=line_number,
        field_name="type",
        value=parsed["type"],
        allowed=get_args(WorkItemType),
    )
    _check_in_enum(
        path=path,
        line_number=line_number,
        field_name="status",
        value=parsed["status"],
        allowed=get_args(WorkItemStatus),
    )
    _check_in_enum(
        path=path,
        line_number=line_number,
        field_name="origin",
        value=parsed["origin"],
        allowed=get_args(Origin),
    )
    resolution_value = parsed["resolution"]
    if resolution_value is not None:
        _check_in_enum(
            path=path,
            line_number=line_number,
            field_name="resolution",
            value=resolution_value,
            allowed=get_args(Resolution),
        )
    audit_value = parsed["audit"]
    audit_record = (
        None
        if audit_value is None
        else _parse_audit(path=path, line_number=line_number, parsed=audit_value)
    )
    return WorkItem(
        id=parsed["id"],
        type=parsed["type"],
        status=parsed["status"],
        title=parsed["title"],
        description=parsed["description"],
        origin=parsed["origin"],
        gap_id=parsed["gap_id"],
        priority=parsed["priority"],
        assignee=parsed["assignee"],
        depends_on=tuple(parsed["depends_on"]),
        captured_at=parsed["captured_at"],
        resolution=resolution_value,
        reason=parsed["reason"],
        audit=audit_record,
        superseded_by=parsed["superseded_by"],
    )


def _parse_audit(*, path: Path, line_number: int, parsed: dict[str, Any]) -> AuditRecord:
    required = frozenset({"verification_timestamp", "commits", "files_changed"})
    missing = required - parsed.keys()
    if missing:
        raise SchemaViolationError(
            path=path,
            line_number=line_number,
            detail=f"audit object missing keys: {sorted(missing)}",
        )
    return AuditRecord(
        verification_timestamp=parsed["verification_timestamp"],
        commits=tuple(parsed["commits"]),
        files_changed=tuple(parsed["files_changed"]),
    )


def _parse_memo(*, path: Path, line_number: int, parsed: dict[str, Any]) -> Memo:
    _check_required_keys(
        path=path,
        line_number=line_number,
        parsed=parsed,
        required=_MEMO_REQUIRED_KEYS,
    )
    _check_in_enum(
        path=path,
        line_number=line_number,
        field_name="state",
        value=parsed["state"],
        allowed=get_args(MemoState),
    )
    disposition_value = parsed["disposition"]
    if disposition_value is not None:
        _check_in_enum(
            path=path,
            line_number=line_number,
            field_name="disposition",
            value=disposition_value,
            allowed=get_args(Disposition),
        )
    return Memo(
        id=parsed["id"],
        text=parsed["text"],
        state=parsed["state"],
        disposition=disposition_value,
        captured_at=parsed["captured_at"],
        work_item_id=parsed["work_item_id"],
        knowledge_file=parsed["knowledge_file"],
        propose_change_topic=parsed["propose_change_topic"],
    )


def _check_required_keys(
    *,
    path: Path,
    line_number: int,
    parsed: dict[str, Any],
    required: frozenset[str],
) -> None:
    parsed_keys = frozenset(parsed.keys())
    missing = required - parsed_keys
    extra = parsed_keys - required
    if missing:
        raise SchemaViolationError(
            path=path,
            line_number=line_number,
            detail=f"missing required keys: {sorted(missing)}",
        )
    if extra:
        raise SchemaViolationError(
            path=path,
            line_number=line_number,
            detail=f"unexpected extra keys: {sorted(extra)}",
        )


def _check_in_enum(
    *,
    path: Path,
    line_number: int,
    field_name: str,
    value: object,
    allowed: tuple[str, ...],
) -> None:
    if value not in allowed:
        raise SchemaViolationError(
            path=path,
            line_number=line_number,
            detail=(f"field {field_name!r} value {value!r} not in allowed set {list(allowed)}"),
        )


def _work_item_to_dict(*, item: WorkItem) -> dict[str, Any]:
    payload = asdict(item)
    payload["depends_on"] = list(item.depends_on)
    if item.audit is not None:
        payload["audit"] = {
            "verification_timestamp": item.audit.verification_timestamp,
            "commits": list(item.audit.commits),
            "files_changed": list(item.audit.files_changed),
        }
    return payload


def _memo_to_dict(*, memo: Memo) -> dict[str, Any]:
    return asdict(memo)

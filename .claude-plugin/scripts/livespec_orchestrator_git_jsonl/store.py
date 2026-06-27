"""JSONL store primitives for work-items.

Per SPECIFICATION/contracts.md, the store is
append-only at the write boundary and the materialized view of an
entity is its supersession-chain head, computed from the in-record
`supersedes` pointers independently of the physical order of records in
the file (git may reorder lines during a merge; the legacy "latest
record by file order wins" reduction is retired).

The canonical PURE reduction — `work_item_record_identity`,
`reduce_work_item_heads`, `materialize_work_items` — is the SHARED
surface this repo donated byte-faithfully to the W7 extraction; it now
lives in `livespec_runtime.work_items.reduce` and is RE-EXPORTED here so
every consumer keeps importing it from `livespec_orchestrator_git_jsonl.store`
unchanged. What stays LOCAL is the JSONL-specific backend I/O
(`read_work_items` / `append_work_item` over `io/store.py`), the
JSONL-schema validators (`_validate_work_item_payload` / `_check_*` /
`_validate_audit_payload`), and the dict<->WorkItem boundary
(`_parse_work_item` on read, `_work_item_to_dict` on write).

`JsonlWorkItemStore` is the thin facade that conforms this repo's
backend to the shared `livespec_runtime.work_items.store.WorkItemStore`
Protocol (a stream of records out, one record in) without rewriting any
call site; the module-level `_: type[WorkItemStore]` binding makes
pyright attest that conformance statically.

Public API:

- `read_work_items(*, path)` — stream WorkItem records from the file
  (raises StoreFileMissingError if absent).
- `append_work_item(*, path, item)` — write a new record line.
- `work_item_record_identity(*, item)` — re-exported canonical
  per-record identity (`sha256:<hex-digest>` over the canonical
  serialization).
- `reduce_work_item_heads(*, records)` — re-exported canonical
  order-independent head reduction.
- `materialize_work_items(*, records)` — re-exported reduction to the
  current-head-per-id dict.
- `JsonlWorkItemStore` — the WorkItemStore-conforming facade over the
  free functions above.

The reader functions validate every record against the schema; a
violation raises SchemaViolationError carrying the offending line
number. A non-JSON line raises MalformedRecordLineError. Both are
EXPECTED errors per the Result-vs-bugs split.
"""

from collections.abc import Iterator
from dataclasses import asdict
from pathlib import Path
from typing import Any, get_args

from livespec_runtime.work_items.reduce import (
    materialize_work_items,
    reduce_work_item_heads,
    work_item_record_identity,
)
from livespec_runtime.work_items.store import WorkItemStore

from livespec_orchestrator_git_jsonl.errors import SchemaViolationError
from livespec_orchestrator_git_jsonl.io.store import (
    append_record as _io_append_record,
)
from livespec_orchestrator_git_jsonl.io.store import (
    iter_records as _io_iter_records,
)
from livespec_orchestrator_git_jsonl.types import (
    AuditRecord,
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

# OPTIONAL work-item keys: present in records authored after their
# introduction; missing in legacy records pre-dating their landing.
# Read path treats absence as `None`; write path always serializes
# (per livespec PC #4 sub-proposal 3 — `spec_commitment_hint` — and
# the v008 append-only-store disciplines — `supersedes`).
_WORK_ITEM_OPTIONAL_KEYS = frozenset({"spec_commitment_hint", "supersedes"})

_WORK_ITEM_ALLOWED_KEYS = _WORK_ITEM_REQUIRED_KEYS | _WORK_ITEM_OPTIONAL_KEYS

__all__: list[str] = [
    "JsonlWorkItemStore",
    "append_work_item",
    "materialize_work_items",
    "read_work_items",
    "reduce_work_item_heads",
    "work_item_record_identity",
]


def read_work_items(*, path: Path) -> Iterator[WorkItem]:
    """Stream WorkItem records from the JSONL file at `path`."""
    for line_number, parsed in _iter_records(path=path):
        yield _parse_work_item(path=path, line_number=line_number, parsed=parsed)


def append_work_item(*, path: Path, item: WorkItem) -> None:
    """Append a single WorkItem as a new line in the JSONL file.

    Validates the dict-serialized payload against the same schema the
    read path enforces before writing; raises SchemaViolationError when
    the payload would not round-trip through `read_work_items`. The
    write is symmetric with the read so a record landing on disk is
    guaranteed to parse back cleanly.
    """
    payload = _work_item_to_dict(item=item)
    _validate_work_item_payload(path=path, line_number=0, parsed=payload)
    _append_record(path=path, payload=payload)


class JsonlWorkItemStore:
    """WorkItemStore-conforming facade over this repo's JSONL backend.

    Conforms structurally to
    `livespec_runtime.work_items.store.WorkItemStore` by exposing the two
    Protocol operations over the module-level free functions, binding the
    single JSONL `Path` (git-jsonl's `StoreConfig` wraps exactly one
    `Path`, `work_items_path`, which is passed here directly). No call site
    is rewritten: tools that want the Protocol view construct this facade;
    everything else keeps calling the free functions.
    """

    def __init__(self, *, path: Path) -> None:
        self._path = path

    def read_work_items(self) -> Iterator[WorkItem]:
        """Stream every WorkItem record the backing JSONL file holds."""
        return read_work_items(path=self._path)

    def append_work_item(self, *, item: WorkItem) -> None:
        """Append a single WorkItem record to the backing JSONL file."""
        append_work_item(path=self._path, item=item)


# Static conformance assertion: pyright rejects this binding if
# JsonlWorkItemStore stops satisfying the WorkItemStore Protocol.
_: type[WorkItemStore] = JsonlWorkItemStore


def _iter_records(*, path: Path) -> Iterator[tuple[int, dict[str, Any]]]:
    yield from _io_iter_records(path=path)


def _append_record(*, path: Path, payload: dict[str, Any]) -> None:
    _io_append_record(path=path, payload=payload)


def _validate_work_item_payload(
    *,
    path: Path,
    line_number: int,
    parsed: dict[str, Any],
) -> None:
    """Verify a work-item dict satisfies the schema contract.

    Shared by the read path (parse) and the write path (append).
    Raises SchemaViolationError on any deviation; returns None on
    success. The `line_number=0` sentinel is used by the append path
    to indicate the validation happened pre-write, not against a
    specific line on disk.
    """
    _check_required_keys(
        path=path,
        line_number=line_number,
        parsed=parsed,
        required=_WORK_ITEM_REQUIRED_KEYS,
        optional=_WORK_ITEM_OPTIONAL_KEYS,
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
    if audit_value is not None:
        _validate_audit_payload(
            path=path,
            line_number=line_number,
            parsed=audit_value,
        )
    _check_optional_string_key(
        path=path,
        line_number=line_number,
        parsed=parsed,
        key="spec_commitment_hint",
    )
    _check_optional_string_key(
        path=path,
        line_number=line_number,
        parsed=parsed,
        key="supersedes",
    )


def _parse_work_item(*, path: Path, line_number: int, parsed: dict[str, Any]) -> WorkItem:
    _validate_work_item_payload(path=path, line_number=line_number, parsed=parsed)
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
        resolution=parsed["resolution"],
        reason=parsed["reason"],
        audit=audit_record,
        superseded_by=parsed["superseded_by"],
        spec_commitment_hint=parsed.get("spec_commitment_hint"),
        supersedes=parsed.get("supersedes"),
    )


def _validate_audit_payload(
    *,
    path: Path,
    line_number: int,
    parsed: dict[str, Any],
) -> None:
    """Verify an audit sub-object's required keys and merge-evidence fields.

    Per SPECIFICATION/contracts.md "Work-items JSONL record schema" -> audit,
    `merge_sha` is a required, non-empty string and `pr_number` (when present)
    is an integer or null. `pr_number` is optional-on-read so audit objects
    authored before the field landed still parse cleanly.
    """
    required = frozenset({"verification_timestamp", "commits", "files_changed", "merge_sha"})
    missing = required - parsed.keys()
    if missing:
        raise SchemaViolationError(
            path=path,
            line_number=line_number,
            detail=f"audit object missing keys: {sorted(missing)}",
        )
    merge_sha_value = parsed["merge_sha"]
    if not isinstance(merge_sha_value, str) or merge_sha_value == "":
        raise SchemaViolationError(
            path=path,
            line_number=line_number,
            detail="audit field 'merge_sha' must be a non-empty string",
        )
    if "pr_number" in parsed:
        pr_number_value = parsed["pr_number"]
        is_valid_pr_number = pr_number_value is None or (
            isinstance(pr_number_value, int) and not isinstance(pr_number_value, bool)
        )
        if not is_valid_pr_number:
            raise SchemaViolationError(
                path=path,
                line_number=line_number,
                detail=(
                    f"audit field 'pr_number' must be an integer or null, "
                    f"got {type(pr_number_value).__name__}"
                ),
            )


def _parse_audit(*, path: Path, line_number: int, parsed: dict[str, Any]) -> AuditRecord:
    _validate_audit_payload(path=path, line_number=line_number, parsed=parsed)
    return AuditRecord(
        verification_timestamp=parsed["verification_timestamp"],
        commits=tuple(parsed["commits"]),
        files_changed=tuple(parsed["files_changed"]),
        merge_sha=parsed["merge_sha"],
        pr_number=parsed.get("pr_number"),
    )


def _check_required_keys(
    *,
    path: Path,
    line_number: int,
    parsed: dict[str, Any],
    required: frozenset[str],
    optional: frozenset[str] = frozenset(),
) -> None:
    """Verify `parsed` carries exactly the union of required + optional keys.

    Required keys MUST be present (missing → SchemaViolationError).
    Optional keys MAY be present (their absence is silent; consumers
    default the field on read). Any key outside `required | optional`
    is an unexpected extra and fires SchemaViolationError.

    The optional set lets new schema fields land without rejecting
    legacy records that pre-date the field — see PC #4 sub-proposal
    3 (`spec_commitment_hint`).
    """
    parsed_keys = frozenset(parsed.keys())
    allowed = required | optional
    missing = required - parsed_keys
    extra = parsed_keys - allowed
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


def _check_optional_string_key(
    *,
    path: Path,
    line_number: int,
    parsed: dict[str, Any],
    key: str,
) -> None:
    """Verify an optional-on-read key, when present, is string or null."""
    if key not in parsed:
        return
    value = parsed[key]
    if value is not None and not isinstance(value, str):
        raise SchemaViolationError(
            path=path,
            line_number=line_number,
            detail=(f"field {key!r} must be string or null, got {type(value).__name__}"),
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
            "merge_sha": item.audit.merge_sha,
            "pr_number": item.audit.pr_number,
        }
    return payload

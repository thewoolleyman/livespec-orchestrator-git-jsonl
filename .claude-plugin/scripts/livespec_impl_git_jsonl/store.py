"""JSONL store primitives for work-items.

Per SPECIFICATION/contracts.md §"Work-items JSONL record schema" /
§"Materialized view" / §"Append-only store disciplines", the store is
append-only at the write boundary and the materialized view of an
entity is its supersession-chain head, computed from the in-record
`supersedes` pointers independently of the physical order of records in
the file (git may reorder lines during a merge; the legacy "latest
record by file order wins" reduction is retired).

Public API:

- `read_work_items(*, path)` — stream WorkItem records from the file
  (raises StoreFileMissingError if absent).
- `append_work_item(*, path, item)` — write a new record line.
- `work_item_record_identity(*, item)` — the stable per-record
  identity: `sha256:<hex-digest>` over the record's canonical
  serialization (every schema key explicit, sorted keys, compact
  separators — exactly the line bytes the append path writes, without
  the trailing newline). Derivable from record content alone; the
  value a superseding record carries in its `supersedes` key.
- `reduce_work_item_heads(*, records)` — the canonical
  order-independent reduction: per entity `id`, every record whose
  identity no sibling record's `supersedes` names, ordered ascending by
  the deterministic tie-break (`captured_at`, then per-record
  identity). Identical records (equal identity — e.g. a line
  duplicated by a `merge=union` merge) collapse to one. More than one
  head for an `id` is concurrent divergence, surfaced for detection
  rather than silently resolved.
- `materialize_work_items(records)` — reduce a stream to the
  current-head-per-id dict (the tie-break winner among each entity's
  heads).

The reader functions validate every record against the schema; a
violation raises SchemaViolationError carrying the offending line
number. A non-JSON line raises MalformedRecordLineError. Both are
EXPECTED errors per the Result-vs-bugs split.
"""

import hashlib
import json
from collections.abc import Iterator
from dataclasses import asdict
from pathlib import Path
from typing import Any, Protocol, TypeVar, get_args

from livespec_impl_git_jsonl.errors import SchemaViolationError
from livespec_impl_git_jsonl.io.store import (
    append_record as _io_append_record,
)
from livespec_impl_git_jsonl.io.store import (
    iter_records as _io_iter_records,
)
from livespec_impl_git_jsonl.types import (
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
    "append_work_item",
    "materialize_work_items",
    "read_work_items",
    "reduce_work_item_heads",
    "work_item_record_identity",
]


class _SupersedableRecord(Protocol):
    """Structural shape the canonical head reduction consumes."""

    @property
    def id(self) -> str: ...

    @property
    def captured_at(self) -> str: ...

    @property
    def supersedes(self) -> str | None: ...


_RecordT = TypeVar("_RecordT", bound=_SupersedableRecord)


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


def work_item_record_identity(*, item: WorkItem) -> str:
    """Return the stable per-record identity of a work-item record.

    `sha256:<hex-digest>` over the record's canonical serialization
    (all sixteen schema keys explicit, sorted, compact separators).
    Legacy records read back from disk without the optional keys
    normalize to the same canonical form, so the identity is a pure
    function of record content — no file positions, no external state.
    """
    return _record_identity(payload=_work_item_to_dict(item=item))


def reduce_work_item_heads(*, records: Iterator[WorkItem]) -> dict[str, tuple[WorkItem, ...]]:
    """Reduce a WorkItem stream to the un-superseded heads per `id`.

    The canonical order-independent reduction per
    SPECIFICATION/contracts.md §"Materialized view": each entity's
    heads are the records whose identity no sibling record's
    `supersedes` pointer names, in ascending tie-break order
    (`captured_at`, then per-record identity). A tuple longer than one
    is concurrent divergence — representable and detectable, never
    silently resolved here.
    """
    entries = ((work_item_record_identity(item=record), record) for record in records)
    return _reduce_heads(entries=entries)


def materialize_work_items(*, records: Iterator[WorkItem]) -> dict[str, WorkItem]:
    """Reduce a WorkItem stream to the current-head-per-id dict.

    The current head is the supersession-chain head; when an entity
    has divergent heads the deterministic tie-break winner (greatest
    `captured_at`, then greatest per-record identity) is returned.
    Consumers that must DETECT divergence consume
    `reduce_work_item_heads` directly.
    """
    return {
        entity_id: heads[-1] for entity_id, heads in reduce_work_item_heads(records=records).items()
    }


def _record_identity(*, payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _reduce_heads(
    *,
    entries: Iterator[tuple[str, _RecordT]],
) -> dict[str, tuple[_RecordT, ...]]:
    groups: dict[str, dict[str, _RecordT]] = {}
    for identity, record in entries:
        groups.setdefault(record.id, {})[identity] = record
    heads: dict[str, tuple[_RecordT, ...]] = {}
    for entity_id, group in groups.items():
        superseded = frozenset(
            record.supersedes for record in group.values() if record.supersedes is not None
        )
        unsuperseded = {
            identity: record for identity, record in group.items() if identity not in superseded
        }
        tie_break_order = sorted(
            (record.captured_at, identity) for identity, record in unsuperseded.items()
        )
        heads[entity_id] = tuple(unsuperseded[identity] for _, identity in tie_break_order)
    return heads


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

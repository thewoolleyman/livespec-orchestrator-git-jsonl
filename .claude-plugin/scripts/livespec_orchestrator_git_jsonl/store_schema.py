"""Work-item JSONL schema validation and dict conversion."""

from pathlib import Path
from typing import Any, get_args

from livespec_orchestrator_git_jsonl.errors import SchemaViolationError
from livespec_orchestrator_git_jsonl.store_audit_schema import validate_audit_payload
from livespec_orchestrator_git_jsonl.types import (
    FactorySafety,
    Origin,
    Resolution,
    WorkItem,
    WorkItemStatus,
    WorkItemType,
)

__all__: list[str] = [
    "parse_work_item",
    "validate_work_item_payload",
    "work_item_to_dict",
]

_WORK_ITEM_REQUIRED_KEYS = frozenset(
    {
        "id",
        "type",
        "status",
        "title",
        "description",
        "origin",
        "gap_id",
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
#
# `rank` (the v013 lifecycle schema; livespec-runtime v0.5.0) is
# required-on-WRITE (every WorkItem the store serializes carries it) but
# optional-on-READ: a legacy line authored before `rank` reads back as the
# shared bottom-sentinel `livespec_runtime.work_items.rank.BOTTOM_SENTINEL`
# (the store-adapter substitution — NOT nullability in the domain type),
# so it sits in the optional-presence set, not the required set. `priority`
# was removed in v013 (`rank` is the sole ordering authority); it is NOT a
# tolerated key — a record carrying it is a schema violation.
_WORK_ITEM_OPTIONAL_KEYS = frozenset(
    {
        "rank",
        "spec_commitment_hint",
        "supersedes",
        "acceptance_criteria",
        "notes",
        "factory_safety",
    }
)

_WORK_ITEM_ALLOWED_KEYS = _WORK_ITEM_REQUIRED_KEYS | _WORK_ITEM_OPTIONAL_KEYS


def validate_work_item_payload(
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
        validate_audit_payload(
            path=path,
            line_number=line_number,
            parsed=audit_value,
        )
    _check_optional_string_key(
        path=path,
        line_number=line_number,
        parsed=parsed,
        key="rank",
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
    _check_optional_string_key(
        path=path,
        line_number=line_number,
        parsed=parsed,
        key="acceptance_criteria",
    )
    _check_optional_string_key(
        path=path,
        line_number=line_number,
        parsed=parsed,
        key="notes",
    )
    factory_safety_value = parsed.get("factory_safety")
    if factory_safety_value is not None:
        _check_in_enum(
            path=path,
            line_number=line_number,
            field_name="factory_safety",
            value=factory_safety_value,
            allowed=get_args(FactorySafety),
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


def parse_work_item(*, path: Path, line_number: int, parsed: dict[str, Any]) -> WorkItem:
    from livespec_orchestrator_git_jsonl.store_codec import parse_work_item as parse

    return parse(path=path, line_number=line_number, parsed=parsed)


def work_item_to_dict(*, item: WorkItem) -> dict[str, Any]:
    from livespec_orchestrator_git_jsonl.store_codec import work_item_to_dict as serialize

    return serialize(item=item)

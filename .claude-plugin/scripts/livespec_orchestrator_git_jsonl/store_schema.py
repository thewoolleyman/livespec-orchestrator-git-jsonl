"""Work-item JSONL schema validation and dict conversion."""

from pathlib import Path
from typing import Any, get_args

from returns.result import Failure, Result, Success

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
) -> Result[None, SchemaViolationError]:
    """Verify a work-item dict satisfies the schema contract on the Result railway."""
    error = _work_item_schema_error(path=path, line_number=line_number, parsed=parsed)
    if error is not None:
        return Failure(error)
    return Success(None)


def _work_item_schema_error(
    *, path: Path, line_number: int, parsed: dict[str, Any]
) -> SchemaViolationError | None:
    required_or_enum = _required_or_enum_error(
        path=path,
        line_number=line_number,
        parsed=parsed,
    )
    if required_or_enum is not None:
        return required_or_enum
    audit = _audit_error(path=path, line_number=line_number, parsed=parsed)
    if audit is not None:
        return audit
    optional = _optional_fields_error(path=path, line_number=line_number, parsed=parsed)
    if optional is not None:
        return optional
    return _factory_safety_error(path=path, line_number=line_number, parsed=parsed)


def _required_or_enum_error(
    *, path: Path, line_number: int, parsed: dict[str, Any]
) -> SchemaViolationError | None:
    required_error = _check_required_keys(
        path=path,
        line_number=line_number,
        parsed=parsed,
        required=_WORK_ITEM_REQUIRED_KEYS,
        optional=_WORK_ITEM_OPTIONAL_KEYS,
    )
    if required_error is not None:
        return required_error
    return _first_enum_error(
        path=path,
        line_number=line_number,
        fields=(
            ("type", parsed["type"], get_args(WorkItemType)),
            ("status", parsed["status"], get_args(WorkItemStatus)),
            ("origin", parsed["origin"], get_args(Origin)),
            ("resolution", parsed["resolution"], get_args(Resolution)),
        ),
    )


def _first_enum_error(
    *,
    path: Path,
    line_number: int,
    fields: tuple[tuple[str, object, tuple[str, ...]], ...],
) -> SchemaViolationError | None:
    for field_name, value, allowed in fields:
        if field_name == "resolution" and value is None:
            continue
        enum_error = _check_in_enum(
            path=path,
            line_number=line_number,
            field_name=field_name,
            value=value,
            allowed=allowed,
        )
        if enum_error is not None:
            return enum_error
    return None


def _audit_error(
    *, path: Path, line_number: int, parsed: dict[str, Any]
) -> SchemaViolationError | None:
    audit_value = parsed["audit"]
    if audit_value is None:
        return None
    audit_result = validate_audit_payload(
        path=path,
        line_number=line_number,
        parsed=audit_value,
    )
    if isinstance(audit_result, Failure):
        return audit_result.failure()
    return None


def _optional_fields_error(
    *, path: Path, line_number: int, parsed: dict[str, Any]
) -> SchemaViolationError | None:
    for key in ("rank", "spec_commitment_hint", "supersedes", "acceptance_criteria", "notes"):
        string_error = _check_optional_string_key(
            path=path,
            line_number=line_number,
            parsed=parsed,
            key=key,
        )
        if string_error is not None:
            return string_error
    return None


def _factory_safety_error(
    *, path: Path, line_number: int, parsed: dict[str, Any]
) -> SchemaViolationError | None:
    factory_safety_value = parsed.get("factory_safety")
    if factory_safety_value is None:
        return None
    return _check_in_enum(
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
) -> SchemaViolationError | None:
    """Return a SchemaViolationError when required/extraneous keys fail validation."""
    parsed_keys = frozenset(parsed.keys())
    allowed = required | optional
    missing = required - parsed_keys
    extra = parsed_keys - allowed
    if missing:
        return SchemaViolationError(
            path=path,
            line_number=line_number,
            detail=f"missing required keys: {sorted(missing)}",
        )
    if extra:
        return SchemaViolationError(
            path=path,
            line_number=line_number,
            detail=f"unexpected extra keys: {sorted(extra)}",
        )
    return None


def _check_optional_string_key(
    *,
    path: Path,
    line_number: int,
    parsed: dict[str, Any],
    key: str,
) -> SchemaViolationError | None:
    """Return a SchemaViolationError when an optional string key has the wrong shape."""
    if key not in parsed:
        return None
    value = parsed[key]
    if value is not None and not isinstance(value, str):
        return SchemaViolationError(
            path=path,
            line_number=line_number,
            detail=(f"field {key!r} must be string or null, got {type(value).__name__}"),
        )
    return None


def _check_in_enum(
    *,
    path: Path,
    line_number: int,
    field_name: str,
    value: object,
    allowed: tuple[str, ...],
) -> SchemaViolationError | None:
    if value not in allowed:
        return SchemaViolationError(
            path=path,
            line_number=line_number,
            detail=(f"field {field_name!r} value {value!r} not in allowed set {list(allowed)}"),
        )
    return None


def parse_work_item(
    *, path: Path, line_number: int, parsed: dict[str, Any]
) -> Result[WorkItem, SchemaViolationError]:
    from livespec_orchestrator_git_jsonl.store_codec import parse_work_item as parse

    return parse(path=path, line_number=line_number, parsed=parsed)


def work_item_to_dict(*, item: WorkItem) -> dict[str, Any]:
    from livespec_orchestrator_git_jsonl.store_codec import work_item_to_dict as serialize

    return serialize(item=item)

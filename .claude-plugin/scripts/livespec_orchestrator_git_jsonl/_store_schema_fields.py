"""Generic record-field shape checks, independent of any one record's schema.

These three graders answer questions about a PARSED JSON object and a key or an
enum: are the required keys present and no others, is this optional key a string
or null, is this value one of an allowed set. None of them knows what a
work-item is — no work-item key set, no work-item type, no field order — which
is exactly why they live apart from the module that composes them.

`store_schema` owns the OTHER concern: which keys a work-item record requires,
which it tolerates, and the order the per-field graders run in. Keeping the two
in one file had the composition and its primitives accreting together past the
file-LLOC ceiling, and the primitives are the half with no work-item knowledge
to lose by moving.

The names are PUBLIC because they cross a module boundary: pyright strict's
`reportPrivateUsage` and the `private_calls` check both refuse a `_`-prefixed
name imported from another module, so a shared helper is either a real
interface or it is duplicated. The MODULE is `_`-prefixed instead — it is a
private-helper module of this package, exercised through the public
`validate_work_item_payload` that imports it, and so carries no paired test
file of its own.
"""

from pathlib import Path
from typing import Any

from livespec_orchestrator_git_jsonl.errors import SchemaViolationError

__all__: list[str] = [
    "enum_membership_error",
    "optional_string_key_error",
    "required_keys_error",
]


def required_keys_error(
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


def optional_string_key_error(
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


def enum_membership_error(
    *,
    path: Path,
    line_number: int,
    field_name: str,
    value: object,
    allowed: tuple[str, ...],
) -> SchemaViolationError | None:
    """Return a SchemaViolationError when a value is outside its allowed set."""
    if value not in allowed:
        return SchemaViolationError(
            path=path,
            line_number=line_number,
            detail=(f"field {field_name!r} value {value!r} not in allowed set {list(allowed)}"),
        )
    return None

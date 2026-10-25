"""Work-item JSONL schema validation and dict conversion."""

from pathlib import Path
from typing import Any, get_args

from returns.result import Failure, Result, Success

from livespec_orchestrator_git_jsonl._store_schema_fields import (
    enum_membership_error,
    optional_string_key_error,
    required_keys_error,
)
from livespec_orchestrator_git_jsonl.errors import SchemaViolationError
from livespec_orchestrator_git_jsonl.spec_change_tier import parse_spec_change_tier
from livespec_orchestrator_git_jsonl.store_audit_schema import validate_audit_payload
from livespec_orchestrator_git_jsonl.types import (
    FactorySafety,
    Origin,
    Resolution,
    ReviewRequirement,
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
        # `factory_safety` / `review_requirement` are shared work-item policy
        # classifications this JSONL store PRESERVES (round-trips) but does not
        # act on — the git-jsonl plugin runs no Dispatcher, so it neither admits
        # nor review-gates. They are kept, not dropped, mirroring the
        # `work_item_to_dict` keep-not-drop treatment; enforcement is separate.
        "factory_safety",
        "review_requirement",
        # `spec_change_tier` (the v022 spec-stated-judgement-consumer revision)
        # is required-on-WRITE and optional-on-READ: every record this store
        # serializes carries the key explicitly, and a legacy line authored
        # before it reads back as `None`. The tolerance is also what hides a
        # write path that forgot the key, which is why the paired tests assert
        # the key's PRESENCE on a record carrying no tier.
        "spec_change_tier",
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
    review_requirement = _review_requirement_error(
        path=path, line_number=line_number, parsed=parsed
    )
    if review_requirement is not None:
        return review_requirement
    spec_change_tier = _spec_change_tier_error(path=path, line_number=line_number, parsed=parsed)
    if spec_change_tier is not None:
        return spec_change_tier
    return _factory_safety_error(path=path, line_number=line_number, parsed=parsed)


def _spec_change_tier_error(
    *, path: Path, line_number: int, parsed: dict[str, Any]
) -> SchemaViolationError | None:
    """Grade `spec_change_tier` through the SAME parser the read path uses.

    The parser is the authority and this is a thin adapter onto it, deliberately:
    a second account of the tier's shape here would let the write path admit a
    record the read path then refuses, which strands the filing on disk as a
    line nobody can materialize. Validating through `parse_spec_change_tier`
    also means the write path refuses a `tier: spec-change` that no
    `partial`/`unstated` verdict earned, so "written without a spec-change
    tier" is a property of the store rather than a convention of its callers.
    """
    tier_result = parse_spec_change_tier(path=path, line_number=line_number, parsed=parsed)
    if isinstance(tier_result, Failure):
        return tier_result.failure()
    return None


def _required_or_enum_error(
    *, path: Path, line_number: int, parsed: dict[str, Any]
) -> SchemaViolationError | None:
    required_error = required_keys_error(
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
        enum_error = enum_membership_error(
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
        string_error = optional_string_key_error(
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
    return enum_membership_error(
        path=path,
        line_number=line_number,
        field_name="factory_safety",
        value=factory_safety_value,
        allowed=get_args(FactorySafety),
    )


def _review_requirement_error(
    *, path: Path, line_number: int, parsed: dict[str, Any]
) -> SchemaViolationError | None:
    review_requirement_value = parsed.get("review_requirement")
    if review_requirement_value is None:
        return None
    return enum_membership_error(
        path=path,
        line_number=line_number,
        field_name="review_requirement",
        value=review_requirement_value,
        allowed=get_args(ReviewRequirement),
    )


def parse_work_item(
    *, path: Path, line_number: int, parsed: dict[str, Any]
) -> Result[WorkItem, SchemaViolationError]:
    from livespec_orchestrator_git_jsonl.store_codec import parse_work_item as parse

    return parse(path=path, line_number=line_number, parsed=parsed)


def work_item_to_dict(*, item: WorkItem) -> dict[str, Any]:
    from livespec_orchestrator_git_jsonl.store_codec import work_item_to_dict as serialize

    return serialize(item=item)

"""Audit sub-object schema validation."""

from pathlib import Path
from typing import Any

from returns.result import Failure, Result, Success

from livespec_orchestrator_git_jsonl.errors import SchemaViolationError

__all__: list[str] = ["validate_audit_payload"]


def validate_audit_payload(
    *,
    path: Path,
    line_number: int,
    parsed: dict[str, Any],
) -> Result[None, SchemaViolationError]:
    """Verify an audit sub-object's required keys and merge-evidence fields."""
    required = frozenset({"verification_timestamp", "commits", "files_changed", "merge_sha"})
    missing = required - parsed.keys()
    if missing:
        return Failure(
            SchemaViolationError(
                path=path,
                line_number=line_number,
                detail=f"audit object missing keys: {sorted(missing)}",
            )
        )
    merge_sha_value = parsed["merge_sha"]
    if not isinstance(merge_sha_value, str) or merge_sha_value == "":
        return Failure(
            SchemaViolationError(
                path=path,
                line_number=line_number,
                detail="audit field 'merge_sha' must be a non-empty string",
            )
        )
    if "pr_number" in parsed:
        pr_number_value = parsed["pr_number"]
        is_valid_pr_number = pr_number_value is None or (
            isinstance(pr_number_value, int) and not isinstance(pr_number_value, bool)
        )
        if not is_valid_pr_number:
            return Failure(
                SchemaViolationError(
                    path=path,
                    line_number=line_number,
                    detail=(
                        f"audit field 'pr_number' must be an integer or null, "
                        f"got {type(pr_number_value).__name__}"
                    ),
                )
            )
    return Success(None)

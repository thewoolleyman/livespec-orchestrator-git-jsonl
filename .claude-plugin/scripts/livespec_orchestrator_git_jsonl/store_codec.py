"""Work-item JSONL dict/dataclass conversion helpers."""

from dataclasses import asdict
from pathlib import Path
from typing import Any

from livespec_runtime.work_items.rank import BOTTOM_SENTINEL
from returns.result import Failure, Result, Success

from livespec_orchestrator_git_jsonl.errors import SchemaViolationError
from livespec_orchestrator_git_jsonl.types import AuditRecord, WorkItem

__all__: list[str] = ["parse_work_item", "work_item_to_dict"]


def parse_work_item(
    *, path: Path, line_number: int, parsed: dict[str, Any]
) -> Result[WorkItem, SchemaViolationError]:
    from livespec_orchestrator_git_jsonl.store_schema import validate_work_item_payload

    validation = validate_work_item_payload(path=path, line_number=line_number, parsed=parsed)
    if isinstance(validation, Failure):
        return Failure(validation.failure())
    audit_value = parsed["audit"]
    audit_record: AuditRecord | None = None
    if audit_value is not None:
        audit_record = _parse_audit(parsed=audit_value)
    return Success(
        WorkItem(
            id=parsed["id"],
            type=parsed["type"],
            status=parsed["status"],
            title=parsed["title"],
            description=parsed["description"],
            origin=parsed["origin"],
            gap_id=parsed["gap_id"],
            # Absent OR null/empty `rank` (a legacy pre-v013 line) reads back as
            # the shared bottom-sentinel; a present non-empty string is taken
            # verbatim (its str-ness is enforced by `_validate_work_item_payload`).
            rank=parsed.get("rank") or BOTTOM_SENTINEL,
            assignee=parsed["assignee"],
            depends_on=tuple(parsed["depends_on"]),
            captured_at=parsed["captured_at"],
            resolution=parsed["resolution"],
            reason=parsed["reason"],
            audit=audit_record,
            superseded_by=parsed["superseded_by"],
            spec_commitment_hint=parsed.get("spec_commitment_hint"),
            supersedes=parsed.get("supersedes"),
            acceptance_criteria=parsed.get("acceptance_criteria"),
            notes=parsed.get("notes"),
            factory_safety=parsed.get("factory_safety"),
        )
    )


def _parse_audit(*, parsed: dict[str, Any]) -> AuditRecord:
    return AuditRecord(
        verification_timestamp=parsed["verification_timestamp"],
        commits=tuple(parsed["commits"]),
        files_changed=tuple(parsed["files_changed"]),
        merge_sha=parsed["merge_sha"],
        pr_number=parsed.get("pr_number"),
    )


def work_item_to_dict(*, item: WorkItem) -> dict[str, Any]:
    payload = asdict(item)
    payload["depends_on"] = list(item.depends_on)
    # The abstract WorkItem carries three policy fields this JSONL realization
    # does NOT persist — admission_policy / acceptance_policy /
    # blocked_reason govern the orchestrator Dispatcher/admission this plugin
    # does not run. factory_safety is different: a git-jsonl-backed
    # dispatcher must preserve that classification to enforce factory mode.
    # Drop only the non-persisted policy fields so serialized records match
    # the closed-key schema and round-trip through the read-path validator.
    for policy_key in ("admission_policy", "acceptance_policy", "blocked_reason"):
        _ = payload.pop(policy_key, None)
    if item.audit is not None:
        payload["audit"] = {
            "verification_timestamp": item.audit.verification_timestamp,
            "commits": list(item.audit.commits),
            "files_changed": list(item.audit.files_changed),
            "merge_sha": item.audit.merge_sha,
            "pr_number": item.audit.pr_number,
        }
    return payload

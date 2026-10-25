"""Work-item JSONL dict/dataclass conversion helpers."""

from dataclasses import asdict
from pathlib import Path
from typing import Any

from livespec_runtime.spec_stated import SpecChangeTier
from livespec_runtime.work_items.rank import BOTTOM_SENTINEL
from returns.result import Failure, Result, Success

from livespec_orchestrator_git_jsonl.errors import SchemaViolationError
from livespec_orchestrator_git_jsonl.spec_change_tier import (
    SPEC_CHANGE_TIER_KEY,
    spec_change_tier_to_dict,
)
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
            review_requirement=parsed.get("review_requirement"),
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


def work_item_to_dict(
    *, item: WorkItem, spec_change_tier: SpecChangeTier | None = None
) -> dict[str, Any]:
    """One work-item as the record carries it, with its spec-change tier beside it.

    `spec_change_tier` is a SEPARATE argument because the shared `WorkItem`
    carries no such field — the tier is persisted per orchestrator realization
    (see `spec_change_tier`). It defaults to `None`, which is the honest answer
    for every caller that ran no classification: a gap-tied filing, a migration,
    an amending record authored by a reader that never judged anything. The key
    is still written EXPLICITLY, because the read path treats an absent key as
    `null` and a forgotten key is therefore indistinguishable from a record
    authored before the field existed.
    """
    payload = asdict(item)
    payload["depends_on"] = list(item.depends_on)
    payload[SPEC_CHANGE_TIER_KEY] = spec_change_tier_to_dict(tier=spec_change_tier)
    # The abstract WorkItem carries fields this JSONL realization does NOT
    # persist. Dropping them is not housekeeping: the record schema in
    # SPECIFICATION/contracts.md closes the key set ("additional keys ... are
    # forbidden"), so a field left in the payload makes the write path emit a
    # record its OWN read-path validator rejects — which is how a new upstream
    # field silently empties the store rather than failing loudly at the field.
    #
    # admission_policy / acceptance_policy / blocked_reason govern the
    # orchestrator Dispatcher/admission this plugin does not run.
    # awaits_scope_override is a materialized current-state signal the vendored
    # runtime backs with an `awaits-scope-override` BEADS label; this substrate
    # has no labels and the ratified schema enumerates no key for it, so it is
    # not persisted either and reads back as its `False` default — the same
    # default-on-read treatment the schema states for the policy trio.
    #
    # factory_safety and review_requirement are different: they are shared
    # policy CLASSIFICATIONS a git-jsonl-backed dispatcher must preserve
    # (factory-safety mode; review-before-merge) even though this plugin does
    # not act on them, so they are kept and round-tripped.
    for unpersisted_key in (
        "admission_policy",
        "acceptance_policy",
        "blocked_reason",
        "awaits_scope_override",
    ):
        _ = payload.pop(unpersisted_key, None)
    if item.audit is not None:
        payload["audit"] = {
            "verification_timestamp": item.audit.verification_timestamp,
            "commits": list(item.audit.commits),
            "files_changed": list(item.audit.files_changed),
            "merge_sha": item.audit.merge_sha,
            "pr_number": item.audit.pr_number,
        }
    return payload

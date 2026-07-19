"""Core merge-evidence backfill implementation."""

import json
import tempfile
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

from returns.io import IOSuccess
from returns.result import Failure
from returns.unsafe import unsafe_perform_io

from livespec_orchestrator_git_jsonl.checks.work_item_merge_evidence import (
    GRANDFATHER_MERGE_SHA_SENTINEL,
)
from livespec_orchestrator_git_jsonl.errors import MalformedRecordLineError
from livespec_orchestrator_git_jsonl.io.store import parse_jsonl_line
from livespec_orchestrator_git_jsonl.migration.merge_evidence_git import discover_merge_sha
from livespec_orchestrator_git_jsonl.store import (
    append_work_item,
    materialize_work_items,
    read_work_items,
    work_item_record_identity,
)
from livespec_orchestrator_git_jsonl.types import AuditRecord, WorkItem

__all__: list[str] = ["BackfillReport", "backfill_file"]

_REQUIRE_EVIDENCE_RESOLUTIONS = frozenset({"completed", "spec-revised", "resolved-out-of-band"})


@dataclass(frozen=True, kw_only=True)
class BackfillReport:
    """Per-run summary of repairs, appends, and orphan findings."""

    repaired: tuple[str, ...]
    appended: tuple[str, ...]
    orphans: tuple[str, ...]


def backfill_file(
    *,
    path: Path,
    repo_dir: Path,
    canonical_branch: str,
    grandfather: bool,
    dry_run: bool,
) -> BackfillReport:
    """Backfill merge-evidence in the work-items store at `path`.

    Writes happen only when `dry_run` is False AND no orphan findings
    were raised (all-or-nothing). Raises the store's EXPECTED errors
    (`MalformedRecordLineError`, `SchemaViolationError`) when the
    input — even after phase-1 repair — cannot be read canonically.
    """
    lines = _load_lines(path=path)
    out_lines, repaired, phase_one_orphans = _phase_one_repairs(
        lines=lines,
        path=path,
        repo_dir=repo_dir,
        canonical_branch=canonical_branch,
        grandfather=grandfather,
    )
    if phase_one_orphans:
        # The orphaned lines still lack merge_sha, so the store stays
        # unreadable by the canonical surface — phase 2 cannot run.
        # Writes are blocked anyway (all-or-nothing), so report the
        # findings and stop.
        return BackfillReport(repaired=repaired, appended=(), orphans=phase_one_orphans)
    content = "".join(line + "\n" for line in out_lines)
    transitions, appended, phase_two_orphans = _phase_two_transitions(
        content=content,
        repo_dir=repo_dir,
        canonical_branch=canonical_branch,
        grandfather=grandfather,
    )
    if not dry_run and not phase_two_orphans:
        _ = path.write_text(content, encoding="utf-8")
        for transition in transitions:
            _ = append_work_item(path=path, item=transition)
    return BackfillReport(repaired=repaired, appended=appended, orphans=phase_two_orphans)


def _load_lines(*, path: Path) -> list[str]:
    """Read raw record lines; raise MalformedRecordLineError on blank lines.

    The raw read is the sanctioned phase-1 exception: lines carrying a
    legacy audit object without `merge_sha` fail the canonical read
    path's schema validation, so the repair MUST happen below it.
    """
    raw = path.read_text(encoding="utf-8")
    lines = raw.splitlines()
    for line_number, line in enumerate(lines, start=1):
        if line.strip() == "":
            raise MalformedRecordLineError(
                path=path,
                line_number=line_number,
                raw_line=line,
                detail="empty line not permitted between records",
            )
    return lines


def _phase_one_repairs(
    *,
    lines: list[str],
    path: Path,
    repo_dir: Path,
    canonical_branch: str,
    grandfather: bool,
) -> tuple[list[str], tuple[str, ...], tuple[str, ...]]:
    """Repair audit objects lacking `merge_sha`; return (lines, repaired, orphans)."""
    out_lines: list[str] = []
    repaired: list[str] = []
    orphans: list[str] = []
    for line_number, line in enumerate(lines, start=1):
        parsed_record = parse_jsonl_line(path=path, line_number=line_number, raw_line=line)
        if isinstance(parsed_record, Failure):
            raise parsed_record.failure()
        record = parsed_record.unwrap()
        audit_value = record.get("audit")
        if not isinstance(audit_value, dict):
            out_lines.append(line)
            continue
        audit = cast("dict[str, Any]", audit_value)
        if audit.get("merge_sha") not in (None, ""):
            out_lines.append(line)
            continue
        work_item_id = str(record.get("id"))
        merge_sha = (
            GRANDFATHER_MERGE_SHA_SENTINEL
            if grandfather
            else discover_merge_sha(
                repo_dir=repo_dir,
                canonical_branch=canonical_branch,
                work_item_id=work_item_id,
                commits=cast("list[Any]", audit.get("commits") or []),
            )
        )
        if merge_sha is None:
            orphans.append(_orphan_finding(work_item_id=work_item_id, branch=canonical_branch))
            out_lines.append(line)
            continue
        audit["merge_sha"] = merge_sha
        out_lines.append(json.dumps(record, separators=(",", ":"), sort_keys=True))
        repaired.append(f"{work_item_id}: populated audit.merge_sha {merge_sha} in place")
    return out_lines, tuple(repaired), tuple(orphans)


def _phase_two_transitions(
    *,
    content: str,
    repo_dir: Path,
    canonical_branch: str,
    grandfather: bool,
) -> tuple[tuple[WorkItem, ...], tuple[str, ...], tuple[str, ...]]:
    """Build superseding transition records for audit-null closed heads.

    Reads the phase-1-repaired content through the CANONICAL query
    surface (via a scratch copy, so dry-run and orphan-blocked runs
    never touch the real store), per the one-canonical-reducer
    obligation. Schema violations surviving phase 1 propagate to the
    caller as the store's EXPECTED errors.
    """
    with tempfile.TemporaryDirectory() as scratch_dir:
        scratch_path = Path(scratch_dir) / "phase-one-preview.jsonl"
        _ = scratch_path.write_text(content, encoding="utf-8")
        records_result = read_work_items(path=scratch_path)
        if not isinstance(records_result, IOSuccess):
            raise unsafe_perform_io(records_result.failure())
        records = unsafe_perform_io(records_result.unwrap())
        index = materialize_work_items(records=iter(records))
    now = datetime.now(tz=timezone.utc).isoformat(timespec="seconds")
    transitions: list[WorkItem] = []
    appended: list[str] = []
    orphans: list[str] = []
    for item_id in sorted(index):
        head = index[item_id]
        if head.status != "done" or head.type == "epic" or head.audit is not None:
            continue
        if head.resolution not in _REQUIRE_EVIDENCE_RESOLUTIONS:
            continue
        merge_sha = (
            GRANDFATHER_MERGE_SHA_SENTINEL
            if grandfather
            else discover_merge_sha(
                repo_dir=repo_dir,
                canonical_branch=canonical_branch,
                work_item_id=item_id,
                commits=[],
            )
        )
        if merge_sha is None:
            orphans.append(_orphan_finding(work_item_id=item_id, branch=canonical_branch))
            continue
        audit = AuditRecord(
            verification_timestamp=now,
            commits=(),
            files_changed=(),
            merge_sha=merge_sha,
            pr_number=None,
        )
        transitions.append(
            replace(
                head,
                captured_at=now,
                audit=audit,
                supersedes=work_item_record_identity(item=head),
            )
        )
        appended.append(
            f"{item_id}: appended merge-evidence transition record (merge_sha {merge_sha})"
        )
    return tuple(transitions), tuple(appended), tuple(orphans)


def _orphan_finding(*, work_item_id: str, branch: str) -> str:
    return (
        f"{work_item_id}: no merge evidence found on origin/{branch} — "
        "dispose manually (re-open or close as wontfix) or re-run with --grandfather"
    )

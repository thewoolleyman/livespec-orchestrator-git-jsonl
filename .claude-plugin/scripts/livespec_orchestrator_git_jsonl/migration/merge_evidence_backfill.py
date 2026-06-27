"""One-shot merge-evidence backfill for existing closed work-items.

Per SPECIFICATION/contracts.md: work-items closed before the
`merge_sha` schema addition
cannot be validated against the `work_item_merge_evidence` static
check (and legacy audit objects lacking `merge_sha` cannot even be
READ by the canonical query surface) until backfilled. Two strategies:

- **Strategy (a) — disciplined default.** Scan local git for the SHAs
  in each closed work-item's `audit.commits` (falling back to a
  `git log --grep=<id>` walk over `origin/<canonical_branch>` when
  none are recorded). For each candidate, resolve the merge commit
  that introduced it via
  `git rev-list --merges --ancestry-path <sha>..origin/<branch>`
  (the commit itself stands in when the work landed without a merge
  commit — the rebase-merge / fast-forward case) and populate
  `merge_sha`. Candidates not reachable from the canonical branch are
  orphans: surfaced as findings — they are exactly what the
  merge-evidence epic exists to find — and they BLOCK all writes
  (all-or-nothing), so the user disposes them (re-open, close as
  wontfix) or re-runs with `--grandfather`.
- **Strategy (b) — `--grandfather` fallback.** Populate the
  `<pre-schema-bootstrap>` sentinel (exempt from the static check's
  reachability test) on every closure needing evidence. Fast, but
  leaves a known-incomplete sentinel in the data.

Two phases:

1. **In-place repair.** Record lines whose audit object lacks (or
   carries an empty) `merge_sha` are unreadable by the canonical
   surface, so this phase reads raw lines and rewrites ONLY the
   offending lines (the sanctioned exception to the append-only write
   rule; see this directory's CLAUDE.md). Untouched lines keep their
   original bytes so record identities are preserved.
2. **Transition appends.** With every line readable, the canonical
   surface (`read_work_items` / `materialize_work_items` /
   `work_item_record_identity` / `append_work_item`) drives the rest:
   each closed, non-epic head with a merge-implying resolution and a
   null audit gains ONE superseding transition record carrying the
   synthesized audit (`supersedes` = the prior head's identity, so
   the reduction stays single-headed).

CLI: `--path <work-items-file>` (required), `--canonical-branch`
(default: the check module's `resolve_canonical_branch` chain),
`--grandfather`, `--dry-run`. Exit 0 on success, 1 on orphan findings
or unreadable input. All git operations are local; no network I/O.
"""

import argparse
import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

from livespec_orchestrator_git_jsonl.checks.work_item_merge_evidence import (
    GRANDFATHER_MERGE_SHA_SENTINEL,
    resolve_canonical_branch,
)
from livespec_orchestrator_git_jsonl.errors import (
    MalformedRecordLineError,
    SchemaViolationError,
    StoreFileMissingError,
)
from livespec_orchestrator_git_jsonl.io.store import parse_jsonl_line
from livespec_orchestrator_git_jsonl.store import (
    append_work_item,
    materialize_work_items,
    read_work_items,
    work_item_record_identity,
)
from livespec_orchestrator_git_jsonl.types import AuditRecord, WorkItem

__all__: list[str] = ["BackfillReport", "backfill_file", "main"]


_REQUIRE_EVIDENCE_RESOLUTIONS = frozenset({"completed", "spec-revised", "resolved-out-of-band"})


@dataclass(frozen=True, kw_only=True)
class BackfillReport:
    """Per-run summary of repairs, appends, and orphan findings."""

    repaired: tuple[str, ...]
    appended: tuple[str, ...]
    orphans: tuple[str, ...]


def main(*, argv: list[str] | None = None) -> int:
    """CLI entry: --path <file> [--canonical-branch <name>] [--grandfather] [--dry-run]."""
    parser = argparse.ArgumentParser(
        description=(
            "Backfill audit.merge_sha on existing closed work-items per "
            "SPECIFICATION/contracts.md 'Backfill for existing closed work-items'. "
            "Strategy (a) walks local git evidence; --grandfather populates the "
            "pre-schema-bootstrap sentinel instead. Orphan findings block all writes."
        ),
    )
    _ = parser.add_argument("--path", type=Path, required=True)
    _ = parser.add_argument("--canonical-branch", dest="canonical_branch", default=None)
    _ = parser.add_argument("--grandfather", action="store_true")
    _ = parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    target_path: Path = args.path
    dry_run: bool = args.dry_run
    grandfather: bool = args.grandfather
    if not target_path.exists():
        _ = sys.stderr.write(f"ERROR: {target_path} does not exist\n")
        return 1
    repo_dir = target_path.parent
    canonical_branch: str = (
        args.canonical_branch
        if args.canonical_branch is not None
        else resolve_canonical_branch(repo_dir=repo_dir)
    )
    try:
        report = backfill_file(
            path=target_path,
            repo_dir=repo_dir,
            canonical_branch=canonical_branch,
            grandfather=grandfather,
            dry_run=dry_run,
        )
    except (StoreFileMissingError, MalformedRecordLineError, SchemaViolationError) as exc:
        _ = sys.stderr.write(f"ERROR: {target_path} not backfillable — {exc}\n")
        return 1
    for line in (*report.repaired, *report.appended, *report.orphans):
        _ = sys.stdout.write(line + "\n")
    verb = "would apply" if dry_run or report.orphans else "applied"
    repairs = f"{len(report.repaired)} in-place repair(s)"
    appends = f"{len(report.appended)} transition append(s)"
    summary = f"{verb} {repairs}, {appends}; {len(report.orphans)} orphan finding(s)"
    _ = sys.stdout.write(summary + "\n")
    if report.orphans:
        hint = "dispose orphans (re-open or close as wontfix) or re-run with --grandfather"
        _ = sys.stdout.write(f"no records were written — {hint}\n")
        return 1
    return 0


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
            append_work_item(path=path, item=transition)
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
        record = parse_jsonl_line(path=path, line_number=line_number, raw_line=line)
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
            else _discover_merge_sha(
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
        index = materialize_work_items(records=read_work_items(path=scratch_path))
    now = datetime.now(tz=timezone.utc).isoformat(timespec="seconds")
    transitions: list[WorkItem] = []
    appended: list[str] = []
    orphans: list[str] = []
    for item_id in sorted(index):
        head = index[item_id]
        if head.status != "closed" or head.type == "epic" or head.audit is not None:
            continue
        if head.resolution not in _REQUIRE_EVIDENCE_RESOLUTIONS:
            continue
        merge_sha = (
            GRANDFATHER_MERGE_SHA_SENTINEL
            if grandfather
            else _discover_merge_sha(
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


def _discover_merge_sha(
    *,
    repo_dir: Path,
    canonical_branch: str,
    work_item_id: str,
    commits: list[Any],
) -> str | None:
    """Resolve the canonical-branch SHA that introduced the work, or None.

    Candidates are the recorded `audit.commits` SHAs; when none are
    recorded, commits on `origin/<canonical_branch>` whose message
    mentions the work-item id (newest first). The first candidate that
    exists locally and is reachable from the canonical branch wins.
    """
    candidates = [str(commit) for commit in commits]
    if not candidates:
        candidates = _id_grep_candidates(
            repo_dir=repo_dir,
            canonical_branch=canonical_branch,
            work_item_id=work_item_id,
        )
    for candidate in candidates:
        introducing = _introducing_sha(
            repo_dir=repo_dir,
            canonical_branch=canonical_branch,
            sha=candidate,
        )
        if introducing is not None:
            return introducing
    return None


def _id_grep_candidates(
    *,
    repo_dir: Path,
    canonical_branch: str,
    work_item_id: str,
) -> list[str]:
    """SHAs on origin/<canonical_branch> whose message mentions the id."""
    completed = subprocess.run(
        [
            "git",
            "log",
            "--format=%H",
            f"--grep={work_item_id}",
            f"origin/{canonical_branch}",
        ],
        cwd=repo_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    # A failed invocation (e.g. repo_dir is not a git repo, or the
    # origin ref is absent) leaves stdout empty, so the split() below
    # yields no candidates without a separate returncode branch.
    return completed.stdout.split()


def _introducing_sha(*, repo_dir: Path, canonical_branch: str, sha: str) -> str | None:
    """The merge commit that introduced `sha` on the canonical branch.

    Returns the last `--ancestry-path --merges` commit per the spec's
    `| tail -1` recipe; the commit itself when no merge commit exists
    (rebase-merge / fast-forward landings); None when `sha` does not
    exist locally or is not reachable from origin/<canonical_branch>.
    """
    reachable = _git_ok(repo_dir=repo_dir, args=["cat-file", "-e", sha]) and _git_ok(
        repo_dir=repo_dir,
        args=["merge-base", "--is-ancestor", sha, f"origin/{canonical_branch}"],
    )
    if not reachable:
        return None
    completed = subprocess.run(
        [
            "git",
            "rev-list",
            "--merges",
            "--ancestry-path",
            f"{sha}..origin/{canonical_branch}",
        ],
        cwd=repo_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    merges = completed.stdout.split()
    return merges[-1] if merges else sha


def _git_ok(*, repo_dir: Path, args: list[str]) -> bool:
    """Run a local git command; True iff it exits 0 (network-free)."""
    completed = subprocess.run(
        ["git", *args],
        cwd=repo_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.returncode == 0


if __name__ == "__main__":
    raise SystemExit(main())

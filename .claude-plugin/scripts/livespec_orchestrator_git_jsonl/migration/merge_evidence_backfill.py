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
import sys
from pathlib import Path

from livespec_orchestrator_git_jsonl.checks.work_item_merge_evidence import (
    resolve_canonical_branch,
)
from livespec_orchestrator_git_jsonl.errors import (
    MalformedRecordLineError,
    SchemaViolationError,
    StoreFileMissingError,
)
from livespec_orchestrator_git_jsonl.migration.merge_evidence_backfill_core import (
    BackfillReport,
    backfill_file,
)

__all__: list[str] = ["BackfillReport", "backfill_file", "main"]


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
    except OSError as exc:
        _ = sys.stderr.write(f"ERROR: failed to append merge-evidence transition: {exc}\n")
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

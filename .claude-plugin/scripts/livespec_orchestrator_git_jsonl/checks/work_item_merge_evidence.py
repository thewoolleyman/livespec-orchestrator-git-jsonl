"""`check-work-item-merge-evidence` merge-evidence static check.

Per SPECIFICATION/contracts.md, this check walks the
materialized work-items view (via the canonical query surface) and
applies the merge-evidence rules to every closed work-item:

- A merge-implying resolution (`completed`, `spec-revised`,
  `resolved-out-of-band`) REQUIRES a non-null audit whose `merge_sha`
  exists in the local repo (`git cat-file -e`) and is reachable from
  `origin/<canonical_branch>` (`git merge-base --is-ancestor`). The
  store's read path already rejects an audit object whose `merge_sha`
  is empty, so the spec's non-empty requirement is enforced upstream
  of this check.
- An administrative resolution (`wontfix`, `duplicate`,
  `no-longer-applicable`) must NOT carry merge-evidence: `audit` must
  be null (the spec's empty-string negative-evidence arm is
  unrepresentable in a readable store for the same upstream reason).
- A closed work-item without a resolution is malformed.
- Work-items with `type == "epic"` are EXEMPT from the merge-evidence
  requirement; INSTEAD every local `depends_on` child must resolve to
  a closed work-item.
- The grandfather sentinel (`<pre-schema-bootstrap>`, per the
  SPECIFICATION/contracts.md backfill strategy (b)) is exempt from the
  reachability test.

All git operations are local (`cat-file`, `merge-base`,
`symbolic-ref`); the check performs no network I/O. They run in the
work-items file's parent directory (the consumer project root). The
canonical branch resolves `--canonical-branch` flag →
`.livespec.jsonc` plugin-block `canonical_branch` key → `origin/HEAD`
symbolic-ref → `master`, per SPECIFICATION/contracts.md.

The check is plugin-private (it depends on the JSONL schema this
plugin defines) and is wired into this repo's `just check` aggregate
as `check-work-item-merge-evidence`, invoked through the
`.claude-plugin/scripts/bin/check_work_item_merge_evidence.py`
wrapper. An absent store file is a pass (nothing to attest; noted in
output); a malformed or schema-violating store is a failure —
reported as a finding, never an uncaught traceback.
"""

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Any, Final, cast

from livespec_orchestrator_git_jsonl.commands._config import resolve_store_config
from livespec_orchestrator_git_jsonl.errors import (
    MalformedRecordLineError,
    SchemaViolationError,
    StoreFileMissingError,
)
from livespec_orchestrator_git_jsonl.io._jsonc import loads_optional
from livespec_orchestrator_git_jsonl.store import materialize_work_items, read_work_items
from livespec_orchestrator_git_jsonl.types import DependsOnRaw, WorkItem

__all__: list[str] = ["GRANDFATHER_MERGE_SHA_SENTINEL", "main", "resolve_canonical_branch"]


_CHECK_NAME = "check-work-item-merge-evidence"

# Strategy (b) of SPECIFICATION/contracts.md: the merge-evidence
# backfill migration populates
# this sentinel on grandfathered closures; the check exempts it from
# the reachability test. The merge_evidence_backfill migration module
# imports this constant so the two stay a single definition.
GRANDFATHER_MERGE_SHA_SENTINEL: Final[str] = "<pre-schema-bootstrap>"

_REQUIRE_EVIDENCE_RESOLUTIONS = frozenset({"completed", "spec-revised", "resolved-out-of-band"})

_DEFAULT_CANONICAL_BRANCH = "master"
_CONFIG_FILENAME = ".livespec.jsonc"
_PLUGIN_BLOCK = "livespec-orchestrator-git-jsonl"
_CANONICAL_BRANCH_KEY = "canonical_branch"


def main(*, argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog=_CHECK_NAME)
    _ = parser.add_argument("--work-items-path", dest="work_items_path", default=None)
    _ = parser.add_argument("--canonical-branch", dest="canonical_branch", default=None)
    args = parser.parse_args(argv)
    config = resolve_store_config(
        cwd=Path.cwd(),
        work_items_arg=args.work_items_path,
    )
    repo_dir = config.work_items_path.parent
    canonical_branch: str = (
        args.canonical_branch
        if args.canonical_branch is not None
        else resolve_canonical_branch(repo_dir=repo_dir)
    )

    notes: list[str] = []
    failures: list[str] = []
    index: dict[str, WorkItem] = {}
    try:
        index = materialize_work_items(records=read_work_items(path=config.work_items_path))
    except StoreFileMissingError:
        notes = [f"{_CHECK_NAME}: work-items store '{config.work_items_path}' absent — skipped"]
    except (MalformedRecordLineError, SchemaViolationError) as exc:
        failures = [
            f"{_CHECK_NAME}: work-items store '{config.work_items_path}' unreadable — {exc}"
        ]
    else:
        for item_id in sorted(index):
            item = index[item_id]
            if item.status != "closed":
                continue
            message = _item_violation(
                repo_dir=repo_dir,
                item=item,
                index=index,
                canonical_branch=canonical_branch,
            )
            if message is not None:
                prefix = f"{_CHECK_NAME}: work-items store '{config.work_items_path}'"
                failures.append(f"{prefix}: work-item '{item_id}': {message}")

    for line in (*notes, *failures):
        _ = sys.stdout.write(line + "\n")
    if failures:
        _ = sys.stdout.write(f"{_CHECK_NAME}: FAIL — {len(failures)} finding(s)\n")
        return 1
    _ = sys.stdout.write(
        f"{_CHECK_NAME}: OK — every closed work-item carries conformant merge-evidence\n"
    )
    return 0


def resolve_canonical_branch(*, repo_dir: Path) -> str:
    """Resolve the canonical branch per the `compat`-block contract.

    Precedence: `.livespec.jsonc` plugin-block `canonical_branch` key →
    `git symbolic-ref --short refs/remotes/origin/HEAD` (with the
    `origin/` prefix stripped) → the hard-coded `master` fallback.
    """
    configured = _configured_branch(repo_dir=repo_dir)
    if configured is not None:
        return configured
    completed = subprocess.run(
        ["git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode == 0:
        return completed.stdout.strip().removeprefix("origin/")
    return _DEFAULT_CANONICAL_BRANCH


def _configured_branch(*, repo_dir: Path) -> str | None:
    """Read the plugin block's `canonical_branch` key, or None when unusable."""
    config_path = repo_dir / _CONFIG_FILENAME
    if not config_path.is_file():
        return None
    parsed = loads_optional(text=config_path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        return None
    block = cast("dict[str, Any]", parsed).get(_PLUGIN_BLOCK)
    if not isinstance(block, dict):
        return None
    value = cast("dict[str, Any]", block).get(_CANONICAL_BRANCH_KEY)
    if isinstance(value, str) and value != "":
        return value
    return None


def _item_violation(
    *,
    repo_dir: Path,
    item: WorkItem,
    index: dict[str, WorkItem],
    canonical_branch: str,
) -> str | None:
    """Apply the merge-evidence rules to one closed work-item."""
    if item.type == "epic":
        return _epic_violation(item=item, index=index)
    if item.resolution is None:
        return "closed work-item without resolution is malformed"
    if item.resolution in _REQUIRE_EVIDENCE_RESOLUTIONS:
        return _evidence_violation(repo_dir=repo_dir, item=item, canonical_branch=canonical_branch)
    return _administrative_violation(item=item)


def _evidence_violation(
    *,
    repo_dir: Path,
    item: WorkItem,
    canonical_branch: str,
) -> str | None:
    """Return a violation message for a merge-implying closure, or None."""
    if item.audit is None:
        return (
            "closed work-item with a merge-implying resolution is "
            "missing the required audit merge-evidence"
        )
    if item.audit.merge_sha == GRANDFATHER_MERGE_SHA_SENTINEL:
        return None
    if not _sha_reachable(
        repo_dir=repo_dir,
        merge_sha=item.audit.merge_sha,
        canonical_branch=canonical_branch,
    ):
        return (
            f"audit.merge_sha '{item.audit.merge_sha}' is not reachable "
            f"from origin/{canonical_branch}"
        )
    return None


def _administrative_violation(*, item: WorkItem) -> str | None:
    """An administratively closed record MUST NOT carry merge-evidence."""
    if item.audit is not None:
        return "administratively closed work-item must not carry audit merge-evidence"
    return None


def _epic_violation(*, item: WorkItem, index: dict[str, WorkItem]) -> str | None:
    """Every local child of a closed epic must resolve to a closed work-item."""
    for entry in item.depends_on:
        child_id = _local_child_id(entry=entry)
        if child_id is None:
            continue
        child = index.get(child_id)
        if child is not None and child.status != "closed":
            return f"closed epic has non-closed child '{child_id}'"
    return None


def _local_child_id(*, entry: DependsOnRaw) -> str | None:
    """Extract the local child id from a `depends_on` entry, or None.

    Accepts both the legacy bare-string form and the v072 typed-dict
    local form `{"kind": "local", "work_item_id": <id>}`. Non-local
    kinds have no in-store child to resolve and yield None.
    """
    if isinstance(entry, str):
        return entry
    if entry.get("kind") != "local":
        return None
    child = entry.get("work_item_id")
    return child if isinstance(child, str) else None


def _sha_reachable(*, repo_dir: Path, merge_sha: str, canonical_branch: str) -> bool:
    """The SHA exists locally AND is an ancestor of origin/<canonical_branch>."""
    if not _git_ok(repo_dir=repo_dir, args=["cat-file", "-e", merge_sha]):
        return False
    return _git_ok(
        repo_dir=repo_dir,
        args=["merge-base", "--is-ancestor", merge_sha, f"origin/{canonical_branch}"],
    )


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

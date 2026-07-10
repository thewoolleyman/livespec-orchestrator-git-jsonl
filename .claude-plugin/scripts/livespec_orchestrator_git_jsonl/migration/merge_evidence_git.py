"""Local-git merge evidence discovery for the backfill migration."""

import subprocess
from pathlib import Path
from typing import Any

__all__: list[str] = ["discover_merge_sha"]


def discover_merge_sha(
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

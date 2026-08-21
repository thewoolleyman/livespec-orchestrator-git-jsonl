"""Local-git merge evidence discovery for the backfill migration."""

import subprocess
from pathlib import Path
from typing import Any

from returns.result import Failure, Result, Success

from livespec_orchestrator_git_jsonl.errors import GitEvidenceLookupError

__all__: list[str] = ["discover_merge_sha"]


def discover_merge_sha(
    *,
    repo_dir: Path,
    canonical_branch: str,
    work_item_id: str,
    commits: list[Any],
) -> Result[str | None, GitEvidenceLookupError]:
    """Resolve the canonical-branch SHA that introduced the work.

    Candidates are the recorded `audit.commits` SHAs; when none are
    recorded, commits on `origin/<canonical_branch>` whose message
    mentions the work-item id (newest first). The first candidate that
    exists locally and is reachable from the canonical branch wins. A
    successful lookup with no reachable evidence returns Success(None);
    a failed git invocation returns Failure(...).
    """
    candidates = [str(commit) for commit in commits]
    if not candidates:
        grep_result = _id_grep_candidates(
            repo_dir=repo_dir,
            canonical_branch=canonical_branch,
            work_item_id=work_item_id,
        )
        if isinstance(grep_result, Failure):
            return grep_result
        candidates = grep_result.unwrap()
    for candidate in candidates:
        introducing_result = _introducing_sha(
            repo_dir=repo_dir,
            canonical_branch=canonical_branch,
            sha=candidate,
        )
        if isinstance(introducing_result, Failure):
            return introducing_result
        introducing = introducing_result.unwrap()
        if introducing is not None:
            return Success(introducing)
    return Success(None)


def _id_grep_candidates(
    *,
    repo_dir: Path,
    canonical_branch: str,
    work_item_id: str,
) -> Result[list[str], GitEvidenceLookupError]:
    """SHAs on origin/<canonical_branch> whose message mentions the id."""
    result = _run_git(
        repo_dir=repo_dir,
        args=[
            "git",
            "log",
            "--format=%H",
            f"--grep={work_item_id}",
            f"origin/{canonical_branch}",
        ],
    )
    if isinstance(result, Failure):
        return result
    completed = result.unwrap()
    return Success(completed.stdout.split())


def _introducing_sha(
    *, repo_dir: Path, canonical_branch: str, sha: str
) -> Result[str | None, GitEvidenceLookupError]:
    """The merge commit that introduced `sha` on the canonical branch.

    Returns the last `--ancestry-path --merges` commit per the spec's
    `| tail -1` recipe; the commit itself when no merge commit exists
    (rebase-merge / fast-forward landings); Success(None) when `sha`
    does not exist locally or is not reachable from origin/<canonical_branch>.
    """
    exists = _git_bool(
        repo_dir=repo_dir,
        args=["git", "cat-file", "-e", sha],
        absent_object_is_false=True,
    )
    if isinstance(exists, Failure):
        return exists
    if not exists.unwrap():
        return Success(None)
    ancestor = _git_bool(
        repo_dir=repo_dir,
        args=["git", "merge-base", "--is-ancestor", sha, f"origin/{canonical_branch}"],
        absent_object_is_false=False,
    )
    if isinstance(ancestor, Failure):
        return ancestor
    if not ancestor.unwrap():
        return Success(None)
    result = _run_git(
        repo_dir=repo_dir,
        args=[
            "git",
            "rev-list",
            "--merges",
            "--ancestry-path",
            f"{sha}..origin/{canonical_branch}",
        ],
    )
    if isinstance(result, Failure):
        return result
    completed = result.unwrap()
    merges = completed.stdout.split()
    return Success(merges[-1] if merges else sha)


def _git_bool(
    *,
    repo_dir: Path,
    args: list[str],
    absent_object_is_false: bool,
) -> Result[bool, GitEvidenceLookupError]:
    """Run a local git predicate; true/false exits stay on the success track."""
    if not repo_dir.is_dir():
        return Failure(_missing_cwd_failure(repo_dir=repo_dir, command=tuple(args)))
    completed = subprocess.run(
        args,
        cwd=repo_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode == 0:
        passed = True
        return Success(passed)
    if (completed.returncode == 1 and completed.stderr.strip() == "") or (
        absent_object_is_false
        and _is_absent_object(
            stderr=completed.stderr,
        )
    ):
        failed_cleanly = False
        return Success(failed_cleanly)
    return Failure(_git_failure(repo_dir=repo_dir, completed=completed, command=tuple(args)))


def _run_git(
    *,
    repo_dir: Path,
    args: list[str],
) -> Result[subprocess.CompletedProcess[str], GitEvidenceLookupError]:
    """Run local git; any non-zero exit is a failed lookup."""
    if not repo_dir.is_dir():
        return Failure(_missing_cwd_failure(repo_dir=repo_dir, command=tuple(args)))
    completed = subprocess.run(
        args,
        cwd=repo_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode == 0:
        return Success(completed)
    return Failure(_git_failure(repo_dir=repo_dir, completed=completed, command=tuple(args)))


def _git_failure(
    *,
    repo_dir: Path,
    completed: subprocess.CompletedProcess[str],
    command: tuple[str, ...],
) -> GitEvidenceLookupError:
    """Convert a failed subprocess result into the migration's expected error."""
    return GitEvidenceLookupError(
        cwd=repo_dir,
        command=command,
        returncode=completed.returncode,
        stderr=completed.stderr,
    )


def _missing_cwd_failure(*, repo_dir: Path, command: tuple[str, ...]) -> GitEvidenceLookupError:
    """Create the same expected-error shape when cwd is absent."""
    return GitEvidenceLookupError(
        cwd=repo_dir,
        command=command,
        returncode=127,
        stderr="working directory does not exist",
    )


def _is_absent_object(*, stderr: str) -> bool:
    """True when git is saying the candidate object itself is absent."""
    return "Not a valid object name" in stderr or "could not get object info" in stderr

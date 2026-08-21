"""Focused tests for merge-evidence git lookup result shapes."""

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest
from livespec_orchestrator_git_jsonl.migration.merge_evidence_backfill import main
from livespec_orchestrator_git_jsonl.migration.merge_evidence_git import (
    _id_grep_candidates,
    _introducing_sha,
    _is_absent_object,
    discover_merge_sha,
)
from returns.result import Failure, Success


def _run_git(*, args: list[str], cwd: Path) -> str:
    """Run git isolated from host config; return stripped stdout."""
    env = {
        "PATH": os.environ["PATH"],
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "HOME": str(cwd),
    }
    completed = subprocess.run(
        ["git", "-c", "user.email=t@example.com", "-c", "user.name=t", *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip()


def _init_repo(*, root: Path) -> str:
    """Create a git repo with one commit; point origin/master at it; return its SHA."""
    _ = _run_git(args=["init", "--initial-branch=master"], cwd=root)
    _ = (root / "seed.txt").write_text("seed\n", encoding="utf-8")
    _ = _run_git(args=["add", "seed.txt"], cwd=root)
    _ = _run_git(args=["commit", "-m", "seed"], cwd=root)
    _ = _run_git(args=["update-ref", "refs/remotes/origin/master", "HEAD"], cwd=root)
    return _run_git(args=["rev-parse", "HEAD"], cwd=root)


def _raw_record(*, audit: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": "li-aaa111",
        "type": "task",
        "status": "done",
        "title": "t",
        "description": "d",
        "origin": "freeform",
        "gap_id": None,
        "assignee": None,
        "depends_on": [],
        "captured_at": "2026-06-12T00:00:00+00:00",
        "resolution": "completed",
        "reason": "r",
        "audit": audit,
        "superseded_by": None,
        "spec_commitment_hint": None,
        "supersedes": None,
    }


def _legacy_audit(*, commits: list[str]) -> dict[str, Any]:
    return {
        "verification_timestamp": "2026-06-12T00:00:00+00:00",
        "commits": commits,
        "files_changed": [],
    }


def test_discover_merge_sha_preserves_id_grep_failure(tmp_path: Path) -> None:
    repo = tmp_path / "not-a-git-repo"
    repo.mkdir()
    result = discover_merge_sha(
        repo_dir=repo,
        canonical_branch="master",
        work_item_id="li-aaa111",
        commits=[],
    )
    assert isinstance(result, Failure)
    assert result.failure().command == (
        "git",
        "log",
        "--format=%H",
        "--grep=li-aaa111",
        "origin/master",
    )


def test_id_grep_candidates_preserves_existing_non_repo_failure(tmp_path: Path) -> None:
    repo = tmp_path / "not-a-git-repo"
    repo.mkdir()
    result = _id_grep_candidates(
        repo_dir=repo,
        canonical_branch="master",
        work_item_id="li-aaa111",
    )
    assert isinstance(result, Failure)
    assert result.failure().returncode != 0


def test_introducing_sha_returns_none_for_non_ancestor_candidate(tmp_path: Path) -> None:
    _ = _init_repo(root=tmp_path)
    _ = _run_git(args=["checkout", "-b", "side"], cwd=tmp_path)
    _ = (tmp_path / "side.txt").write_text("side\n", encoding="utf-8")
    _ = _run_git(args=["add", "side.txt"], cwd=tmp_path)
    _ = _run_git(args=["commit", "-m", "side"], cwd=tmp_path)
    side_sha = _run_git(args=["rev-parse", "HEAD"], cwd=tmp_path)
    result = _introducing_sha(repo_dir=tmp_path, canonical_branch="master", sha=side_sha)
    assert isinstance(result, Success)
    assert result.unwrap() is None


def test_introducing_sha_preserves_missing_origin_ref_failure(tmp_path: Path) -> None:
    sha = _init_repo(root=tmp_path)
    result = _introducing_sha(repo_dir=tmp_path, canonical_branch="missing", sha=sha)
    assert isinstance(result, Failure)
    assert result.failure().command == (
        "git",
        "merge-base",
        "--is-ancestor",
        sha,
        "origin/missing",
    )


def test_introducing_sha_preserves_rev_list_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(
        args: list[str],
        *,
        cwd: Path,
        capture_output: bool,
        text: bool,
        check: bool,
    ) -> subprocess.CompletedProcess[str]:
        _ = (cwd, capture_output, text, check)
        if args[1] == "rev-list":
            return subprocess.CompletedProcess(
                args=args,
                returncode=2,
                stdout="",
                stderr="rev-list exploded",
            )
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(
        "livespec_orchestrator_git_jsonl.migration.merge_evidence_git.subprocess.run",
        fake_run,
    )
    result = _introducing_sha(repo_dir=tmp_path, canonical_branch="master", sha="abc123")
    assert isinstance(result, Failure)
    assert result.failure().command == (
        "git",
        "rev-list",
        "--merges",
        "--ancestry-path",
        "abc123..origin/master",
    )


def test_main_reports_git_lookup_failure(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "wi.jsonl"
    record = _raw_record(audit=_legacy_audit(commits=["0" * 40]))
    _ = path.write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")
    rc = main(argv=["--path", str(path)])
    captured = capsys.readouterr()
    assert rc == 1
    assert "failed to discover merge evidence" in captured.err
    assert "git cat-file" in captured.err


def test_absent_object_stderr_variants_are_clean_negative() -> None:
    assert _is_absent_object(stderr="fatal: Not a valid object name abc")
    assert _is_absent_object(stderr="fatal: could not get object info")

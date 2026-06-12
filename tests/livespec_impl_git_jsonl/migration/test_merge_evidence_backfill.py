"""Tests for the merge-evidence backfill migration.

Per SPECIFICATION/contracts.md §"Backfill for existing closed
work-items": Strategy (a) — the disciplined default — scans git for
the SHAs in each closed work-item's `audit.commits` (falling back to
a `git log --grep=<id>` walk when none are recorded), resolves the
merge commit on `origin/<canonical_branch>` that introduced the work
(`git rev-list --merges --ancestry-path`, with the commit itself
standing in when the work landed without a merge commit), and
populates `merge_sha`; orphans (no evidence reachable from the
canonical branch) are surfaced as findings and BLOCK all writes.
Strategy (b) — the `--grandfather` fallback — populates the
`<pre-schema-bootstrap>` sentinel instead.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from livespec_impl_git_jsonl.checks.work_item_merge_evidence import (
    GRANDFATHER_MERGE_SHA_SENTINEL,
)
from livespec_impl_git_jsonl.checks.work_item_merge_evidence import (
    main as check_main,
)
from livespec_impl_git_jsonl.migration.merge_evidence_backfill import main
from livespec_impl_git_jsonl.store import (
    append_work_item,
    materialize_work_items,
    read_work_items,
    reduce_work_item_heads,
    work_item_record_identity,
)
from livespec_impl_git_jsonl.types import (
    AuditRecord,
    Resolution,
    WorkItem,
    WorkItemStatus,
    WorkItemType,
)


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


def _init_repo(*, root: Path, message: str = "seed commit") -> str:
    """Create a git repo with one commit; point origin/master at it; return its SHA."""
    _ = _run_git(args=["init", "--initial-branch=master"], cwd=root)
    _ = (root / "seed.txt").write_text("seed\n", encoding="utf-8")
    _ = _run_git(args=["add", "seed.txt"], cwd=root)
    _ = _run_git(args=["commit", "-m", message], cwd=root)
    _ = _run_git(args=["update-ref", "refs/remotes/origin/master", "HEAD"], cwd=root)
    return _run_git(args=["rev-parse", "HEAD"], cwd=root)


def _commit_on_master(*, root: Path, filename: str, message: str) -> str:
    """Add one commit on master; refresh origin/master; return its SHA."""
    _ = (root / filename).write_text(filename + "\n", encoding="utf-8")
    _ = _run_git(args=["add", filename], cwd=root)
    _ = _run_git(args=["commit", "-m", message], cwd=root)
    _ = _run_git(args=["update-ref", "refs/remotes/origin/master", "HEAD"], cwd=root)
    return _run_git(args=["rev-parse", "HEAD"], cwd=root)


def _merged_feature(*, root: Path) -> tuple[str, str]:
    """Merge a feature commit into master via --no-ff; return (work_sha, merge_sha)."""
    _ = _run_git(args=["checkout", "-b", "feature"], cwd=root)
    _ = (root / "feature.txt").write_text("feature\n", encoding="utf-8")
    _ = _run_git(args=["add", "feature.txt"], cwd=root)
    _ = _run_git(args=["commit", "-m", "feature work"], cwd=root)
    work_sha = _run_git(args=["rev-parse", "HEAD"], cwd=root)
    _ = _run_git(args=["checkout", "master"], cwd=root)
    _ = _run_git(args=["merge", "--no-ff", "feature", "-m", "merge feature"], cwd=root)
    merge_sha = _run_git(args=["rev-parse", "HEAD"], cwd=root)
    _ = _run_git(args=["update-ref", "refs/remotes/origin/master", "HEAD"], cwd=root)
    return work_sha, merge_sha


def _raw_record(
    *,
    id_: str = "li-aaa111",
    status: str = "closed",
    resolution: str | None = "completed",
    audit: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": id_,
        "type": "task",
        "status": status,
        "title": "t",
        "description": "d",
        "origin": "freeform",
        "gap_id": None,
        "priority": 2,
        "assignee": None,
        "depends_on": [],
        "captured_at": "2026-06-12T00:00:00+00:00",
        "resolution": resolution,
        "reason": "r",
        "audit": audit,
        "superseded_by": None,
        "spec_commitment_hint": None,
        "supersedes": None,
    }


def _legacy_audit(*, commits: list[str]) -> dict[str, Any]:
    """An audit object authored before the merge_sha schema addition."""
    return {
        "verification_timestamp": "2026-06-12T00:00:00+00:00",
        "commits": commits,
        "files_changed": [],
    }


def _write_raw_store(*, path: Path, records: list[dict[str, Any]]) -> None:
    content = "".join(json.dumps(record, sort_keys=True) + "\n" for record in records)
    _ = path.write_text(content, encoding="utf-8")


def _work_item(
    *,
    id_: str = "li-aaa111",
    type_: WorkItemType = "task",
    status: WorkItemStatus = "closed",
    resolution: Resolution | None = "completed",
    audit: AuditRecord | None = None,
) -> WorkItem:
    return WorkItem(
        id=id_,
        type=type_,
        status=status,
        title="t",
        description="d",
        origin="freeform",
        gap_id=None,
        priority=2,
        assignee=None,
        depends_on=(),
        captured_at="2026-06-12T00:00:00+00:00",
        resolution=resolution,
        reason="r",
        audit=audit,
        superseded_by=None,
    )


def test_main_errors_when_path_missing(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = main(argv=["--path", str(tmp_path / "absent.jsonl")])
    captured = capsys.readouterr()
    assert rc == 1
    assert "does not exist" in captured.err


def test_repairs_audit_missing_merge_sha_using_commit_evidence(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _ = _init_repo(root=tmp_path)
    work_sha, merge_sha = _merged_feature(root=tmp_path)
    path = tmp_path / "wi.jsonl"
    _write_raw_store(
        path=path,
        records=[_raw_record(audit=_legacy_audit(commits=[work_sha]))],
    )
    rc = main(argv=["--path", str(path)])
    captured = capsys.readouterr()
    assert rc == 0
    assert "populated audit.merge_sha" in captured.out
    assert path.read_text(encoding="utf-8").count("\n") == 1
    index = materialize_work_items(records=read_work_items(path=path))
    audit = index["li-aaa111"].audit
    assert audit is not None
    assert audit.merge_sha == merge_sha


def test_repairs_with_commit_itself_when_no_merge_commit_exists(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _ = _init_repo(root=tmp_path)
    work_sha = _commit_on_master(root=tmp_path, filename="work.txt", message="rebased work")
    path = tmp_path / "wi.jsonl"
    _write_raw_store(
        path=path,
        records=[_raw_record(audit=_legacy_audit(commits=[work_sha]))],
    )
    rc = main(argv=["--path", str(path)])
    _ = capsys.readouterr()
    assert rc == 0
    index = materialize_work_items(records=read_work_items(path=path))
    audit = index["li-aaa111"].audit
    assert audit is not None
    assert audit.merge_sha == work_sha


def test_repairs_empty_merge_sha_and_skips_unusable_candidates(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _ = _init_repo(root=tmp_path)
    work_sha = _commit_on_master(root=tmp_path, filename="work.txt", message="work")
    legacy = _legacy_audit(commits=["0" * 40, work_sha])
    legacy["merge_sha"] = ""
    path = tmp_path / "wi.jsonl"
    _write_raw_store(path=path, records=[_raw_record(audit=legacy)])
    rc = main(argv=["--path", str(path)])
    _ = capsys.readouterr()
    assert rc == 0
    index = materialize_work_items(records=read_work_items(path=path))
    audit = index["li-aaa111"].audit
    assert audit is not None
    assert audit.merge_sha == work_sha


def test_repairs_via_id_grep_when_audit_commits_is_empty(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _ = _init_repo(root=tmp_path)
    work_sha = _commit_on_master(root=tmp_path, filename="work.txt", message="fix: close li-aaa111")
    path = tmp_path / "wi.jsonl"
    _write_raw_store(path=path, records=[_raw_record(audit=_legacy_audit(commits=[]))])
    rc = main(argv=["--path", str(path)])
    _ = capsys.readouterr()
    assert rc == 0
    index = materialize_work_items(records=read_work_items(path=path))
    audit = index["li-aaa111"].audit
    assert audit is not None
    assert audit.merge_sha == work_sha


def test_appends_transition_for_audit_null_closure(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _ = _init_repo(root=tmp_path)
    work_sha = _commit_on_master(
        root=tmp_path, filename="work.txt", message="feat: realize li-aaa111"
    )
    path = tmp_path / "wi.jsonl"
    original = _work_item(audit=None)
    append_work_item(path=path, item=original)
    rc = main(argv=["--path", str(path)])
    captured = capsys.readouterr()
    assert rc == 0
    assert "appended merge-evidence transition record" in captured.out
    heads = reduce_work_item_heads(records=read_work_items(path=path))
    assert len(heads["li-aaa111"]) == 1
    head = heads["li-aaa111"][0]
    assert head.supersedes == work_item_record_identity(item=original)
    assert head.audit is not None
    assert head.audit.merge_sha == work_sha
    assert head.audit.pr_number is None


def test_phase_two_orphan_blocks_writes(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _ = _init_repo(root=tmp_path)
    path = tmp_path / "wi.jsonl"
    append_work_item(path=path, item=_work_item(audit=None))
    before = path.read_text(encoding="utf-8")
    rc = main(argv=["--path", str(path)])
    captured = capsys.readouterr()
    assert rc == 1
    assert "no merge evidence found on origin/master" in captured.out
    assert "no records were written" in captured.out
    assert path.read_text(encoding="utf-8") == before


def test_phase_one_orphan_blocks_all_writes(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _ = _init_repo(root=tmp_path)
    _ = _commit_on_master(root=tmp_path, filename="work.txt", message="feat: realize li-bbb222")
    path = tmp_path / "wi.jsonl"
    orphan_line = json.dumps(
        _raw_record(id_="li-aaa111", audit=_legacy_audit(commits=["0" * 40])),
        sort_keys=True,
    )
    evidenced_line = json.dumps(_raw_record(id_="li-bbb222", audit=None), sort_keys=True)
    _ = path.write_text(orphan_line + "\n" + evidenced_line + "\n", encoding="utf-8")
    before = path.read_text(encoding="utf-8")
    rc = main(argv=["--path", str(path)])
    captured = capsys.readouterr()
    assert rc == 1
    assert "li-aaa111" in captured.out
    assert "no merge evidence found" in captured.out
    assert path.read_text(encoding="utf-8") == before


def test_grandfather_sentinels_both_phases_without_git(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "work-items.jsonl"
    _write_raw_store(
        path=path,
        records=[
            _raw_record(id_="li-aaa111", audit=_legacy_audit(commits=["0" * 40])),
            _raw_record(id_="li-bbb222", audit=None),
        ],
    )
    rc = main(argv=["--path", str(path), "--grandfather"])
    _ = capsys.readouterr()
    assert rc == 0
    index = materialize_work_items(records=read_work_items(path=path))
    for item_id in ("li-aaa111", "li-bbb222"):
        audit = index[item_id].audit
        assert audit is not None
        assert audit.merge_sha == GRANDFATHER_MERGE_SHA_SENTINEL
    monkeypatch.chdir(tmp_path)
    check_rc = check_main(argv=[])
    captured = capsys.readouterr()
    assert check_rc == 0
    assert "OK" in captured.out


def test_dry_run_reports_without_writing(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _ = _init_repo(root=tmp_path)
    _ = _commit_on_master(root=tmp_path, filename="work.txt", message="feat: li-aaa111")
    path = tmp_path / "wi.jsonl"
    append_work_item(path=path, item=_work_item(audit=None))
    before = path.read_text(encoding="utf-8")
    rc = main(argv=["--path", str(path), "--dry-run"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "would apply" in captured.out
    assert path.read_text(encoding="utf-8") == before


def test_skips_stores_with_nothing_to_backfill(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "wi.jsonl"
    append_work_item(path=path, item=_work_item(status="open", resolution=None, audit=None))
    append_work_item(
        path=path,
        item=_work_item(id_="li-bbb222", resolution="wontfix", audit=None),
    )
    append_work_item(
        path=path,
        item=_work_item(id_="li-ccc333", type_="epic", resolution="completed", audit=None),
    )
    append_work_item(
        path=path,
        item=_work_item(id_="li-ddd444", resolution=None, audit=None),
    )
    append_work_item(
        path=path,
        item=_work_item(
            id_="li-eee555",
            audit=AuditRecord(
                verification_timestamp="2026-06-12T00:00:00+00:00",
                commits=(),
                files_changed=(),
                merge_sha=GRANDFATHER_MERGE_SHA_SENTINEL,
                pr_number=None,
            ),
        ),
    )
    before = path.read_text(encoding="utf-8")
    rc = main(argv=["--path", str(path)])
    captured = capsys.readouterr()
    assert rc == 0
    assert "0 in-place repair(s), 0 transition append(s)" in captured.out
    assert path.read_text(encoding="utf-8") == before


def test_errors_on_malformed_json_line(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "wi.jsonl"
    _ = path.write_text("not-json\n", encoding="utf-8")
    rc = main(argv=["--path", str(path)])
    captured = capsys.readouterr()
    assert rc == 1
    assert "not backfillable" in captured.err


def test_errors_on_blank_line_between_records(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "wi.jsonl"
    record = json.dumps(_raw_record(audit=None), sort_keys=True)
    _ = path.write_text(record + "\n\n" + record + "\n", encoding="utf-8")
    rc = main(argv=["--path", str(path)])
    captured = capsys.readouterr()
    assert rc == 1
    assert "not backfillable" in captured.err


def test_errors_when_store_still_violates_schema_after_repair(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "wi.jsonl"
    record = _raw_record(audit=None)
    record["blocked_by"] = ["li-zzz999"]
    _write_raw_store(path=path, records=[record])
    rc = main(argv=["--path", str(path)])
    captured = capsys.readouterr()
    assert rc == 1
    assert "not backfillable" in captured.err


def test_honors_canonical_branch_flag(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _ = _init_repo(root=tmp_path)
    _ = (tmp_path / "work.txt").write_text("work\n", encoding="utf-8")
    _ = _run_git(args=["add", "work.txt"], cwd=tmp_path)
    _ = _run_git(args=["commit", "-m", "feat: li-aaa111"], cwd=tmp_path)
    work_sha = _run_git(args=["rev-parse", "HEAD"], cwd=tmp_path)
    _ = _run_git(args=["update-ref", "refs/remotes/origin/release", "HEAD"], cwd=tmp_path)
    path = tmp_path / "wi.jsonl"
    append_work_item(path=path, item=_work_item(audit=None))
    rc = main(argv=["--path", str(path), "--canonical-branch", "release"])
    _ = capsys.readouterr()
    assert rc == 0
    index = materialize_work_items(records=read_work_items(path=path))
    audit = index["li-aaa111"].audit
    assert audit is not None
    assert audit.merge_sha == work_sha


def test_module_is_invocable_as_a_script(tmp_path: Path) -> None:
    """The __main__ guard threads main()'s exit code to the shell."""
    module_path = (
        Path(__file__).resolve().parents[3]
        / ".claude-plugin"
        / "scripts"
        / "livespec_impl_git_jsonl"
        / "migration"
        / "merge_evidence_backfill.py"
    )
    env = {
        "PATH": os.environ["PATH"],
        "PYTHONPATH": str(module_path.parents[2]),
    }
    completed = subprocess.run(
        [sys.executable, str(module_path), "--path", str(tmp_path / "absent.jsonl")],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 1
    assert "does not exist" in completed.stderr

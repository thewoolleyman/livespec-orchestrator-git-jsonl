"""Tests for the `check-work-item-merge-evidence` static check.

Per SPECIFICATION/contracts.md §"Work-items JSONL record schema" →
"`work_item_merge_evidence` static check": every closed work-item with
a merge-implying resolution (`completed`, `spec-revised`,
`resolved-out-of-band`) must carry a non-null audit whose `merge_sha`
exists locally and is reachable from `origin/<canonical_branch>`;
administratively closed work-items (`wontfix`, `duplicate`,
`no-longer-applicable`) must NOT carry merge-evidence; closed items
without a resolution are malformed; epics are exempt but instead
require every local `depends_on` child to be closed. The grandfather
sentinel (`<pre-schema-bootstrap>`, per §"Backfill for existing closed
work-items") is exempt from the reachability test.
"""

import os
import subprocess
from pathlib import Path

import pytest
from livespec_impl_git_jsonl.checks.work_item_merge_evidence import (
    GRANDFATHER_MERGE_SHA_SENTINEL,
    main,
    resolve_canonical_branch,
)
from livespec_impl_git_jsonl.store import append_work_item
from livespec_impl_git_jsonl.types import (
    AuditRecord,
    DependsOnRaw,
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


def _init_repo(*, root: Path) -> str:
    """Create a git repo with one commit; point origin/master at it; return its SHA."""
    _ = _run_git(args=["init", "--initial-branch=master"], cwd=root)
    _ = (root / "seed.txt").write_text("seed\n", encoding="utf-8")
    _ = _run_git(args=["add", "seed.txt"], cwd=root)
    _ = _run_git(args=["commit", "-m", "seed commit"], cwd=root)
    _ = _run_git(args=["update-ref", "refs/remotes/origin/master", "HEAD"], cwd=root)
    return _run_git(args=["rev-parse", "HEAD"], cwd=root)


def _audit(*, merge_sha: str) -> AuditRecord:
    return AuditRecord(
        verification_timestamp="2026-06-12T00:00:00+00:00",
        commits=(),
        files_changed=(),
        merge_sha=merge_sha,
        pr_number=None,
    )


def _work_item(
    *,
    id_: str = "li-aaa111",
    type_: WorkItemType = "task",
    status: WorkItemStatus = "closed",
    resolution: Resolution | None = "completed",
    audit: AuditRecord | None = None,
    depends_on: tuple[DependsOnRaw, ...] = (),
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
        depends_on=depends_on,
        captured_at="2026-06-12T00:00:00+00:00",
        resolution=resolution,
        reason="r" if status == "closed" else None,
        audit=audit,
        superseded_by=None,
    )


def test_main_passes_when_store_absent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    rc = main(argv=[])
    captured = capsys.readouterr()
    assert rc == 0
    assert "absent — skipped" in captured.out
    assert "OK" in captured.out


def test_main_passes_on_empty_store(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    _ = (tmp_path / "work-items.jsonl").write_text("", encoding="utf-8")
    rc = main(argv=[])
    captured = capsys.readouterr()
    assert rc == 0
    assert "OK" in captured.out


def test_main_fails_on_unreadable_store(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    _ = (tmp_path / "work-items.jsonl").write_text("not-json\n", encoding="utf-8")
    rc = main(argv=[])
    captured = capsys.readouterr()
    assert rc == 1
    assert "unreadable" in captured.out
    assert "FAIL" in captured.out


def test_main_skips_non_closed_items(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "work-items.jsonl"
    append_work_item(path=path, item=_work_item(status="open", resolution=None))
    append_work_item(
        path=path, item=_work_item(id_="li-aaa222", status="deferred", resolution=None)
    )
    rc = main(argv=[])
    captured = capsys.readouterr()
    assert rc == 0
    assert "OK" in captured.out


def test_main_passes_on_reachable_merge_sha(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    head = _init_repo(root=tmp_path)
    path = tmp_path / "work-items.jsonl"
    append_work_item(path=path, item=_work_item(audit=_audit(merge_sha=head)))
    rc = main(argv=[])
    captured = capsys.readouterr()
    assert rc == 0
    assert "OK" in captured.out


def test_main_fails_when_required_audit_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "work-items.jsonl"
    append_work_item(path=path, item=_work_item(resolution="spec-revised", audit=None))
    rc = main(argv=[])
    captured = capsys.readouterr()
    assert rc == 1
    assert "li-aaa111" in captured.out
    assert "missing the required audit merge-evidence" in captured.out
    assert "FAIL" in captured.out


def test_main_fails_when_merge_sha_is_unknown_to_git(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    _ = _init_repo(root=tmp_path)
    path = tmp_path / "work-items.jsonl"
    bogus = "0" * 40
    append_work_item(path=path, item=_work_item(audit=_audit(merge_sha=bogus)))
    rc = main(argv=[])
    captured = capsys.readouterr()
    assert rc == 1
    assert bogus in captured.out
    assert "not reachable from origin/master" in captured.out


def test_main_fails_when_merge_sha_is_not_on_canonical_branch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    _ = _init_repo(root=tmp_path)
    _ = (tmp_path / "later.txt").write_text("later\n", encoding="utf-8")
    _ = _run_git(args=["add", "later.txt"], cwd=tmp_path)
    _ = _run_git(args=["commit", "-m", "later commit"], cwd=tmp_path)
    ahead = _run_git(args=["rev-parse", "HEAD"], cwd=tmp_path)
    path = tmp_path / "work-items.jsonl"
    append_work_item(path=path, item=_work_item(audit=_audit(merge_sha=ahead)))
    rc = main(argv=[])
    captured = capsys.readouterr()
    assert rc == 1
    assert "not reachable from origin/master" in captured.out


def test_main_exempts_grandfather_sentinel_from_reachability(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "work-items.jsonl"
    append_work_item(
        path=path,
        item=_work_item(audit=_audit(merge_sha=GRANDFATHER_MERGE_SHA_SENTINEL)),
    )
    rc = main(argv=[])
    captured = capsys.readouterr()
    assert rc == 0
    assert "OK" in captured.out


def test_main_fails_on_administrative_closure_with_audit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "work-items.jsonl"
    append_work_item(
        path=path,
        item=_work_item(resolution="wontfix", audit=_audit(merge_sha="deadbeef")),
    )
    rc = main(argv=[])
    captured = capsys.readouterr()
    assert rc == 1
    assert "must not carry audit merge-evidence" in captured.out


def test_main_passes_on_administrative_closure_without_audit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "work-items.jsonl"
    append_work_item(path=path, item=_work_item(resolution="duplicate", audit=None))
    rc = main(argv=[])
    captured = capsys.readouterr()
    assert rc == 0
    assert "OK" in captured.out


def test_main_fails_on_closed_item_without_resolution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "work-items.jsonl"
    append_work_item(path=path, item=_work_item(resolution=None))
    rc = main(argv=[])
    captured = capsys.readouterr()
    assert rc == 1
    assert "closed work-item without resolution is malformed" in captured.out


def test_main_fails_on_closed_epic_with_non_closed_child(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "work-items.jsonl"
    append_work_item(path=path, item=_work_item(id_="li-chi111", status="open", resolution=None))
    append_work_item(
        path=path,
        item=_work_item(
            id_="li-epi111",
            type_="epic",
            resolution="completed",
            depends_on=({"kind": "local", "work_item_id": "li-chi111"},),
        ),
    )
    rc = main(argv=[])
    captured = capsys.readouterr()
    assert rc == 1
    assert "closed epic has non-closed child 'li-chi111'" in captured.out


def test_main_passes_on_closed_epic_with_closed_children(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "work-items.jsonl"
    append_work_item(
        path=path,
        item=_work_item(id_="li-chi111", resolution="wontfix", audit=None),
    )
    append_work_item(
        path=path,
        item=_work_item(id_="li-chi222", resolution="no-longer-applicable", audit=None),
    )
    append_work_item(
        path=path,
        item=_work_item(
            id_="li-epi111",
            type_="epic",
            resolution="completed",
            depends_on=(
                {"kind": "local", "work_item_id": "li-chi111"},
                "li-chi222",
            ),
        ),
    )
    rc = main(argv=[])
    captured = capsys.readouterr()
    assert rc == 0
    assert "OK" in captured.out


def test_main_skips_unresolvable_epic_children(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "work-items.jsonl"
    append_work_item(
        path=path,
        item=_work_item(
            id_="li-epi111",
            type_="epic",
            resolution="completed",
            depends_on=(
                {"kind": "external", "ref": "livespec#li-zzz999"},
                {"kind": "local", "work_item_id": 5},
                "li-gon000",
            ),
        ),
    )
    rc = main(argv=[])
    captured = capsys.readouterr()
    assert rc == 0
    assert "OK" in captured.out


def test_main_honors_canonical_branch_flag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    head = _init_repo(root=tmp_path)
    _ = _run_git(args=["update-ref", "refs/remotes/origin/release", "HEAD"], cwd=tmp_path)
    path = tmp_path / "work-items.jsonl"
    append_work_item(path=path, item=_work_item(audit=_audit(merge_sha=head)))
    rc = main(argv=["--canonical-branch", "release"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "OK" in captured.out


def test_main_names_flagged_canonical_branch_in_findings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    _ = _init_repo(root=tmp_path)
    path = tmp_path / "work-items.jsonl"
    append_work_item(path=path, item=_work_item(audit=_audit(merge_sha="0" * 40)))
    rc = main(argv=["--canonical-branch", "release"])
    captured = capsys.readouterr()
    assert rc == 1
    assert "not reachable from origin/release" in captured.out


def test_main_with_explicit_store_path(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "custom" / "wi.jsonl"
    append_work_item(path=path, item=_work_item(resolution="completed", audit=None))
    rc = main(argv=["--work-items-path", str(path)])
    captured = capsys.readouterr()
    assert rc == 1
    assert str(path) in captured.out
    assert "missing the required audit merge-evidence" in captured.out


def test_resolve_canonical_branch_prefers_livespec_jsonc_key(tmp_path: Path) -> None:
    _ = (tmp_path / ".livespec.jsonc").write_text(
        '// consumer config\n{"livespec-impl-git-jsonl": {"canonical_branch": "trunk"}}\n',
        encoding="utf-8",
    )
    assert resolve_canonical_branch(repo_dir=tmp_path) == "trunk"


def test_resolve_canonical_branch_uses_origin_head_symbolic_ref(tmp_path: Path) -> None:
    _ = _init_repo(root=tmp_path)
    _ = _run_git(args=["update-ref", "refs/remotes/origin/main", "HEAD"], cwd=tmp_path)
    _ = _run_git(
        args=["symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main"],
        cwd=tmp_path,
    )
    assert resolve_canonical_branch(repo_dir=tmp_path) == "main"


def test_resolve_canonical_branch_defaults_to_master_without_git(tmp_path: Path) -> None:
    assert resolve_canonical_branch(repo_dir=tmp_path) == "master"


@pytest.mark.parametrize(
    "config_text",
    [
        "{not valid jsonc",
        "[1, 2, 3]",
        "{}",
        '{"livespec-impl-git-jsonl": "not-a-block"}',
        '{"livespec-impl-git-jsonl": {}}',
        '{"livespec-impl-git-jsonl": {"canonical_branch": ""}}',
        '{"livespec-impl-git-jsonl": {"canonical_branch": 5}}',
    ],
)
def test_resolve_canonical_branch_falls_back_on_unusable_config(
    tmp_path: Path,
    config_text: str,
) -> None:
    _ = (tmp_path / ".livespec.jsonc").write_text(config_text, encoding="utf-8")
    assert resolve_canonical_branch(repo_dir=tmp_path) == "master"

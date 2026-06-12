"""Tests for the `check-no-divergent-heads` store-integrity check.

Per SPECIFICATION/contracts.md §"Append-only store disciplines" →
"Store-integrity checks (orchestrator-private)": the check materializes
BOTH declared backing stores (work-items + memos) via the canonical
reducer and fires fail when any entity id resolves to more than one
un-superseded head, naming the offending entity id and the conflicting
record identities so the operator can append a reconciling record.
"""

from pathlib import Path

import pytest
from livespec_impl_git_jsonl.checks.no_divergent_heads import main
from livespec_impl_git_jsonl.store import (
    append_memo,
    append_work_item,
    memo_record_identity,
    work_item_record_identity,
)
from livespec_impl_git_jsonl.types import Memo, WorkItem


def _work_item(
    *,
    id_: str = "li-aaa111",
    title: str = "t",
    captured_at: str = "2026-06-11T00:00:00Z",
    supersedes: str | None = None,
) -> WorkItem:
    return WorkItem(
        id=id_,
        type="task",
        status="open",
        title=title,
        description="d",
        origin="freeform",
        gap_id=None,
        priority=2,
        assignee=None,
        depends_on=(),
        captured_at=captured_at,
        resolution=None,
        reason=None,
        audit=None,
        superseded_by=None,
        supersedes=supersedes,
    )


def _memo(
    *,
    id_: str = "mm-aaa111",
    text: str = "some observation",
    captured_at: str = "2026-06-11T00:00:00Z",
    supersedes: str | None = None,
) -> Memo:
    return Memo(
        id=id_,
        text=text,
        state="untriaged",
        disposition=None,
        captured_at=captured_at,
        work_item_id=None,
        knowledge_file=None,
        propose_change_topic=None,
        supersedes=supersedes,
    )


def test_main_passes_when_both_stores_absent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    rc = main(argv=[])
    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out.count("absent — skipped") == 2
    assert "OK" in captured.out


def test_main_passes_on_empty_stores(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    _ = (tmp_path / "work-items.jsonl").write_text("", encoding="utf-8")
    _ = (tmp_path / "memos.jsonl").write_text("", encoding="utf-8")
    rc = main(argv=[])
    captured = capsys.readouterr()
    assert rc == 0
    assert "OK" in captured.out


def test_main_passes_on_clean_stores(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    append_work_item(path=tmp_path / "work-items.jsonl", item=_work_item())
    append_memo(path=tmp_path / "memos.jsonl", memo=_memo())
    rc = main(argv=[])
    captured = capsys.readouterr()
    assert rc == 0
    assert "OK" in captured.out


def test_main_passes_on_resolved_supersession_chain(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "work-items.jsonl"
    original = _work_item(title="original")
    append_work_item(path=path, item=original)
    amendment = _work_item(
        title="amended",
        captured_at="2026-06-11T01:00:00Z",
        supersedes=work_item_record_identity(item=original),
    )
    append_work_item(path=path, item=amendment)
    rc = main(argv=[])
    captured = capsys.readouterr()
    assert rc == 0
    assert "OK" in captured.out


def test_main_fails_on_divergent_work_item_heads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "work-items.jsonl"
    first = _work_item(title="head one")
    second = _work_item(title="head two", captured_at="2026-06-11T01:00:00Z")
    append_work_item(path=path, item=first)
    append_work_item(path=path, item=second)
    rc = main(argv=[])
    captured = capsys.readouterr()
    assert rc == 1
    assert "li-aaa111" in captured.out
    assert "2 un-superseded heads" in captured.out
    assert work_item_record_identity(item=first) in captured.out
    assert work_item_record_identity(item=second) in captured.out
    assert "FAIL" in captured.out


def test_main_fails_on_divergent_memo_heads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "memos.jsonl"
    first = _memo(text="head one")
    second = _memo(text="head two", captured_at="2026-06-11T01:00:00Z")
    append_memo(path=path, memo=first)
    append_memo(path=path, memo=second)
    rc = main(argv=[])
    captured = capsys.readouterr()
    assert rc == 1
    assert "mm-aaa111" in captured.out
    assert "2 un-superseded heads" in captured.out
    assert memo_record_identity(memo=first) in captured.out
    assert memo_record_identity(memo=second) in captured.out
    assert "FAIL" in captured.out


def test_main_fails_on_malformed_work_items_store(
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


def test_main_fails_on_schema_violating_memos_store(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    _ = (tmp_path / "memos.jsonl").write_text('{"id": "mm-aaa111"}\n', encoding="utf-8")
    rc = main(argv=[])
    captured = capsys.readouterr()
    assert rc == 1
    assert "unreadable" in captured.out
    assert "FAIL" in captured.out


def test_main_with_explicit_store_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    work_items_path = tmp_path / "custom" / "wi.jsonl"
    memos_path = tmp_path / "custom" / "mm.jsonl"
    first = _work_item(title="head one")
    second = _work_item(title="head two", captured_at="2026-06-11T01:00:00Z")
    append_work_item(path=work_items_path, item=first)
    append_work_item(path=work_items_path, item=second)
    append_memo(path=memos_path, memo=_memo())
    rc = main(
        argv=[
            "--work-items-path",
            str(work_items_path),
            "--memos-path",
            str(memos_path),
        ]
    )
    captured = capsys.readouterr()
    assert rc == 1
    assert str(work_items_path) in captured.out
    assert "li-aaa111" in captured.out

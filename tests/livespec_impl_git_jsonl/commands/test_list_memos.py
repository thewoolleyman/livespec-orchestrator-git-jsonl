"""Tests for the list-memos thin-transport command."""

import json
from pathlib import Path

import pytest
from livespec_impl_git_jsonl.commands.list_memos import main
from livespec_impl_git_jsonl.store import append_memo
from livespec_impl_git_jsonl.types import Memo


def _memo(*, id_: str, state: str, text: str = "memo body") -> Memo:
    return Memo(
        id=id_,
        text=text,
        state=state,  # type: ignore[arg-type]
        disposition="discard" if state == "dispositioned" else None,
        captured_at="2026-05-19T00:00:00Z",
        work_item_id=None,
        knowledge_file=None,
        propose_change_topic=None,
    )


def test_main_missing_store_prints_no_memos(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    rc = main([])
    captured = capsys.readouterr()
    assert rc == 0
    assert "(no memos)" in captured.out


def test_main_lists_memos_human(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "memos.jsonl"
    append_memo(path=path, memo=_memo(id_="mm-aaa", state="untriaged"))
    rc = main([])
    captured = capsys.readouterr()
    assert rc == 0
    assert "mm-aaa" in captured.out
    assert "untriaged" in captured.out


def test_main_filter_untriaged_excludes_dispositioned(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "memos.jsonl"
    append_memo(path=path, memo=_memo(id_="mm-aaa", state="untriaged"))
    append_memo(path=path, memo=_memo(id_="mm-bbb", state="dispositioned"))
    rc = main(["--filter=untriaged"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "mm-aaa" in captured.out
    assert "mm-bbb" not in captured.out


def test_main_filter_dispositioned(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "memos.jsonl"
    append_memo(path=path, memo=_memo(id_="mm-aaa", state="untriaged"))
    append_memo(path=path, memo=_memo(id_="mm-bbb", state="dispositioned"))
    rc = main(["--filter=dispositioned"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "mm-bbb" in captured.out
    assert "mm-aaa" not in captured.out


def test_main_json_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "memos.jsonl"
    append_memo(path=path, memo=_memo(id_="mm-aaa", state="untriaged"))
    rc = main(["--json"])
    captured = capsys.readouterr()
    assert rc == 0
    payload = json.loads(captured.out)
    assert isinstance(payload, list)
    assert payload[0]["id"] == "mm-aaa"


def test_main_with_custom_memos_path(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "custom-memos.jsonl"
    append_memo(path=path, memo=_memo(id_="mm-aaa", state="untriaged"))
    rc = main(["--memos-path", str(path)])
    captured = capsys.readouterr()
    assert rc == 0
    assert "mm-aaa" in captured.out

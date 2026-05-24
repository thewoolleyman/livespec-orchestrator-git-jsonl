"""Tests for the next thin-transport ranker."""

import json
from pathlib import Path

import pytest
from livespec_impl_plaintext.commands.next import main, rank
from livespec_impl_plaintext.store import append_work_item
from livespec_impl_plaintext.types import WorkItem


def _item(
    *,
    id_: str,
    priority: int = 2,
    origin: str = "freeform",
    captured_at: str = "2026-05-19T00:00:00Z",
    status: str = "open",
    depends_on: tuple[str, ...] = (),
) -> WorkItem:
    return WorkItem(
        id=id_,
        type="task",
        status=status,  # type: ignore[arg-type]
        title=id_,
        description="d",
        origin=origin,  # type: ignore[arg-type]
        gap_id="G1" if origin == "gap-tied" else None,
        priority=priority,
        assignee=None,
        depends_on=depends_on,
        captured_at=captured_at,
        resolution=None,
        reason=None,
        audit=None,
        superseded_by=None,
    )


def test_rank_no_items_returns_none_action() -> None:
    result = rank(items=[])
    assert result["action"] == "none"
    assert result["work_item_ref"] is None
    assert result["urgency"] == "low"


def test_rank_picks_highest_priority() -> None:
    items = [_item(id_="li-a", priority=3), _item(id_="li-b", priority=1)]
    result = rank(items=items)
    assert result["action"] == "implement"
    assert result["work_item_ref"] == "li-b"


def test_rank_gap_tied_beats_freeform_at_same_priority() -> None:
    items = [
        _item(id_="li-a", priority=2, origin="freeform"),
        _item(id_="li-b", priority=2, origin="gap-tied"),
    ]
    result = rank(items=items)
    assert result["work_item_ref"] == "li-b"


def test_rank_oldest_first_at_same_priority_origin() -> None:
    items = [
        _item(id_="li-newer", priority=2, captured_at="2026-05-19T02:00:00Z"),
        _item(id_="li-older", priority=2, captured_at="2026-05-19T01:00:00Z"),
    ]
    result = rank(items=items)
    assert result["work_item_ref"] == "li-older"


def test_rank_id_tiebreaker() -> None:
    items = [
        _item(id_="li-zzz", priority=2, captured_at="t"),
        _item(id_="li-aaa", priority=2, captured_at="t"),
    ]
    result = rank(items=items)
    assert result["work_item_ref"] == "li-aaa"


def test_rank_excludes_blocked_status() -> None:
    items = [_item(id_="li-a", status="blocked"), _item(id_="li-b")]
    result = rank(items=items)
    assert result["work_item_ref"] == "li-b"


def test_rank_excludes_closed_status() -> None:
    items = [_item(id_="li-a", status="closed"), _item(id_="li-b")]
    result = rank(items=items)
    assert result["work_item_ref"] == "li-b"


def test_rank_unresolved_dependency_excludes_item() -> None:
    items = [
        _item(id_="li-blocker"),
        _item(id_="li-blocked", depends_on=("li-blocker",)),
    ]
    result = rank(items=items)
    assert result["work_item_ref"] == "li-blocker"


def test_rank_closed_dependency_unblocks_item() -> None:
    items = [
        _item(id_="li-done", status="closed"),
        _item(id_="li-ready", depends_on=("li-done",)),
    ]
    result = rank(items=items)
    assert result["work_item_ref"] == "li-ready"


def test_rank_missing_local_dependency_does_not_exclude_item() -> None:
    """Missing local ids resolve to UNKNOWN; only OPEN excludes per v072 contract."""
    items = [_item(id_="li-x", depends_on=("li-missing",))]
    result = rank(items=items)
    assert result["action"] == "implement"
    assert result["work_item_ref"] == "li-x"


def test_rank_urgency_high_for_p0() -> None:
    items = [_item(id_="li-x", priority=0)]
    assert rank(items=items)["urgency"] == "high"


def test_rank_urgency_medium_for_p2() -> None:
    items = [_item(id_="li-x", priority=2)]
    assert rank(items=items)["urgency"] == "medium"


def test_rank_urgency_low_for_p4() -> None:
    items = [_item(id_="li-x", priority=4)]
    assert rank(items=items)["urgency"] == "low"


def test_main_missing_store_prints_none(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    rc = main([])
    captured = capsys.readouterr()
    assert rc == 0
    assert "none" in captured.out


def test_main_human_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "work-items.jsonl"
    append_work_item(path=path, item=_item(id_="li-x"))
    rc = main([])
    captured = capsys.readouterr()
    assert rc == 0
    assert "implement" in captured.out
    assert "li-x" in captured.out


def test_main_json_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "work-items.jsonl"
    append_work_item(path=path, item=_item(id_="li-x"))
    rc = main(["--json"])
    captured = capsys.readouterr()
    assert rc == 0
    payload = json.loads(captured.out)
    assert payload["action"] == "implement"
    assert payload["work_item_ref"] == "li-x"

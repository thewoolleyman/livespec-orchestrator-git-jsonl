"""Tests for the next thin-transport ranker.

Per `SPECIFICATION/contracts.md`: the
wrapper emits a `{candidates[], pagination}` envelope with optional
`--limit` (default 5, positive int) and `--offset` (default 0,
non-negative int) flags. Empty `candidates[]` is the no-work signal —
the wrapper MUST NOT degrade to any legacy single-object shape.
"""

import json
from pathlib import Path

import pytest
from livespec_orchestrator_git_jsonl.commands.next import (
    build_envelope,
    main,
    rank_candidates,
)
from livespec_orchestrator_git_jsonl.errors import SchemaViolationError
from livespec_orchestrator_git_jsonl.store import append_work_item
from livespec_orchestrator_git_jsonl.types import WorkItem
from returns.io import IOFailure


def _item(
    *,
    id_: str,
    rank: str = "a1",
    origin: str = "freeform",
    captured_at: str = "2026-05-19T00:00:00Z",
    status: str = "ready",
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
        rank=rank,
        assignee=None,
        depends_on=depends_on,
        captured_at=captured_at,
        resolution=None,
        reason=None,
        audit=None,
        superseded_by=None,
    )


# ---------------------------------------------------------------------------
# rank_candidates — pure-function tier, enumerates ALL ripe candidates.
# ---------------------------------------------------------------------------


def test_rank_candidates_no_items_returns_empty_list() -> None:
    assert rank_candidates(items=[]) == []


def test_rank_candidates_orders_by_rank() -> None:
    # rank is the sole ordering authority (v013); "a1" < "a3" lexicographically.
    items = [_item(id_="li-a", rank="a3"), _item(id_="li-b", rank="a1")]
    result = rank_candidates(items=items)
    assert [c["work_item_ref"] for c in result] == ["li-b", "li-a"]


def test_rank_candidates_origin_does_not_affect_order_at_same_rank() -> None:
    # origin is no longer an ordering signal (priority/origin heuristic retired);
    # identical rank falls through to the id tiebreak.
    items = [
        _item(id_="li-b", rank="a1", origin="freeform"),
        _item(id_="li-a", rank="a1", origin="gap-tied"),
    ]
    result = rank_candidates(items=items)
    assert [c["work_item_ref"] for c in result] == ["li-a", "li-b"]


def test_rank_candidates_captured_at_does_not_affect_order() -> None:
    # captured_at is no longer an ordering signal; identical rank → id tiebreak.
    items = [
        _item(id_="li-newer", rank="a1", captured_at="2026-05-19T02:00:00Z"),
        _item(id_="li-older", rank="a1", captured_at="2026-05-19T01:00:00Z"),
    ]
    result = rank_candidates(items=items)
    assert [c["work_item_ref"] for c in result] == ["li-newer", "li-older"]


def test_rank_candidates_id_tiebreaker() -> None:
    # A tie on rank is broken deterministically by id.
    items = [
        _item(id_="li-zzz", rank="a1"),
        _item(id_="li-aaa", rank="a1"),
    ]
    result = rank_candidates(items=items)
    assert [c["work_item_ref"] for c in result] == ["li-aaa", "li-zzz"]


def test_rank_candidates_excludes_blocked_status() -> None:
    items = [_item(id_="li-a", status="blocked"), _item(id_="li-b")]
    result = rank_candidates(items=items)
    assert [c["work_item_ref"] for c in result] == ["li-b"]


def test_rank_candidates_excludes_done_status() -> None:
    items = [_item(id_="li-a", status="done"), _item(id_="li-b")]
    result = rank_candidates(items=items)
    assert [c["work_item_ref"] for c in result] == ["li-b"]


def test_rank_candidates_unresolved_dependency_excludes_item() -> None:
    items = [
        _item(id_="li-blocker"),
        _item(id_="li-blocked", depends_on=("li-blocker",)),
    ]
    result = rank_candidates(items=items)
    assert [c["work_item_ref"] for c in result] == ["li-blocker"]


def test_rank_candidates_done_dependency_unblocks_item() -> None:
    items = [
        _item(id_="li-done", status="done"),
        _item(id_="li-ready", depends_on=("li-done",)),
    ]
    result = rank_candidates(items=items)
    assert [c["work_item_ref"] for c in result] == ["li-ready"]


def test_rank_candidates_missing_local_dependency_does_not_exclude() -> None:
    """Missing local ids resolve to UNKNOWN; only OPEN excludes per v072 contract."""
    items = [_item(id_="li-x", depends_on=("li-missing",))]
    result = rank_candidates(items=items)
    assert [c["work_item_ref"] for c in result] == ["li-x"]


def test_rank_candidates_carries_required_envelope_fields() -> None:
    items = [_item(id_="li-x", rank="a0", origin="gap-tied")]
    candidates = rank_candidates(items=items)
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate["action"] == "implement"
    assert candidate["work_item_ref"] == "li-x"
    assert candidate["urgency"] == "medium"
    assert candidate["reason"] == "ranked ready item (rank a0, origin gap-tied)"
    # impl-git-jsonl-specific fields MAY ride along (contract permits)
    assert candidate["rank"] == "a0"
    assert candidate["origin"] == "gap-tied"


def test_rank_candidates_urgency_is_always_medium() -> None:
    # `priority` was removed in v013; urgency is a uniform advisory "medium"
    # for every candidate (the ranked ORDER carries the dispatch signal).
    items = [_item(id_="li-x", rank="a0"), _item(id_="li-y", rank="a9")]
    urgencies = {c["urgency"] for c in rank_candidates(items=items)}
    assert urgencies == {"medium"}


# ---------------------------------------------------------------------------
# build_envelope — pagination + envelope wrapping.
# ---------------------------------------------------------------------------


def test_build_envelope_no_items_emits_empty_candidates_with_pagination() -> None:
    envelope = build_envelope(items=[], offset=0, limit=5)
    assert envelope == {
        "candidates": [],
        "pagination": {"offset": 0, "limit": 5, "total": 0, "has_more": False},
    }


def test_build_envelope_applies_limit() -> None:
    items = [_item(id_=f"li-{i:02d}", rank=f"a{i}") for i in range(10)]
    envelope = build_envelope(items=items, offset=0, limit=3)
    candidates = envelope["candidates"]
    assert isinstance(candidates, list)
    assert len(candidates) == 3
    pagination = envelope["pagination"]
    assert pagination == {"offset": 0, "limit": 3, "total": 10, "has_more": True}


def test_build_envelope_applies_offset() -> None:
    items = [_item(id_=f"li-{i:02d}", rank=f"a{i}") for i in range(5)]
    envelope = build_envelope(items=items, offset=2, limit=2)
    candidates = envelope["candidates"]
    assert isinstance(candidates, list)
    # rank order a0..a4 → offset 2 skips li-00, li-01 → emits li-02, li-03
    assert [c["work_item_ref"] for c in candidates] == ["li-02", "li-03"]
    assert envelope["pagination"] == {
        "offset": 2,
        "limit": 2,
        "total": 5,
        "has_more": True,
    }


def test_build_envelope_has_more_false_when_slice_reaches_end() -> None:
    items = [_item(id_=f"li-{i:02d}", rank=f"a{i}") for i in range(3)]
    envelope = build_envelope(items=items, offset=0, limit=5)
    pagination = envelope["pagination"]
    assert pagination == {"offset": 0, "limit": 5, "total": 3, "has_more": False}


def test_build_envelope_offset_past_total_returns_empty_with_has_more_false() -> None:
    items = [_item(id_="li-x")]
    envelope = build_envelope(items=items, offset=5, limit=5)
    assert envelope["candidates"] == []
    assert envelope["pagination"] == {
        "offset": 5,
        "limit": 5,
        "total": 1,
        "has_more": False,
    }


# ---------------------------------------------------------------------------
# main — wrapper-level integration (--json output, flag validation).
# ---------------------------------------------------------------------------


def test_main_missing_store_emits_empty_envelope_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    rc = main(argv=["--json"])
    captured = capsys.readouterr()
    assert rc == 0
    payload = json.loads(captured.out)
    assert payload["candidates"] == []
    assert payload["pagination"] == {
        "offset": 0,
        "limit": 5,
        "total": 0,
        "has_more": False,
    }


def test_main_missing_store_human_output_says_no_work(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    rc = main(argv=[])
    captured = capsys.readouterr()
    assert rc == 0
    # Human-readable no-work signal — no JSON, no legacy "none" action.
    assert "no candidates" in captured.out.lower() or "no work" in captured.out.lower()


def test_main_json_output_envelope_shape(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "work-items.jsonl"
    append_work_item(path=path, item=_item(id_="li-x"))
    rc = main(argv=["--json"])
    captured = capsys.readouterr()
    assert rc == 0
    payload = json.loads(captured.out)
    assert set(payload.keys()) == {"candidates", "pagination"}
    assert len(payload["candidates"]) == 1
    candidate = payload["candidates"][0]
    assert candidate["work_item_ref"] == "li-x"
    assert candidate["action"] == "implement"
    assert payload["pagination"] == {
        "offset": 0,
        "limit": 5,
        "total": 1,
        "has_more": False,
    }


def test_main_human_output_lists_each_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "work-items.jsonl"
    append_work_item(path=path, item=_item(id_="li-x"))
    rc = main(argv=[])
    captured = capsys.readouterr()
    assert rc == 0
    assert "li-x" in captured.out
    assert "implement" in captured.out


def test_main_limit_applied_in_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "work-items.jsonl"
    for i in range(7):
        append_work_item(path=path, item=_item(id_=f"li-{i:02d}", rank=f"a{i}"))
    rc = main(argv=["--json", "--limit", "3"])
    captured = capsys.readouterr()
    assert rc == 0
    payload = json.loads(captured.out)
    assert len(payload["candidates"]) == 3
    assert payload["pagination"]["limit"] == 3
    assert payload["pagination"]["total"] == 7
    assert payload["pagination"]["has_more"] is True


def test_main_offset_applied_in_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "work-items.jsonl"
    for i in range(5):
        append_work_item(path=path, item=_item(id_=f"li-{i:02d}", rank=f"a{i}"))
    rc = main(argv=["--json", "--offset", "2", "--limit", "2"])
    captured = capsys.readouterr()
    assert rc == 0
    payload = json.loads(captured.out)
    assert [c["work_item_ref"] for c in payload["candidates"]] == ["li-02", "li-03"]
    assert payload["pagination"]["offset"] == 2


def test_main_invalid_limit_zero_exits_2(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    rc = main(argv=["--limit", "0"])
    captured = capsys.readouterr()
    assert rc == 2
    assert "limit" in captured.err.lower()


def test_main_invalid_limit_negative_exits_2(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    rc = main(argv=["--limit", "-1"])
    captured = capsys.readouterr()
    assert rc == 2
    assert "limit" in captured.err.lower()


def test_main_invalid_limit_nonint_exits_2(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    rc = main(argv=["--limit", "abc"])
    captured = capsys.readouterr()
    assert rc == 2
    assert "limit" in captured.err.lower()


def test_main_invalid_offset_negative_exits_2(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    rc = main(argv=["--offset", "-1"])
    captured = capsys.readouterr()
    assert rc == 2
    assert "offset" in captured.err.lower()


def test_main_invalid_offset_nonint_exits_2(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    rc = main(argv=["--offset", "xyz"])
    captured = capsys.readouterr()
    assert rc == 2
    assert "offset" in captured.err.lower()


def test_main_offset_zero_is_valid(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`--offset 0` is the documented default; it MUST be accepted."""
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "work-items.jsonl"
    append_work_item(path=path, item=_item(id_="li-x"))
    rc = main(argv=["--json", "--offset", "0"])
    captured = capsys.readouterr()
    assert rc == 0
    payload = json.loads(captured.out)
    assert payload["pagination"]["offset"] == 0


def test_main_raises_non_missing_store_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    error = SchemaViolationError(
        path=tmp_path / "work-items.jsonl",
        line_number=1,
        detail="bad store",
    )
    monkeypatch.setattr(
        "livespec_orchestrator_git_jsonl.commands.next.read_work_items",
        lambda **_kwargs: IOFailure(error),
    )

    with pytest.raises(SchemaViolationError):
        main(argv=["--project-root", str(tmp_path)])

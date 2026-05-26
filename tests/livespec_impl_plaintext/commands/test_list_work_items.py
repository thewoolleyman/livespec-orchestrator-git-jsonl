"""Tests for the list-work-items thin-transport command."""

import json
from pathlib import Path

import pytest
from livespec_impl_plaintext.commands.list_work_items import main
from livespec_impl_plaintext.store import append_work_item
from livespec_impl_plaintext.types import AuditRecord, WorkItem


def _item(
    *,
    id_: str,
    status: str = "open",
    origin: str = "freeform",
    gap_id: str | None = None,
    depends_on: tuple[str, ...] = (),
    priority: int = 2,
    spec_commitment_hint: str | None = None,
) -> WorkItem:
    return WorkItem(
        id=id_,
        type="task",
        status=status,  # type: ignore[arg-type]
        title=f"{id_} title",
        description="d",
        origin=origin,  # type: ignore[arg-type]
        gap_id=gap_id,
        priority=priority,
        assignee=None,
        depends_on=depends_on,
        captured_at="2026-05-19T00:00:00Z",
        resolution="fix" if status == "closed" else None,
        reason="done" if status == "closed" else None,
        audit=AuditRecord(
            verification_timestamp="2026-05-19T01:00:00Z",
            commits=("c",),
            files_changed=("f",),
        )
        if status == "closed"
        else None,
        superseded_by=None,
        spec_commitment_hint=spec_commitment_hint,
    )


def test_main_missing_store_prints_no_items(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    rc = main([])
    captured = capsys.readouterr()
    assert rc == 0
    assert "(no work-items)" in captured.out


def test_main_lists_all_human(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "work-items.jsonl"
    append_work_item(path=path, item=_item(id_="li-a", origin="gap-tied", gap_id="G1"))
    append_work_item(path=path, item=_item(id_="li-b"))
    rc = main([])
    captured = capsys.readouterr()
    assert rc == 0
    assert "li-a" in captured.out
    assert "li-b" in captured.out
    assert "gap=G1" in captured.out


def test_main_filter_gap_tied(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "work-items.jsonl"
    append_work_item(path=path, item=_item(id_="li-a", origin="gap-tied", gap_id="G1"))
    append_work_item(path=path, item=_item(id_="li-b"))
    rc = main(["--filter=gap-tied"])
    captured = capsys.readouterr()
    assert "li-a" in captured.out
    assert "li-b" not in captured.out
    assert rc == 0


def test_main_filter_freeform(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "work-items.jsonl"
    append_work_item(path=path, item=_item(id_="li-a", origin="gap-tied", gap_id="G1"))
    append_work_item(path=path, item=_item(id_="li-b"))
    rc = main(["--filter=freeform"])
    captured = capsys.readouterr()
    assert "li-b" in captured.out
    assert "li-a" not in captured.out
    assert rc == 0


def test_main_filter_blocked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "work-items.jsonl"
    append_work_item(path=path, item=_item(id_="li-a", status="blocked"))
    append_work_item(path=path, item=_item(id_="li-b"))
    rc = main(["--filter=blocked"])
    captured = capsys.readouterr()
    assert "li-a" in captured.out
    assert "li-b" not in captured.out
    assert rc == 0


def test_main_filter_ready_excludes_open_local_deps(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "work-items.jsonl"
    append_work_item(path=path, item=_item(id_="li-a"))
    append_work_item(path=path, item=_item(id_="li-b", depends_on=("li-a",)))
    rc = main(["--filter=ready"])
    captured = capsys.readouterr()
    assert "li-a" in captured.out
    assert "li-b" not in captured.out
    assert rc == 0


def test_main_filter_ready_does_not_exclude_missing_local_dep(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Missing local ids resolve to UNKNOWN; only OPEN excludes per the v072 contract.

    The doctor's `no-orphan-dependency` invariant is the right surface
    for missing-local detection — the next ranker and the ready filter
    deliberately do not double up.
    """
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "work-items.jsonl"
    append_work_item(path=path, item=_item(id_="li-c", depends_on=("li-missing",)))
    rc = main(["--filter=ready"])
    captured = capsys.readouterr()
    assert "li-c" in captured.out
    assert rc == 0


def test_main_filter_ready_includes_closed_deps(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "work-items.jsonl"
    append_work_item(path=path, item=_item(id_="li-a", status="closed"))
    append_work_item(path=path, item=_item(id_="li-b", depends_on=("li-a",)))
    rc = main(["--filter=ready"])
    captured = capsys.readouterr()
    assert "li-b" in captured.out
    assert rc == 0


def test_main_filter_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "work-items.jsonl"
    append_work_item(path=path, item=_item(id_="li-a"))
    append_work_item(path=path, item=_item(id_="li-b", status="closed"))
    rc = main(["--filter=closed"])
    captured = capsys.readouterr()
    assert "li-b" in captured.out
    assert "li-a" not in captured.out
    assert rc == 0


def test_main_with_gap_id_filter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "work-items.jsonl"
    append_work_item(path=path, item=_item(id_="li-a", origin="gap-tied", gap_id="G1"))
    append_work_item(path=path, item=_item(id_="li-b", origin="gap-tied", gap_id="G2"))
    rc = main(["--with-gap-id", "G1"])
    captured = capsys.readouterr()
    assert "li-a" in captured.out
    assert "li-b" not in captured.out
    assert rc == 0


def test_main_json_output_with_audit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "work-items.jsonl"
    append_work_item(path=path, item=_item(id_="li-a", status="closed"))
    rc = main(["--json"])
    captured = capsys.readouterr()
    assert rc == 0
    payload = json.loads(captured.out)
    assert payload[0]["id"] == "li-a"
    assert payload[0]["audit"]["commits"] == ["c"]


def test_main_json_output_without_audit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "work-items.jsonl"
    append_work_item(path=path, item=_item(id_="li-open"))
    rc = main(["--json"])
    captured = capsys.readouterr()
    assert rc == 0
    payload = json.loads(captured.out)
    assert payload[0]["id"] == "li-open"
    assert payload[0]["audit"] is None


def test_main_with_custom_work_items_path(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "custom-work-items.jsonl"
    append_work_item(path=path, item=_item(id_="li-a"))
    rc = main(["--work-items-path", str(path)])
    captured = capsys.readouterr()
    assert rc == 0
    assert "li-a" in captured.out


# -- spec_commitment_hint surface (livespec PC #4 sub-proposal 3) --------


def test_main_json_output_includes_spec_commitment_hint_when_set(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`--json` exposes spec_commitment_hint so the doctor invariant can match."""
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "work-items.jsonl"
    append_work_item(
        path=path,
        item=_item(id_="li-a", spec_commitment_hint="spec-impl-commitment-tracking"),
    )
    rc = main(["--json"])
    captured = capsys.readouterr()
    assert rc == 0
    payload = json.loads(captured.out)
    assert payload[0]["spec_commitment_hint"] == "spec-impl-commitment-tracking"


def test_main_json_output_includes_null_spec_commitment_hint_when_unset(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`--json` carries explicit null for freeform work-items (the unset case)."""
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "work-items.jsonl"
    append_work_item(path=path, item=_item(id_="li-a"))
    rc = main(["--json"])
    captured = capsys.readouterr()
    assert rc == 0
    payload = json.loads(captured.out)
    assert "spec_commitment_hint" in payload[0]
    assert payload[0]["spec_commitment_hint"] is None


def test_main_with_spec_commitment_hint_filter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`--with-spec-commitment-hint=<id_hint>` filters to exact hint match."""
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "work-items.jsonl"
    append_work_item(path=path, item=_item(id_="li-match", spec_commitment_hint="topic-x"))
    append_work_item(path=path, item=_item(id_="li-other", spec_commitment_hint="topic-y"))
    append_work_item(path=path, item=_item(id_="li-none"))
    rc = main(["--with-spec-commitment-hint", "topic-x"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "li-match" in captured.out
    assert "li-other" not in captured.out
    assert "li-none" not in captured.out


def test_main_with_spec_commitment_hint_filter_no_matches(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A hint with no matching record yields the empty-listing message."""
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "work-items.jsonl"
    append_work_item(path=path, item=_item(id_="li-a"))
    rc = main(["--with-spec-commitment-hint", "no-match"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "(no work-items)" in captured.out


def test_main_with_spec_commitment_hint_filter_combines_with_filter_name(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Hint filter composes with --filter (intersect, not union)."""
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "work-items.jsonl"
    append_work_item(
        path=path,
        item=_item(id_="li-open", status="open", spec_commitment_hint="topic-x"),
    )
    append_work_item(
        path=path,
        item=_item(id_="li-closed", status="closed", spec_commitment_hint="topic-x"),
    )
    rc = main(["--filter=closed", "--with-spec-commitment-hint", "topic-x"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "li-closed" in captured.out
    assert "li-open" not in captured.out


def test_main_with_spec_commitment_hint_filter_combines_with_gap_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Hint filter composes with --with-gap-id (intersect, not union)."""
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "work-items.jsonl"
    append_work_item(
        path=path,
        item=_item(
            id_="li-a",
            origin="gap-tied",
            gap_id="G1",
            spec_commitment_hint="topic-x",
        ),
    )
    append_work_item(
        path=path,
        item=_item(id_="li-b", spec_commitment_hint="topic-x"),
    )
    rc = main(["--with-gap-id", "G1", "--with-spec-commitment-hint", "topic-x"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "li-a" in captured.out
    assert "li-b" not in captured.out

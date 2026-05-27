"""Tests for the beads → JSONL migration utility."""

import json
from pathlib import Path

import pytest
from livespec_impl_plaintext.migration.beads_to_jsonl import (
    main,
    translate_record,
)
from livespec_impl_plaintext.store import read_work_items


def _beads_dict(
    *,
    id_: str = "li-aaa111",
    issue_type: str = "task",
    status: str = "open",
    title: str = "test title",
    description: str = "test description",
    priority: int = 2,
    assignee: str | None = None,
    created_at: str = "2026-05-01T00:00:00Z",
    labels: list[str] | None = None,
    close_reason: str | None = None,
    notes: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "_type": "issue",
        "id": id_,
        "title": title,
        "description": description,
        "status": status,
        "priority": priority,
        "issue_type": issue_type,
        "created_at": created_at,
    }
    if assignee is not None:
        payload["assignee"] = assignee
    if labels is not None:
        payload["labels"] = labels
    if close_reason is not None:
        payload["close_reason"] = close_reason
    if notes is not None:
        payload["notes"] = notes
    return payload


def test_translate_open_freeform_record() -> None:
    parsed = _beads_dict()
    item = translate_record(parsed=parsed)
    assert item.id == "li-aaa111"
    assert item.status == "open"
    assert item.origin == "freeform"
    assert item.gap_id is None
    assert item.resolution is None
    assert item.audit is None


def test_translate_record_carries_assignee() -> None:
    parsed = _beads_dict(assignee="thewoolleyman")
    item = translate_record(parsed=parsed)
    assert item.assignee == "thewoolleyman"


def test_translate_open_gap_tied_record() -> None:
    parsed = _beads_dict(labels=["gap-id:gap-0007"])
    item = translate_record(parsed=parsed)
    assert item.origin == "gap-tied"
    assert item.gap_id == "gap-0007"


def test_translate_closed_with_resolution_label() -> None:
    parsed = _beads_dict(
        status="closed",
        labels=["gap-id:gap-0007", "resolution:completed"],
        close_reason="all green",
    )
    item = translate_record(parsed=parsed)
    assert item.status == "closed"
    assert item.resolution == "completed"
    assert item.reason == "all green"


def test_translate_closed_gap_tied_extracts_audit_from_notes() -> None:
    notes = (
        "Gap id: gap-0007\n"
        "Verification run_id: c4528e58-926d-450e-96f1-ebe294c3f1c2\n"
        "Verification timestamp: 2026-05-10T06:33:13Z\n"
    )
    parsed = _beads_dict(
        status="closed",
        labels=["gap-id:gap-0007", "resolution:completed"],
        close_reason="closed",
        notes=notes,
    )
    item = translate_record(parsed=parsed)
    assert item.audit is not None
    assert item.audit.verification_timestamp == "2026-05-10T06:33:13Z"
    assert item.audit.commits == ()
    assert item.audit.files_changed == ()


def test_translate_closed_freeform_no_audit() -> None:
    parsed = _beads_dict(
        status="closed",
        close_reason="wontfix",
        labels=["resolution:wontfix"],
    )
    item = translate_record(parsed=parsed)
    assert item.audit is None


def test_translate_closed_gap_tied_missing_notes_no_audit() -> None:
    parsed = _beads_dict(
        status="closed",
        labels=["gap-id:gap-0007", "resolution:completed"],
        close_reason="closed",
    )
    item = translate_record(parsed=parsed)
    assert item.audit is None


def test_translate_closed_gap_tied_notes_without_timestamp_no_audit() -> None:
    parsed = _beads_dict(
        status="closed",
        labels=["gap-id:gap-0007", "resolution:completed"],
        close_reason="closed",
        notes="Gap id: gap-0007\nVerification run_id: x\n",
    )
    item = translate_record(parsed=parsed)
    assert item.audit is None


def test_translate_non_string_label_is_ignored() -> None:
    parsed = _beads_dict(labels=[1234, "gap-id:gap-0007"])  # type: ignore[list-item]
    item = translate_record(parsed=parsed)
    assert item.gap_id == "gap-0007"


def test_main_writes_records_and_skips_blank_lines(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    beads_path = tmp_path / "issues.jsonl"
    out_path = tmp_path / "work-items.jsonl"
    lines = [
        json.dumps(_beads_dict(id_="li-a")),
        "",
        json.dumps(_beads_dict(id_="li-b", labels=["gap-id:gap-0001"])),
    ]
    _ = beads_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    rc = main(["--beads-jsonl", str(beads_path), "--work-items-out", str(out_path)])
    captured = capsys.readouterr()
    assert rc == 0
    assert "migrated 2 beads issues" in captured.out
    written = list(read_work_items(path=out_path))
    assert [w.id for w in written] == ["li-a", "li-b"]


def test_main_skips_non_object_lines(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    beads_path = tmp_path / "issues.jsonl"
    out_path = tmp_path / "work-items.jsonl"
    lines = [
        json.dumps(_beads_dict(id_="li-a")),
        json.dumps(["not", "an", "object"]),
        json.dumps(_beads_dict(id_="li-b")),
    ]
    _ = beads_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    rc = main(["--beads-jsonl", str(beads_path), "--work-items-out", str(out_path)])
    captured = capsys.readouterr()
    assert rc == 0
    assert "migrated 2 beads issues" in captured.out

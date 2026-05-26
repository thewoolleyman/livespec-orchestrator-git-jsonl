"""Tests for the JSONL store primitives."""

import json
from pathlib import Path

import pytest
from livespec_impl_plaintext.errors import (
    MalformedRecordLineError,
    SchemaViolationError,
    StoreFileMissingError,
)
from livespec_impl_plaintext.store import (
    append_memo,
    append_work_item,
    materialize_memos,
    materialize_work_items,
    read_memos,
    read_work_items,
)
from livespec_impl_plaintext.types import AuditRecord, Memo, WorkItem


def _minimal_work_item(
    *,
    id_: str = "li-aaa111",
    status: str = "open",
    resolution: str | None = None,
    audit: AuditRecord | None = None,
) -> WorkItem:
    return WorkItem(
        id=id_,
        type="task",
        status=status,  # type: ignore[arg-type]
        title="t",
        description="d",
        origin="freeform",
        gap_id=None,
        priority=2,
        assignee=None,
        depends_on=(),
        captured_at="2026-05-19T00:00:00Z",
        resolution=resolution,  # type: ignore[arg-type]
        reason=None,
        audit=audit,
        superseded_by=None,
    )


def _minimal_memo(
    *,
    id_: str = "mm-aaa111",
    state: str = "untriaged",
    disposition: str | None = None,
) -> Memo:
    return Memo(
        id=id_,
        text="some observation",
        state=state,  # type: ignore[arg-type]
        disposition=disposition,  # type: ignore[arg-type]
        captured_at="2026-05-19T00:00:00Z",
        work_item_id=None,
        knowledge_file=None,
        propose_change_topic=None,
    )


def test_read_work_items_missing_file_raises(tmp_path: Path) -> None:
    path = tmp_path / "missing.jsonl"
    with pytest.raises(StoreFileMissingError) as excinfo:
        list(read_work_items(path=path))
    assert excinfo.value.path == path


def test_read_work_items_happy_path(tmp_path: Path) -> None:
    path = tmp_path / "work-items.jsonl"
    item = _minimal_work_item()
    append_work_item(path=path, item=item)
    items = list(read_work_items(path=path))
    assert items == [item]


def test_append_work_item_with_audit_roundtrips(tmp_path: Path) -> None:
    path = tmp_path / "work-items.jsonl"
    audit = AuditRecord(
        verification_timestamp="2026-05-19T01:00:00Z",
        commits=("deadbeef",),
        files_changed=("a.py",),
    )
    item = _minimal_work_item(id_="li-zzz999", status="closed", resolution="fix", audit=audit)
    append_work_item(path=path, item=item)
    [read_back] = list(read_work_items(path=path))
    assert read_back == item


def test_read_work_items_empty_line_raises(tmp_path: Path) -> None:
    path = tmp_path / "work-items.jsonl"
    _ = path.write_text("\n", encoding="utf-8")
    with pytest.raises(MalformedRecordLineError) as excinfo:
        list(read_work_items(path=path))
    assert "empty line" in excinfo.value.detail


def test_read_work_items_non_json_raises(tmp_path: Path) -> None:
    path = tmp_path / "work-items.jsonl"
    _ = path.write_text("not-json\n", encoding="utf-8")
    with pytest.raises(MalformedRecordLineError) as excinfo:
        list(read_work_items(path=path))
    assert "JSON parse error" in excinfo.value.detail


def test_read_work_items_non_object_root_raises(tmp_path: Path) -> None:
    path = tmp_path / "work-items.jsonl"
    _ = path.write_text('["array"]\n', encoding="utf-8")
    with pytest.raises(MalformedRecordLineError) as excinfo:
        list(read_work_items(path=path))
    assert "JSON object" in excinfo.value.detail


def test_read_work_items_missing_required_key_raises(tmp_path: Path) -> None:
    path = tmp_path / "work-items.jsonl"
    _ = path.write_text(json.dumps({"id": "li-bbb"}) + "\n", encoding="utf-8")
    with pytest.raises(SchemaViolationError) as excinfo:
        list(read_work_items(path=path))
    assert "missing required keys" in excinfo.value.detail


def test_read_work_items_extra_key_raises(tmp_path: Path) -> None:
    path = tmp_path / "work-items.jsonl"
    item = _minimal_work_item()
    append_work_item(path=path, item=item)
    raw = path.read_text(encoding="utf-8")
    payload = json.loads(raw)
    payload["unexpected"] = "value"
    _ = path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    with pytest.raises(SchemaViolationError) as excinfo:
        list(read_work_items(path=path))
    assert "unexpected extra keys" in excinfo.value.detail


def test_read_work_items_bad_enum_status_raises(tmp_path: Path) -> None:
    path = tmp_path / "work-items.jsonl"
    item = _minimal_work_item()
    append_work_item(path=path, item=item)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["status"] = "not-a-real-status"
    _ = path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    with pytest.raises(SchemaViolationError) as excinfo:
        list(read_work_items(path=path))
    assert "status" in excinfo.value.detail


def test_read_work_items_bad_enum_type_raises(tmp_path: Path) -> None:
    path = tmp_path / "work-items.jsonl"
    item = _minimal_work_item()
    append_work_item(path=path, item=item)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["type"] = "not-a-real-type"
    _ = path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    with pytest.raises(SchemaViolationError) as excinfo:
        list(read_work_items(path=path))
    assert "type" in excinfo.value.detail


def test_read_work_items_bad_enum_origin_raises(tmp_path: Path) -> None:
    path = tmp_path / "work-items.jsonl"
    item = _minimal_work_item()
    append_work_item(path=path, item=item)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["origin"] = "not-a-real-origin"
    _ = path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    with pytest.raises(SchemaViolationError) as excinfo:
        list(read_work_items(path=path))
    assert "origin" in excinfo.value.detail


def test_read_work_items_bad_enum_resolution_raises(tmp_path: Path) -> None:
    path = tmp_path / "work-items.jsonl"
    item = _minimal_work_item(status="closed", resolution="fix")
    append_work_item(path=path, item=item)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["resolution"] = "not-a-real-resolution"
    _ = path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    with pytest.raises(SchemaViolationError) as excinfo:
        list(read_work_items(path=path))
    assert "resolution" in excinfo.value.detail


def test_read_work_items_audit_missing_keys_raises(tmp_path: Path) -> None:
    path = tmp_path / "work-items.jsonl"
    payload = {
        "id": "li-x",
        "type": "task",
        "status": "closed",
        "title": "t",
        "description": "d",
        "origin": "freeform",
        "gap_id": None,
        "priority": 2,
        "assignee": None,
        "depends_on": [],
        "captured_at": "2026-05-19T00:00:00Z",
        "resolution": "fix",
        "reason": "fixed",
        "audit": {"verification_timestamp": "2026-05-19T00:00:00Z"},
        "superseded_by": None,
    }
    _ = path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    with pytest.raises(SchemaViolationError) as excinfo:
        list(read_work_items(path=path))
    assert "audit object missing keys" in excinfo.value.detail


def test_read_memos_missing_file_raises(tmp_path: Path) -> None:
    path = tmp_path / "memos.jsonl"
    with pytest.raises(StoreFileMissingError):
        list(read_memos(path=path))


def test_read_memos_happy_path(tmp_path: Path) -> None:
    path = tmp_path / "memos.jsonl"
    memo = _minimal_memo()
    append_memo(path=path, memo=memo)
    [read_back] = list(read_memos(path=path))
    assert read_back == memo


def test_read_memos_with_disposition_roundtrips(tmp_path: Path) -> None:
    path = tmp_path / "memos.jsonl"
    memo = Memo(
        id="mm-zzz999",
        text="dispositioned memo",
        state="dispositioned",
        disposition="impl-bound",
        captured_at="2026-05-19T00:00:00Z",
        work_item_id="li-aaa111",
        knowledge_file=None,
        propose_change_topic=None,
    )
    append_memo(path=path, memo=memo)
    [read_back] = list(read_memos(path=path))
    assert read_back == memo


def test_read_memos_bad_enum_state_raises(tmp_path: Path) -> None:
    path = tmp_path / "memos.jsonl"
    memo = _minimal_memo()
    append_memo(path=path, memo=memo)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["state"] = "not-a-real-state"
    _ = path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    with pytest.raises(SchemaViolationError) as excinfo:
        list(read_memos(path=path))
    assert "state" in excinfo.value.detail


def test_read_memos_bad_enum_disposition_raises(tmp_path: Path) -> None:
    path = tmp_path / "memos.jsonl"
    memo = Memo(
        id="mm-x",
        text="x",
        state="dispositioned",
        disposition="impl-bound",
        captured_at="2026-05-19T00:00:00Z",
        work_item_id="li-x",
        knowledge_file=None,
        propose_change_topic=None,
    )
    append_memo(path=path, memo=memo)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["disposition"] = "not-a-real-disposition"
    _ = path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    with pytest.raises(SchemaViolationError) as excinfo:
        list(read_memos(path=path))
    assert "disposition" in excinfo.value.detail


def test_materialize_work_items_latest_wins(tmp_path: Path) -> None:
    path = tmp_path / "work-items.jsonl"
    first = _minimal_work_item(id_="li-a", status="open")
    second = _minimal_work_item(id_="li-a", status="closed", resolution="fix")
    other = _minimal_work_item(id_="li-b")
    append_work_item(path=path, item=first)
    append_work_item(path=path, item=second)
    append_work_item(path=path, item=other)
    materialized = materialize_work_items(read_work_items(path=path))
    assert materialized["li-a"].status == "closed"
    assert materialized["li-b"].status == "open"


def test_materialize_memos_latest_wins(tmp_path: Path) -> None:
    path = tmp_path / "memos.jsonl"
    first = _minimal_memo(id_="mm-a", state="untriaged")
    second = Memo(
        id="mm-a",
        text="some observation",
        state="dispositioned",
        disposition="discard",
        captured_at="2026-05-19T00:00:00Z",
        work_item_id=None,
        knowledge_file=None,
        propose_change_topic=None,
    )
    append_memo(path=path, memo=first)
    append_memo(path=path, memo=second)
    materialized = materialize_memos(read_memos(path=path))
    assert materialized["mm-a"].state == "dispositioned"


def test_append_creates_parent_directory(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "deeper" / "work-items.jsonl"
    item = _minimal_work_item()
    append_work_item(path=path, item=item)
    assert path.exists()
    assert path.parent.is_dir()


def test_append_work_item_rejects_bad_enum_status(tmp_path: Path) -> None:
    path = tmp_path / "work-items.jsonl"
    bad = _minimal_work_item(status="not-a-real-status")
    with pytest.raises(SchemaViolationError) as excinfo:
        append_work_item(path=path, item=bad)
    assert "status" in excinfo.value.detail


def test_append_work_item_rejects_bad_enum_type(tmp_path: Path) -> None:
    path = tmp_path / "work-items.jsonl"
    item = WorkItem(
        id="li-aaa222",
        type="not-a-real-type",  # type: ignore[arg-type]
        status="open",
        title="t",
        description="d",
        origin="freeform",
        gap_id=None,
        priority=2,
        assignee=None,
        depends_on=(),
        captured_at="2026-05-19T00:00:00Z",
        resolution=None,
        reason=None,
        audit=None,
        superseded_by=None,
    )
    with pytest.raises(SchemaViolationError) as excinfo:
        append_work_item(path=path, item=item)
    assert "type" in excinfo.value.detail


def test_append_work_item_rejects_bad_enum_origin(tmp_path: Path) -> None:
    path = tmp_path / "work-items.jsonl"
    item = WorkItem(
        id="li-aaa333",
        type="task",
        status="open",
        title="t",
        description="d",
        origin="not-a-real-origin",  # type: ignore[arg-type]
        gap_id=None,
        priority=2,
        assignee=None,
        depends_on=(),
        captured_at="2026-05-19T00:00:00Z",
        resolution=None,
        reason=None,
        audit=None,
        superseded_by=None,
    )
    with pytest.raises(SchemaViolationError) as excinfo:
        append_work_item(path=path, item=item)
    assert "origin" in excinfo.value.detail


def test_append_work_item_rejects_bad_enum_resolution(tmp_path: Path) -> None:
    path = tmp_path / "work-items.jsonl"
    bad = _minimal_work_item(status="closed", resolution="not-a-real-resolution")
    with pytest.raises(SchemaViolationError) as excinfo:
        append_work_item(path=path, item=bad)
    assert "resolution" in excinfo.value.detail


def test_append_work_item_does_not_write_on_validation_failure(tmp_path: Path) -> None:
    path = tmp_path / "work-items.jsonl"
    bad = _minimal_work_item(status="not-a-real-status")
    with pytest.raises(SchemaViolationError):
        append_work_item(path=path, item=bad)
    assert not path.exists()


def test_append_memo_rejects_bad_enum_state(tmp_path: Path) -> None:
    path = tmp_path / "memos.jsonl"
    bad = _minimal_memo(state="not-a-real-state")
    with pytest.raises(SchemaViolationError) as excinfo:
        append_memo(path=path, memo=bad)
    assert "state" in excinfo.value.detail


def test_append_memo_rejects_bad_enum_disposition(tmp_path: Path) -> None:
    path = tmp_path / "memos.jsonl"
    bad = _minimal_memo(state="dispositioned", disposition="not-a-real-disposition")
    with pytest.raises(SchemaViolationError) as excinfo:
        append_memo(path=path, memo=bad)
    assert "disposition" in excinfo.value.detail


def test_append_memo_does_not_write_on_validation_failure(tmp_path: Path) -> None:
    path = tmp_path / "memos.jsonl"
    bad = _minimal_memo(state="not-a-real-state")
    with pytest.raises(SchemaViolationError):
        append_memo(path=path, memo=bad)
    assert not path.exists()


# -- spec_commitment_hint field (livespec PC #4 sub-proposal 3) ----------


def test_work_item_default_spec_commitment_hint_is_none() -> None:
    """WorkItem dataclass defaults spec_commitment_hint to None."""
    item = _minimal_work_item()
    assert item.spec_commitment_hint is None


def test_append_work_item_with_spec_commitment_hint_roundtrips(tmp_path: Path) -> None:
    """A work-item with a hint round-trips through write+read losslessly."""
    path = tmp_path / "work-items.jsonl"
    item = WorkItem(
        id="li-hint01",
        type="task",
        status="open",
        title="t",
        description="d",
        origin="freeform",
        gap_id=None,
        priority=2,
        assignee=None,
        depends_on=(),
        captured_at="2026-05-19T00:00:00Z",
        resolution=None,
        reason=None,
        audit=None,
        superseded_by=None,
        spec_commitment_hint="spec-impl-commitment-tracking",
    )
    append_work_item(path=path, item=item)
    [read_back] = list(read_work_items(path=path))
    assert read_back == item
    assert read_back.spec_commitment_hint == "spec-impl-commitment-tracking"


def test_append_work_item_without_spec_commitment_hint_writes_null(tmp_path: Path) -> None:
    """Write path always serializes the field (explicit null on omission)."""
    path = tmp_path / "work-items.jsonl"
    item = _minimal_work_item()
    append_work_item(path=path, item=item)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert "spec_commitment_hint" in payload
    assert payload["spec_commitment_hint"] is None


def test_read_legacy_work_item_without_field_defaults_to_none(tmp_path: Path) -> None:
    """Legacy records lacking spec_commitment_hint read back with None.

    Per livespec PC #4 sub-proposal 3, the OPTIONAL field's read
    path treats absence as None — work-items.jsonl records authored
    before the field landed MUST continue to parse cleanly without
    in-place migration.
    """
    path = tmp_path / "work-items.jsonl"
    legacy_payload = {
        "id": "li-legacy",
        "type": "task",
        "status": "open",
        "title": "legacy",
        "description": "from before the field landed",
        "origin": "freeform",
        "gap_id": None,
        "priority": 2,
        "assignee": None,
        "depends_on": [],
        "captured_at": "2026-05-19T00:00:00Z",
        "resolution": None,
        "reason": None,
        "audit": None,
        "superseded_by": None,
    }
    _ = path.write_text(json.dumps(legacy_payload) + "\n", encoding="utf-8")
    [read_back] = list(read_work_items(path=path))
    assert read_back.spec_commitment_hint is None


def test_read_work_item_with_non_string_hint_raises(tmp_path: Path) -> None:
    """A non-string non-null hint value fires SchemaViolationError."""
    path = tmp_path / "work-items.jsonl"
    item = _minimal_work_item()
    append_work_item(path=path, item=item)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["spec_commitment_hint"] = 42
    _ = path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    with pytest.raises(SchemaViolationError) as excinfo:
        list(read_work_items(path=path))
    assert "spec_commitment_hint" in excinfo.value.detail


def test_append_work_item_rejects_non_string_hint(tmp_path: Path) -> None:
    """The append-side validator rejects a non-string hint payload."""
    path = tmp_path / "work-items.jsonl"
    bad = WorkItem(
        id="li-badhint",
        type="task",
        status="open",
        title="t",
        description="d",
        origin="freeform",
        gap_id=None,
        priority=2,
        assignee=None,
        depends_on=(),
        captured_at="2026-05-19T00:00:00Z",
        resolution=None,
        reason=None,
        audit=None,
        superseded_by=None,
        spec_commitment_hint=42,  # type: ignore[arg-type]
    )
    with pytest.raises(SchemaViolationError) as excinfo:
        append_work_item(path=path, item=bad)
    assert "spec_commitment_hint" in excinfo.value.detail


def test_read_work_item_still_rejects_unexpected_extra_keys(tmp_path: Path) -> None:
    """Extras outside required+optional union still raise (regression guard)."""
    path = tmp_path / "work-items.jsonl"
    item = _minimal_work_item()
    append_work_item(path=path, item=item)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["surprise_key"] = "value"
    _ = path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    with pytest.raises(SchemaViolationError) as excinfo:
        list(read_work_items(path=path))
    assert "unexpected extra keys" in excinfo.value.detail

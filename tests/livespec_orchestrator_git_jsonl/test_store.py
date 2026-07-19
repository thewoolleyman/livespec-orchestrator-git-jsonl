"""Tests for the JSONL store primitives."""

import hashlib
import inspect
import json
from collections.abc import Iterator
from dataclasses import asdict
from itertools import permutations
from pathlib import Path
from typing import Any, get_type_hints

import pytest
from livespec_orchestrator_git_jsonl.errors import (
    MalformedRecordLineError,
    SchemaViolationError,
    StoreFileMissingError,
)
from livespec_orchestrator_git_jsonl.io.store import append_record
from livespec_orchestrator_git_jsonl.store import (
    WORK_ITEM_STORE_PROTOCOL_DIVERGENCE_DEPENDS_ON,
    JsonlWorkItemStore,
    append_work_item,
    materialize_work_items,
    read_work_items,
    reduce_work_item_heads,
    work_item_record_identity,
)
from livespec_orchestrator_git_jsonl.types import AuditRecord, WorkItem
from livespec_runtime.work_items.rank import BOTTOM_SENTINEL
from livespec_runtime.work_items.store import WorkItemStore
from returns.io import IOFailure, IOResult, IOSuccess
from returns.unsafe import unsafe_perform_io


def _read_success(result: IOResult[list[WorkItem], Exception]) -> list[WorkItem]:
    if isinstance(result, IOFailure):
        raise unsafe_perform_io(result.failure())
    assert isinstance(result, IOSuccess)
    return unsafe_perform_io(result.unwrap())


def _append_failure(result: IOResult[None, Exception]) -> Exception:
    assert isinstance(result, IOFailure)
    return unsafe_perform_io(result.failure())


def _minimal_work_item(
    *,
    id_: str = "li-aaa111",
    status: str = "ready",
    resolution: str | None = None,
    audit: AuditRecord | None = None,
    captured_at: str = "2026-05-19T00:00:00Z",
    supersedes: str | None = None,
    rank: str = "a1",
) -> WorkItem:
    return WorkItem(
        id=id_,
        type="task",
        status=status,  # type: ignore[arg-type]
        title="t",
        description="d",
        origin="freeform",
        gap_id=None,
        rank=rank,
        assignee=None,
        depends_on=(),
        captured_at=captured_at,
        resolution=resolution,  # type: ignore[arg-type]
        reason=None,
        audit=audit,
        superseded_by=None,
        supersedes=supersedes,
    )


def test_append_record_returns_io_failure_on_os_error(tmp_path: Path) -> None:
    parent_file = tmp_path / "not-a-dir"
    parent_file.write_text("x", encoding="utf-8")

    failure = _append_failure(append_record(path=parent_file / "store.jsonl", payload={"x": 1}))

    assert isinstance(failure, OSError)


def test_read_work_items_missing_file_raises(tmp_path: Path) -> None:
    path = tmp_path / "missing.jsonl"
    with pytest.raises(StoreFileMissingError) as excinfo:
        _read_success(read_work_items(path=path))
    assert excinfo.value.path == path


def test_read_work_items_happy_path(tmp_path: Path) -> None:
    path = tmp_path / "work-items.jsonl"
    item = _minimal_work_item()
    append_work_item(path=path, item=item)
    items = _read_success(read_work_items(path=path))
    assert items == [item]


def test_append_work_item_with_audit_roundtrips(tmp_path: Path) -> None:
    path = tmp_path / "work-items.jsonl"
    audit = AuditRecord(
        verification_timestamp="2026-05-19T01:00:00Z",
        commits=("deadbeef",),
        files_changed=("a.py",),
        merge_sha="abc123",
    )
    item = _minimal_work_item(id_="li-zzz999", status="done", resolution="completed", audit=audit)
    append_work_item(path=path, item=item)
    [read_back] = _read_success(read_work_items(path=path))
    assert read_back == item


def test_read_work_items_empty_line_raises(tmp_path: Path) -> None:
    path = tmp_path / "work-items.jsonl"
    _ = path.write_text("\n", encoding="utf-8")
    with pytest.raises(MalformedRecordLineError) as excinfo:
        _read_success(read_work_items(path=path))
    assert "empty line" in excinfo.value.detail


def test_read_work_items_non_json_raises(tmp_path: Path) -> None:
    path = tmp_path / "work-items.jsonl"
    _ = path.write_text("not-json\n", encoding="utf-8")
    with pytest.raises(MalformedRecordLineError) as excinfo:
        _read_success(read_work_items(path=path))
    assert "JSON parse error" in excinfo.value.detail


def test_read_work_items_non_object_root_raises(tmp_path: Path) -> None:
    path = tmp_path / "work-items.jsonl"
    _ = path.write_text('["array"]\n', encoding="utf-8")
    with pytest.raises(MalformedRecordLineError) as excinfo:
        _read_success(read_work_items(path=path))
    assert "JSON object" in excinfo.value.detail


def test_read_work_items_missing_required_key_raises(tmp_path: Path) -> None:
    path = tmp_path / "work-items.jsonl"
    _ = path.write_text(json.dumps({"id": "li-bbb"}) + "\n", encoding="utf-8")
    with pytest.raises(SchemaViolationError) as excinfo:
        _read_success(read_work_items(path=path))
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
        _read_success(read_work_items(path=path))
    assert "unexpected extra keys" in excinfo.value.detail


def test_read_work_items_bad_enum_status_raises(tmp_path: Path) -> None:
    path = tmp_path / "work-items.jsonl"
    item = _minimal_work_item()
    append_work_item(path=path, item=item)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["status"] = "not-a-real-status"
    _ = path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    with pytest.raises(SchemaViolationError) as excinfo:
        _read_success(read_work_items(path=path))
    assert "status" in excinfo.value.detail


def test_read_work_items_bad_enum_type_raises(tmp_path: Path) -> None:
    path = tmp_path / "work-items.jsonl"
    item = _minimal_work_item()
    append_work_item(path=path, item=item)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["type"] = "not-a-real-type"
    _ = path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    with pytest.raises(SchemaViolationError) as excinfo:
        _read_success(read_work_items(path=path))
    assert "type" in excinfo.value.detail


def test_read_work_items_bad_enum_origin_raises(tmp_path: Path) -> None:
    path = tmp_path / "work-items.jsonl"
    item = _minimal_work_item()
    append_work_item(path=path, item=item)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["origin"] = "not-a-real-origin"
    _ = path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    with pytest.raises(SchemaViolationError) as excinfo:
        _read_success(read_work_items(path=path))
    assert "origin" in excinfo.value.detail


def test_read_work_items_bad_enum_resolution_raises(tmp_path: Path) -> None:
    path = tmp_path / "work-items.jsonl"
    item = _minimal_work_item(status="done", resolution="completed")
    append_work_item(path=path, item=item)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["resolution"] = "not-a-real-resolution"
    _ = path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    with pytest.raises(SchemaViolationError) as excinfo:
        _read_success(read_work_items(path=path))
    assert "resolution" in excinfo.value.detail


def test_read_work_items_audit_missing_keys_raises(tmp_path: Path) -> None:
    path = tmp_path / "work-items.jsonl"
    payload = {
        "id": "li-x",
        "type": "task",
        "status": "done",
        "title": "t",
        "description": "d",
        "origin": "freeform",
        "gap_id": None,
        "assignee": None,
        "depends_on": [],
        "captured_at": "2026-05-19T00:00:00Z",
        "resolution": "completed",
        "reason": "fixed",
        "audit": {"verification_timestamp": "2026-05-19T00:00:00Z"},
        "superseded_by": None,
    }
    _ = path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    with pytest.raises(SchemaViolationError) as excinfo:
        _read_success(read_work_items(path=path))
    assert "audit object missing keys" in excinfo.value.detail


def test_materialize_work_items_supersession_head_wins(tmp_path: Path) -> None:
    """The chain head wins even when it physically precedes the record it amends."""
    path = tmp_path / "work-items.jsonl"
    first = _minimal_work_item(id_="li-a", status="ready")
    second = _minimal_work_item(
        id_="li-a",
        status="done",
        resolution="completed",
        supersedes=work_item_record_identity(item=first),
    )
    other = _minimal_work_item(id_="li-b")
    append_work_item(path=path, item=second)
    append_work_item(path=path, item=first)
    append_work_item(path=path, item=other)
    materialized = materialize_work_items(records=iter(_read_success(read_work_items(path=path))))
    assert materialized["li-a"].status == "done"
    assert materialized["li-b"].status == "ready"


def test_append_creates_parent_directory(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "deeper" / "work-items.jsonl"
    item = _minimal_work_item()
    append_work_item(path=path, item=item)
    assert path.exists()
    assert path.parent.is_dir()


def test_append_work_item_rejects_bad_enum_status(tmp_path: Path) -> None:
    path = tmp_path / "work-items.jsonl"
    bad = _minimal_work_item(status="not-a-real-status")
    failure = _append_failure(append_work_item(path=path, item=bad))
    assert isinstance(failure, SchemaViolationError)
    assert "status" in failure.detail


def test_append_work_item_rejects_bad_enum_type(tmp_path: Path) -> None:
    path = tmp_path / "work-items.jsonl"
    item = WorkItem(
        id="li-aaa222",
        type="not-a-real-type",  # type: ignore[arg-type]
        status="ready",
        title="t",
        description="d",
        origin="freeform",
        gap_id=None,
        rank="a1",
        assignee=None,
        depends_on=(),
        captured_at="2026-05-19T00:00:00Z",
        resolution=None,
        reason=None,
        audit=None,
        superseded_by=None,
    )
    failure = _append_failure(append_work_item(path=path, item=item))
    assert isinstance(failure, SchemaViolationError)
    assert "type" in failure.detail


def test_append_work_item_rejects_bad_enum_origin(tmp_path: Path) -> None:
    path = tmp_path / "work-items.jsonl"
    item = WorkItem(
        id="li-aaa333",
        type="task",
        status="ready",
        title="t",
        description="d",
        origin="not-a-real-origin",  # type: ignore[arg-type]
        gap_id=None,
        rank="a1",
        assignee=None,
        depends_on=(),
        captured_at="2026-05-19T00:00:00Z",
        resolution=None,
        reason=None,
        audit=None,
        superseded_by=None,
    )
    failure = _append_failure(append_work_item(path=path, item=item))
    assert isinstance(failure, SchemaViolationError)
    assert "origin" in failure.detail


def test_append_work_item_rejects_bad_enum_resolution(tmp_path: Path) -> None:
    path = tmp_path / "work-items.jsonl"
    bad = _minimal_work_item(status="done", resolution="not-a-real-resolution")
    failure = _append_failure(append_work_item(path=path, item=bad))
    assert isinstance(failure, SchemaViolationError)
    assert "resolution" in failure.detail


def test_append_work_item_does_not_write_on_validation_failure(tmp_path: Path) -> None:
    path = tmp_path / "work-items.jsonl"
    bad = _minimal_work_item(status="not-a-real-status")
    failure = _append_failure(append_work_item(path=path, item=bad))
    assert isinstance(failure, SchemaViolationError)
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
        status="ready",
        title="t",
        description="d",
        origin="freeform",
        gap_id=None,
        rank="a1",
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
    [read_back] = _read_success(read_work_items(path=path))
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
        "status": "ready",
        "title": "legacy",
        "description": "from before the field landed",
        "origin": "freeform",
        "gap_id": None,
        "assignee": None,
        "depends_on": [],
        "captured_at": "2026-05-19T00:00:00Z",
        "resolution": None,
        "reason": None,
        "audit": None,
        "superseded_by": None,
    }
    _ = path.write_text(json.dumps(legacy_payload) + "\n", encoding="utf-8")
    [read_back] = _read_success(read_work_items(path=path))
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
        _read_success(read_work_items(path=path))
    assert "spec_commitment_hint" in excinfo.value.detail


def test_append_work_item_rejects_non_string_hint(tmp_path: Path) -> None:
    """The append-side validator rejects a non-string hint payload."""
    path = tmp_path / "work-items.jsonl"
    bad = WorkItem(
        id="li-badhint",
        type="task",
        status="ready",
        title="t",
        description="d",
        origin="freeform",
        gap_id=None,
        rank="a1",
        assignee=None,
        depends_on=(),
        captured_at="2026-05-19T00:00:00Z",
        resolution=None,
        reason=None,
        audit=None,
        superseded_by=None,
        spec_commitment_hint=42,  # type: ignore[arg-type]
    )
    failure = _append_failure(append_work_item(path=path, item=bad))
    assert isinstance(failure, SchemaViolationError)
    assert "spec_commitment_hint" in failure.detail


def test_read_work_item_still_rejects_unexpected_extra_keys(tmp_path: Path) -> None:
    """Extras outside required+optional union still raise (regression guard)."""
    path = tmp_path / "work-items.jsonl"
    item = _minimal_work_item()
    append_work_item(path=path, item=item)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["surprise_key"] = "value"
    _ = path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    with pytest.raises(SchemaViolationError) as excinfo:
        _read_success(read_work_items(path=path))
    assert "unexpected extra keys" in excinfo.value.detail


# -- rank field (v013 lifecycle schema; livespec-runtime v0.5.0) ---------


def test_read_legacy_work_item_without_rank_defaults_to_bottom_sentinel(tmp_path: Path) -> None:
    """A pre-v013 line lacking `rank` reads back as the bottom-sentinel.

    `rank` is optional-on-read: a legacy line authored before the ordering
    key landed materializes with `rank == BOTTOM_SENTINEL` ("~"), the
    store-adapter substitution that sorts strictly after every real key.
    """
    path = tmp_path / "work-items.jsonl"
    legacy_payload = {
        "id": "li-norank",
        "type": "task",
        "status": "ready",
        "title": "legacy",
        "description": "from before rank landed",
        "origin": "freeform",
        "gap_id": None,
        "assignee": None,
        "depends_on": [],
        "captured_at": "2026-05-19T00:00:00Z",
        "resolution": None,
        "reason": None,
        "audit": None,
        "superseded_by": None,
    }
    _ = path.write_text(json.dumps(legacy_payload) + "\n", encoding="utf-8")
    [read_back] = _read_success(read_work_items(path=path))
    assert read_back.rank == BOTTOM_SENTINEL
    assert read_back.rank == "~"


def test_read_work_item_with_rank_roundtrips(tmp_path: Path) -> None:
    """A present non-empty `rank` is taken verbatim and round-trips losslessly."""
    path = tmp_path / "work-items.jsonl"
    item = _minimal_work_item(rank="a3")
    append_work_item(path=path, item=item)
    [read_back] = _read_success(read_work_items(path=path))
    assert read_back.rank == "a3"
    assert read_back == item


def test_read_work_item_with_empty_rank_defaults_to_bottom_sentinel(tmp_path: Path) -> None:
    """A present-but-empty `rank` string is treated as absent (bottom-sentinel)."""
    path = tmp_path / "work-items.jsonl"
    append_work_item(path=path, item=_minimal_work_item())
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["rank"] = ""
    _ = path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    [read_back] = _read_success(read_work_items(path=path))
    assert read_back.rank == BOTTOM_SENTINEL


def test_read_work_item_with_priority_key_raises(tmp_path: Path) -> None:
    """`priority` was removed in v013; a line carrying it is a schema violation."""
    path = tmp_path / "work-items.jsonl"
    append_work_item(path=path, item=_minimal_work_item())
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["priority"] = 2
    _ = path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    with pytest.raises(SchemaViolationError) as excinfo:
        _read_success(read_work_items(path=path))
    assert "unexpected extra keys" in excinfo.value.detail
    assert "priority" in excinfo.value.detail


def test_read_work_item_with_non_string_rank_raises(tmp_path: Path) -> None:
    """A present non-string `rank` value fires SchemaViolationError."""
    path = tmp_path / "work-items.jsonl"
    append_work_item(path=path, item=_minimal_work_item())
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["rank"] = 7
    _ = path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    with pytest.raises(SchemaViolationError) as excinfo:
        _read_success(read_work_items(path=path))
    assert "rank" in excinfo.value.detail


def test_append_work_item_serializes_exactly_twenty_keys(tmp_path: Path) -> None:
    """The write path emits exactly the 20 schema keys — no dropped policy fields.

    The abstract WorkItem's `admission_policy` / `acceptance_policy` /
    `blocked_reason` policy fields are DROPPED on write (this JSONL
    realization does not persist them); `priority` is gone (replaced by
    `rank`). The serialized line carries the 14 required keys + `rank`
    + `spec_commitment_hint` + `supersedes` + `acceptance_criteria`
    + `notes` + `factory_safety`.
    """
    path = tmp_path / "work-items.jsonl"
    append_work_item(path=path, item=_minimal_work_item())
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert set(payload.keys()) == {
        "id",
        "type",
        "status",
        "title",
        "description",
        "origin",
        "gap_id",
        "assignee",
        "depends_on",
        "captured_at",
        "resolution",
        "reason",
        "audit",
        "superseded_by",
        "rank",
        "spec_commitment_hint",
        "supersedes",
        "acceptance_criteria",
        "notes",
        "factory_safety",
    }
    assert len(payload) == 20
    assert "priority" not in payload
    assert "admission_policy" not in payload
    assert "acceptance_policy" not in payload
    assert "blocked_reason" not in payload
    assert payload["factory_safety"] is None


# -- acceptance_criteria + notes fields (bd-gj-lxr; runtime v0.8.0) ------


def test_work_item_defaults_acceptance_criteria_and_notes_to_none() -> None:
    """WorkItem dataclass defaults both new optional fields to None."""
    item = _minimal_work_item()
    assert item.acceptance_criteria is None
    assert item.notes is None


def test_append_work_item_with_acceptance_criteria_and_notes_roundtrips(
    tmp_path: Path,
) -> None:
    """A work-item carrying acceptance_criteria + notes round-trips losslessly."""
    path = tmp_path / "work-items.jsonl"
    item = WorkItem(
        id="li-acc001",
        type="task",
        status="ready",
        title="t",
        description="d",
        origin="freeform",
        gap_id=None,
        rank="a1",
        assignee=None,
        depends_on=(),
        captured_at="2026-05-19T00:00:00Z",
        resolution=None,
        reason=None,
        audit=None,
        superseded_by=None,
        acceptance_criteria="the gate is green and the feature works",
        notes="groomed 2026-07-02; split from the epic",
    )
    append_work_item(path=path, item=item)
    [read_back] = _read_success(read_work_items(path=path))
    assert read_back == item
    assert read_back.acceptance_criteria == "the gate is green and the feature works"
    assert read_back.notes == "groomed 2026-07-02; split from the epic"


def test_append_work_item_with_factory_safety_roundtrips(tmp_path: Path) -> None:
    """A work-item carrying factory_safety persists through the JSONL store."""
    path = tmp_path / "work-items.jsonl"
    item = WorkItem(
        id="li-safe01",
        type="task",
        status="ready",
        title="t",
        description="d",
        origin="freeform",
        gap_id=None,
        rank="a1",
        assignee=None,
        depends_on=(),
        captured_at="2026-05-19T00:00:00Z",
        resolution=None,
        reason=None,
        audit=None,
        superseded_by=None,
        factory_safety="needs-host-secrets",
    )
    append_work_item(path=path, item=item)
    [read_back] = _read_success(read_work_items(path=path))
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert read_back == item
    assert read_back.factory_safety == "needs-host-secrets"
    assert payload["factory_safety"] == "needs-host-secrets"


def test_append_work_item_without_acceptance_criteria_and_notes_writes_null(
    tmp_path: Path,
) -> None:
    """Write path always serializes both fields (explicit null on omission)."""
    path = tmp_path / "work-items.jsonl"
    append_work_item(path=path, item=_minimal_work_item())
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["acceptance_criteria"] is None
    assert payload["notes"] is None


def test_read_legacy_work_item_without_acceptance_criteria_and_notes_defaults_none(
    tmp_path: Path,
) -> None:
    """Legacy records lacking the two fields read back as None (no violation)."""
    path = tmp_path / "work-items.jsonl"
    legacy_payload = {
        "id": "li-legacy2",
        "type": "task",
        "status": "ready",
        "title": "legacy",
        "description": "from before the fields landed",
        "origin": "freeform",
        "gap_id": None,
        "rank": "a1",
        "assignee": None,
        "depends_on": [],
        "captured_at": "2026-05-19T00:00:00Z",
        "resolution": None,
        "reason": None,
        "audit": None,
        "superseded_by": None,
        "spec_commitment_hint": None,
        "supersedes": None,
    }
    _ = path.write_text(json.dumps(legacy_payload) + "\n", encoding="utf-8")
    [read_back] = _read_success(read_work_items(path=path))
    assert read_back.acceptance_criteria is None
    assert read_back.notes is None


def test_read_work_item_with_non_string_acceptance_criteria_raises(
    tmp_path: Path,
) -> None:
    """A present non-string acceptance_criteria fires SchemaViolationError."""
    path = tmp_path / "work-items.jsonl"
    append_work_item(path=path, item=_minimal_work_item())
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["acceptance_criteria"] = 7
    _ = path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    with pytest.raises(SchemaViolationError) as excinfo:
        _read_success(read_work_items(path=path))
    assert "acceptance_criteria" in excinfo.value.detail


def test_read_work_item_with_non_string_notes_raises(tmp_path: Path) -> None:
    """A present non-string notes fires SchemaViolationError."""
    path = tmp_path / "work-items.jsonl"
    append_work_item(path=path, item=_minimal_work_item())
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["notes"] = ["not", "a", "string"]
    _ = path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    with pytest.raises(SchemaViolationError) as excinfo:
        _read_success(read_work_items(path=path))
    assert "notes" in excinfo.value.detail


# -- audit merge-evidence fields (li-tenpup; contracts.md "Work-items
#    JSONL record schema" -> audit.merge_sha + audit.pr_number) ----------


def _audit_payload_dict(
    *,
    merge_sha: str = "abc123",
    pr_number: int | None = 7,
) -> dict[str, Any]:
    """A complete on-disk audit sub-object including the merge-evidence keys."""
    return {
        "verification_timestamp": "2026-05-19T00:00:00Z",
        "commits": ["deadbeef"],
        "files_changed": ["a.py"],
        "merge_sha": merge_sha,
        "pr_number": pr_number,
    }


def _closed_payload_with_audit(*, audit: dict[str, Any] | None) -> dict[str, Any]:
    """A closed/completed work-item payload carrying the supplied audit object."""
    return {
        "id": "li-merge1",
        "type": "task",
        "status": "done",
        "title": "t",
        "description": "d",
        "origin": "freeform",
        "gap_id": None,
        "assignee": None,
        "depends_on": [],
        "captured_at": "2026-05-19T00:00:00Z",
        "resolution": "completed",
        "reason": "done",
        "audit": audit,
        "superseded_by": None,
        "spec_commitment_hint": None,
    }


def test_audit_record_carries_merge_sha_and_pr_number() -> None:
    """AuditRecord exposes the merge_sha and pr_number attributes."""
    audit = AuditRecord(
        verification_timestamp="2026-05-19T00:00:00Z",
        commits=("deadbeef",),
        files_changed=("a.py",),
        merge_sha="abc123",
        pr_number=7,
    )
    assert audit.merge_sha == "abc123"
    assert audit.pr_number == 7


def test_audit_record_pr_number_defaults_to_none() -> None:
    """pr_number is optional at the dataclass level and defaults to None."""
    audit = AuditRecord(
        verification_timestamp="2026-05-19T00:00:00Z",
        commits=("deadbeef",),
        files_changed=("a.py",),
        merge_sha="abc123",
    )
    assert audit.pr_number is None


def test_append_work_item_with_merge_evidence_roundtrips(tmp_path: Path) -> None:
    """A closed work-item with merge_sha + pr_number round-trips losslessly."""
    path = tmp_path / "work-items.jsonl"
    audit = AuditRecord(
        verification_timestamp="2026-05-19T01:00:00Z",
        commits=("deadbeef",),
        files_changed=("a.py",),
        merge_sha="abc123def",
        pr_number=42,
    )
    item = _minimal_work_item(
        id_="li-merge9",
        status="done",
        resolution="completed",
        audit=audit,
    )
    append_work_item(path=path, item=item)
    [read_back] = _read_success(read_work_items(path=path))
    assert read_back == item
    assert read_back.audit is not None
    assert read_back.audit.merge_sha == "abc123def"
    assert read_back.audit.pr_number == 42


def test_append_work_item_serializes_merge_evidence_keys(tmp_path: Path) -> None:
    """The write path emits merge_sha and pr_number inside the audit object."""
    path = tmp_path / "work-items.jsonl"
    audit = AuditRecord(
        verification_timestamp="2026-05-19T01:00:00Z",
        commits=("deadbeef",),
        files_changed=("a.py",),
        merge_sha="abc123def",
        pr_number=None,
    )
    item = _minimal_work_item(
        id_="li-merge8",
        status="done",
        resolution="completed",
        audit=audit,
    )
    append_work_item(path=path, item=item)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["audit"]["merge_sha"] == "abc123def"
    assert "pr_number" in payload["audit"]
    assert payload["audit"]["pr_number"] is None


def test_read_audit_missing_merge_sha_raises(tmp_path: Path) -> None:
    """An audit object lacking merge_sha fires a SchemaViolationError."""
    path = tmp_path / "work-items.jsonl"
    audit = _audit_payload_dict()
    del audit["merge_sha"]
    payload = _closed_payload_with_audit(audit=audit)
    _ = path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    with pytest.raises(SchemaViolationError) as excinfo:
        _read_success(read_work_items(path=path))
    assert "merge_sha" in excinfo.value.detail


def test_read_audit_empty_merge_sha_raises(tmp_path: Path) -> None:
    """An empty-string merge_sha violates the non-empty requirement."""
    path = tmp_path / "work-items.jsonl"
    payload = _closed_payload_with_audit(audit=_audit_payload_dict(merge_sha=""))
    _ = path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    with pytest.raises(SchemaViolationError) as excinfo:
        _read_success(read_work_items(path=path))
    assert "merge_sha" in excinfo.value.detail


def test_read_audit_non_int_pr_number_raises(tmp_path: Path) -> None:
    """A non-integer, non-null pr_number fires a SchemaViolationError."""
    path = tmp_path / "work-items.jsonl"
    audit = _audit_payload_dict()
    audit["pr_number"] = "not-an-int"
    payload = _closed_payload_with_audit(audit=audit)
    _ = path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    with pytest.raises(SchemaViolationError) as excinfo:
        _read_success(read_work_items(path=path))
    assert "pr_number" in excinfo.value.detail


def test_read_audit_with_null_pr_number_roundtrips(tmp_path: Path) -> None:
    """A null pr_number is permitted and reads back as None."""
    path = tmp_path / "work-items.jsonl"
    payload = _closed_payload_with_audit(audit=_audit_payload_dict(pr_number=None))
    _ = path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    [read_back] = _read_success(read_work_items(path=path))
    assert read_back.audit is not None
    assert read_back.audit.merge_sha == "abc123"
    assert read_back.audit.pr_number is None


def test_read_audit_without_pr_number_key_defaults_to_none(tmp_path: Path) -> None:
    """A legacy audit object omitting pr_number entirely reads back as None.

    Exercises the optional-on-read path: `pr_number` absent from the audit
    object still validates (merge_sha present and non-empty) and materializes
    with `pr_number=None`.
    """
    path = tmp_path / "work-items.jsonl"
    audit = _audit_payload_dict()
    del audit["pr_number"]
    payload = _closed_payload_with_audit(audit=audit)
    _ = path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    [read_back] = _read_success(read_work_items(path=path))
    assert read_back.audit is not None
    assert read_back.audit.merge_sha == "abc123"
    assert read_back.audit.pr_number is None


# -- supersedes field + order-independent reduction (v008 append-only-
#    store disciplines; contracts.md "Work-items JSONL record schema" ->
#    supersedes, "Materialized view", "Append-only store disciplines") --


def _sha256_identity_of(*, canonical: str) -> str:
    """The expected identity encoding: sha256 over canonical line bytes."""
    return f"sha256:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"


def test_work_item_default_supersedes_is_none() -> None:
    """WorkItem defaults the supersedes pointer to None (an original record)."""
    item = WorkItem(
        id="li-orig01",
        type="task",
        status="ready",
        title="t",
        description="d",
        origin="freeform",
        gap_id=None,
        rank="a1",
        assignee=None,
        depends_on=(),
        captured_at="2026-05-19T00:00:00Z",
        resolution=None,
        reason=None,
        audit=None,
        superseded_by=None,
    )
    assert item.supersedes is None


def test_append_work_item_writes_supersedes_null(tmp_path: Path) -> None:
    """Required-on-write: the key is serialized explicitly, null on omission."""
    path = tmp_path / "work-items.jsonl"
    append_work_item(path=path, item=_minimal_work_item())
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert "supersedes" in payload
    assert payload["supersedes"] is None


def test_append_work_item_with_supersedes_roundtrips(tmp_path: Path) -> None:
    """An amendment carrying its target's identity round-trips losslessly."""
    path = tmp_path / "work-items.jsonl"
    original = _minimal_work_item(id_="li-amend1")
    amendment = _minimal_work_item(
        id_="li-amend1",
        status="active",
        captured_at="2026-05-19T01:00:00Z",
        supersedes=work_item_record_identity(item=original),
    )
    append_work_item(path=path, item=original)
    append_work_item(path=path, item=amendment)
    read_back = _read_success(read_work_items(path=path))
    assert read_back == [original, amendment]
    assert read_back[1].supersedes == work_item_record_identity(item=original)


def test_read_legacy_work_item_without_supersedes_defaults_to_none(tmp_path: Path) -> None:
    """Optional-on-read: records authored before the field parse cleanly."""
    path = tmp_path / "work-items.jsonl"
    legacy_payload = {
        "id": "li-legacy2",
        "type": "task",
        "status": "ready",
        "title": "legacy",
        "description": "from before supersedes landed",
        "origin": "freeform",
        "gap_id": None,
        "assignee": None,
        "depends_on": [],
        "captured_at": "2026-05-19T00:00:00Z",
        "resolution": None,
        "reason": None,
        "audit": None,
        "superseded_by": None,
        "spec_commitment_hint": None,
    }
    _ = path.write_text(json.dumps(legacy_payload) + "\n", encoding="utf-8")
    [read_back] = _read_success(read_work_items(path=path))
    assert read_back.supersedes is None


def test_read_work_item_with_non_string_supersedes_raises(tmp_path: Path) -> None:
    """A non-string non-null supersedes value fires SchemaViolationError."""
    path = tmp_path / "work-items.jsonl"
    append_work_item(path=path, item=_minimal_work_item())
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["supersedes"] = 42
    _ = path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    with pytest.raises(SchemaViolationError) as excinfo:
        _read_success(read_work_items(path=path))
    assert "supersedes" in excinfo.value.detail


def test_append_work_item_rejects_non_string_supersedes(tmp_path: Path) -> None:
    """The append-side validator rejects a non-string supersedes payload."""
    path = tmp_path / "work-items.jsonl"
    bad = _minimal_work_item(supersedes=42)  # type: ignore[arg-type]
    failure = _append_failure(append_work_item(path=path, item=bad))
    assert isinstance(failure, SchemaViolationError)
    assert "supersedes" in failure.detail


def test_work_item_record_identity_is_sha256_of_canonical_serialization() -> None:
    """The fixed identity encoding: sha256 over the canonical record serialization.

    The shared identity hashes the FULL dataclass serialization (every
    field explicit, sorted keys, compact separators) — including the
    abstract WorkItem's `admission_policy` / `acceptance_policy` /
    `blocked_reason` policy fields, which this JSONL realization does NOT
    persist on the line. So the identity is a pure function of record
    content, independent of which keys the on-disk line happens to carry.
    """
    item = _minimal_work_item()
    payload = asdict(item)
    payload["depends_on"] = list(item.depends_on)
    canonical = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    assert work_item_record_identity(item=item) == _sha256_identity_of(canonical=canonical)


def test_work_item_record_identity_normalizes_legacy_records(tmp_path: Path) -> None:
    """A legacy record's identity matches an explicit-defaults record.

    Records on disk that pre-date the optional keys (`rank`,
    `spec_commitment_hint`, `supersedes`) read back with
    `rank == BOTTOM_SENTINEL` and the other optional fields `None`, so
    identity stays a pure function of record content regardless of which
    schema era serialized the line.
    """
    path = tmp_path / "work-items.jsonl"
    legacy_payload = {
        "id": "li-legacy3",
        "type": "task",
        "status": "ready",
        "title": "legacy",
        "description": "pre-optional-keys record",
        "origin": "freeform",
        "gap_id": None,
        "assignee": None,
        "depends_on": [],
        "captured_at": "2026-05-19T00:00:00Z",
        "resolution": None,
        "reason": None,
        "audit": None,
        "superseded_by": None,
    }
    _ = path.write_text(json.dumps(legacy_payload) + "\n", encoding="utf-8")
    [read_back] = _read_success(read_work_items(path=path))
    assert read_back.rank == BOTTOM_SENTINEL
    explicit = WorkItem(
        id="li-legacy3",
        type="task",
        status="ready",
        title="legacy",
        description="pre-optional-keys record",
        origin="freeform",
        gap_id=None,
        rank=BOTTOM_SENTINEL,
        assignee=None,
        depends_on=(),
        captured_at="2026-05-19T00:00:00Z",
        resolution=None,
        reason=None,
        audit=None,
        superseded_by=None,
    )
    assert work_item_record_identity(item=read_back) == work_item_record_identity(item=explicit)


def test_record_identity_covers_the_supersedes_pointer() -> None:
    """Records differing only in supersedes have distinct identities.

    The pointer participates in the hashed content, so supersession
    chains are hash chains — an amendment cannot be confused with the
    original it amends.
    """
    base = _minimal_work_item(id_="li-chain1")
    amendment = _minimal_work_item(
        id_="li-chain1",
        supersedes=work_item_record_identity(item=base),
    )
    assert work_item_record_identity(item=base) != work_item_record_identity(item=amendment)


def test_materialize_work_items_is_order_independent(tmp_path: Path) -> None:
    """The chain head wins under every physical record permutation.

    All three records share captured_at, so only the supersedes
    pointers — never file order, never the tie-break — determine the
    head. This retires the DEPRECATED "latest record by file order
    wins" reduction.
    """
    a = _minimal_work_item(id_="li-chain2", status="ready")
    b = _minimal_work_item(
        id_="li-chain2",
        status="active",
        supersedes=work_item_record_identity(item=a),
    )
    c = _minimal_work_item(
        id_="li-chain2",
        status="blocked",
        supersedes=work_item_record_identity(item=b),
    )
    for index, ordering in enumerate(permutations((a, b, c))):
        path = tmp_path / f"work-items-{index}.jsonl"
        for record in ordering:
            append_work_item(path=path, item=record)
        materialized = materialize_work_items(
            records=iter(_read_success(read_work_items(path=path)))
        )
        assert materialized == {"li-chain2": c}


def test_materialize_work_items_divergence_tie_breaks_on_captured_at(tmp_path: Path) -> None:
    """Divergent heads materialize to the latest-captured record."""
    earlier = _minimal_work_item(id_="li-div1", status="ready")
    later = _minimal_work_item(
        id_="li-div1",
        status="active",
        captured_at="2026-05-19T02:00:00Z",
    )
    for index, ordering in enumerate(permutations((earlier, later))):
        path = tmp_path / f"work-items-{index}.jsonl"
        for record in ordering:
            append_work_item(path=path, item=record)
        assert materialize_work_items(records=iter(_read_success(read_work_items(path=path)))) == {
            "li-div1": later
        }


def test_materialize_work_items_divergence_tie_breaks_on_identity(tmp_path: Path) -> None:
    """Equal captured_at falls through to the per-record identity tie-break."""
    one = _minimal_work_item(id_="li-div2", status="ready")
    two = _minimal_work_item(id_="li-div2", status="active")
    ranked = sorted((work_item_record_identity(item=record), record) for record in (one, two))
    expected = ranked[-1][1]
    for index, ordering in enumerate(permutations((one, two))):
        path = tmp_path / f"work-items-{index}.jsonl"
        for record in ordering:
            append_work_item(path=path, item=record)
        assert materialize_work_items(records=iter(_read_success(read_work_items(path=path)))) == {
            "li-div2": expected
        }


def test_reduce_work_item_heads_surfaces_divergence(tmp_path: Path) -> None:
    """Concurrent divergence is detectable: every un-superseded head is returned.

    Two amendments of one base record (neither superseding the other)
    both surface, in tie-break order; the superseded base does not. A
    chain-free entity reduces to its single head.
    """
    path = tmp_path / "work-items.jsonl"
    base = _minimal_work_item(id_="li-div3", status="ready")
    left = _minimal_work_item(
        id_="li-div3",
        status="active",
        captured_at="2026-05-19T01:00:00Z",
        supersedes=work_item_record_identity(item=base),
    )
    right = _minimal_work_item(
        id_="li-div3",
        status="blocked",
        captured_at="2026-05-19T02:00:00Z",
        supersedes=work_item_record_identity(item=base),
    )
    single = _minimal_work_item(id_="li-sing1")
    for record in (base, left, right, single):
        append_work_item(path=path, item=record)
    heads = reduce_work_item_heads(records=iter(_read_success(read_work_items(path=path))))
    assert heads == {"li-div3": (left, right), "li-sing1": (single,)}


def test_reduce_work_item_heads_collapses_identical_lines(tmp_path: Path) -> None:
    """A line duplicated by a merge=union merge collapses to one head.

    Identical records share an identity, so the reduction dedupes them
    instead of reporting false divergence.
    """
    path = tmp_path / "work-items.jsonl"
    item = _minimal_work_item(id_="li-dup1")
    append_work_item(path=path, item=item)
    line = path.read_text(encoding="utf-8")
    _ = path.write_text(line + line, encoding="utf-8")
    heads = reduce_work_item_heads(records=iter(_read_success(read_work_items(path=path))))
    assert heads == {"li-dup1": (item,)}


# -- JsonlWorkItemStore facade (W7 livespec-5g4i; tracks its temporary
#    divergence from livespec_runtime.work_items.store.WorkItemStore) -----


def test_jsonl_store_tracks_work_item_store_protocol_divergence() -> None:
    """The facade's temporary protocol divergence is explicit and tracked.

    The vendored WorkItemStore Protocol still exposes unwrapped
    Iterator/None methods, while the local facade deliberately remains on
    the IOResult railway until `livespec-shz8` updates the upstream
    protocol. This guard fails when either side changes so the marker is
    removed or reconciled instead of silently forgotten.
    """
    assert WORK_ITEM_STORE_PROTOCOL_DIVERGENCE_DEPENDS_ON == "livespec-shz8"
    protocol_read = get_type_hints(WorkItemStore.read_work_items)["return"]
    protocol_append = get_type_hints(WorkItemStore.append_work_item)["return"]
    facade_read = get_type_hints(JsonlWorkItemStore.read_work_items)["return"]
    facade_append = get_type_hints(JsonlWorkItemStore.append_work_item)["return"]
    assert protocol_read == Iterator[WorkItem]
    assert protocol_append is type(None)
    assert facade_read == IOResult[list[WorkItem], Exception]
    assert facade_append == IOResult[None, Exception]
    assert inspect.signature(JsonlWorkItemStore.append_work_item).parameters["item"].kind is (
        inspect.Parameter.KEYWORD_ONLY
    )


def test_jsonl_store_append_then_read_round_trips(tmp_path: Path) -> None:
    """A record appended through the facade reads back identically."""
    store = JsonlWorkItemStore(path=tmp_path / "work-items.jsonl")
    item = _minimal_work_item(id_="li-facade1")
    store.append_work_item(item=item)
    assert _read_success(store.read_work_items()) == [item]


def test_jsonl_store_reads_records_written_by_free_function(tmp_path: Path) -> None:
    """The facade reads over the same backing file as the free functions.

    A record appended via the module-level `append_work_item` is visible
    through the facade's `read_work_items`, proving the facade binds the
    JSONL path through to the local backend rather than a private store.
    """
    path = tmp_path / "work-items.jsonl"
    item = _minimal_work_item(id_="li-facade2")
    append_work_item(path=path, item=item)
    store = JsonlWorkItemStore(path=path)
    assert _read_success(store.read_work_items()) == [item]


def test_jsonl_store_read_missing_file_returns_failure(tmp_path: Path) -> None:
    """The facade returns the local backend's StoreFileMissingError on the failure track."""
    path = tmp_path / "missing.jsonl"
    store = JsonlWorkItemStore(path=path)
    with pytest.raises(StoreFileMissingError) as excinfo:
        _read_success(store.read_work_items())
    assert excinfo.value.path == path


def test_jsonl_store_append_runs_local_validators(tmp_path: Path) -> None:
    """The facade append goes through the local JSONL-schema validators.

    A bad-enum payload fired through the facade returns the same
    SchemaViolationError the free-function append path returns, confirming
    the facade does not bypass the validation boundary.
    """
    store = JsonlWorkItemStore(path=tmp_path / "work-items.jsonl")
    bad = _minimal_work_item(status="not-a-real-status")
    failure = _append_failure(store.append_work_item(item=bad))
    assert isinstance(failure, SchemaViolationError)
    assert "status" in failure.detail

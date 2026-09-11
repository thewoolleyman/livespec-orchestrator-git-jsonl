"""Integration-tier exercises for SPECIFICATION/scenarios.md.

Each test drives a scenario end to end across more than one shipped
module — the JSONL store, the `next` ranker, `list-work-items`,
`detect-impl-gaps`, and the append-only materialized-view reduction —
rather than a single unit under test. The node ids live under
`tests.integration.` so the heading-coverage scenario-tier direction
resolves them as integration-tier-or-above.
"""

import json
from pathlib import Path

import pytest
from livespec_orchestrator_git_jsonl.commands.detect_impl_gaps import main as detect_main
from livespec_orchestrator_git_jsonl.commands.list_work_items import main as list_main
from livespec_orchestrator_git_jsonl.commands.next import main as next_main
from livespec_orchestrator_git_jsonl.store import (
    append_work_item,
    materialize_work_items,
    read_work_items,
    work_item_record_identity,
)
from livespec_orchestrator_git_jsonl.types import AuditRecord, WorkItem
from returns.unsafe import unsafe_perform_io


def _ready_item(*, id_: str, origin: str = "freeform", gap_id: str | None = None) -> WorkItem:
    return WorkItem(
        id=id_,
        type="task",
        status="ready",  # type: ignore[arg-type]
        title=f"{id_} title",
        description=f"{id_} description",
        origin=origin,  # type: ignore[arg-type]
        gap_id=gap_id,
        rank="a1",
        assignee=None,
        depends_on=(),
        captured_at="2026-05-19T00:00:00Z",
        resolution=None,
        reason=None,
        audit=None,
        superseded_by=None,
    )


def _done_amendment(*, prior: WorkItem, resolution: str, audit: AuditRecord | None) -> WorkItem:
    return WorkItem(
        id=prior.id,
        type=prior.type,
        status="done",  # type: ignore[arg-type]
        title=prior.title,
        description=prior.description,
        origin=prior.origin,
        gap_id=prior.gap_id,
        rank=prior.rank,
        assignee=None,
        depends_on=(),
        captured_at="2026-05-19T02:00:00Z",
        resolution=resolution,  # type: ignore[arg-type]
        reason="verified and merged",
        audit=audit,
        superseded_by=None,
        supersedes=work_item_record_identity(item=prior),
    )


def _read(*, path: Path) -> list[WorkItem]:
    return unsafe_perform_io(read_work_items(path=path).unwrap())


def test_scenario_1_gap_tied_fix_cycle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Scenario 1: a gap-tied item is filed, ranked by next, then closed.

    File a gap-tied ready record, confirm `next` surfaces it as the
    implement recommendation, then append the completed closing record
    with an audit and confirm `next` no longer ranks it.
    """
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "work-items.jsonl"
    gap_item = _ready_item(id_="li-gap001", origin="gap-tied", gap_id="gap-abc")
    append_work_item(path=path, item=gap_item)

    rc = next_main(argv=["--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert [c["work_item_ref"] for c in payload["candidates"]] == ["li-gap001"]
    assert payload["candidates"][0]["action"] == "implement"

    audit = AuditRecord(
        verification_timestamp="2026-05-19T02:00:00Z",
        commits=("c0ffee",),
        files_changed=("f.py",),
        merge_sha="deadbeef",
        pr_number=7,
    )
    append_work_item(
        path=path, item=_done_amendment(prior=gap_item, resolution="completed", audit=audit)
    )

    rc = next_main(argv=["--json"])
    closed_payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert closed_payload["candidates"] == []


def test_scenario_2_freeform_bug_fix(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Scenario 2: a freeform item is filed, ranked, then closed via the freeform path.

    The freeform closing record carries `resolution: completed` and a
    reason and NO gap re-detection; `list-work-items --filter closed`
    then surfaces it.
    """
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "work-items.jsonl"
    bug = _ready_item(id_="li-bug001")
    append_work_item(path=path, item=bug)

    rc = next_main(argv=["--json"])
    ranked = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert [c["work_item_ref"] for c in ranked["candidates"]] == ["li-bug001"]

    audit = AuditRecord(
        verification_timestamp="2026-05-19T02:00:00Z",
        commits=("abc123",),
        files_changed=("g.py",),
        merge_sha="feedface",
        pr_number=None,
    )
    append_work_item(
        path=path, item=_done_amendment(prior=bug, resolution="completed", audit=audit)
    )

    rc = list_main(argv=["--filter", "closed", "--json"])
    closed = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert [row["id"] for row in closed] == ["li-bug001"]
    assert closed[0]["status"] == "done"


def test_scenario_3_doctor_cross_boundary_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Scenario 3: doctor's cross-boundary queries return the contract JSON shapes.

    Doctor invokes `list-work-items --json` and `detect-impl-gaps --json`.
    Both MUST complete deterministically with the contract-mandated
    schemas — an array of materialized views, and a `{gap_ids: [...]}`
    object.
    """
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "work-items.jsonl"
    append_work_item(path=path, item=_ready_item(id_="li-doc001"))
    spec = tmp_path / "SPECIFICATION"
    (spec / "history" / "v001").mkdir(parents=True)
    (spec / "spec.md").write_text("# T\n\nEverything MUST be deterministic.\n", encoding="utf-8")

    rc = list_main(argv=["--json"])
    items_payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert isinstance(items_payload, list)
    assert [row["id"] for row in items_payload] == ["li-doc001"]

    rc = detect_main(argv=["--json"])
    gaps_payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert list(gaps_payload.keys()) == ["gap_ids"]
    assert gaps_payload["gap_ids"][0].startswith("gap-")


def test_scenario_4_cross_repo_layer_3_empty_queue_signal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Scenario 4: the impl-side `next` emits the empty-queue no-work signal.

    The Layer 3 driver composes this plugin's `next` with the spec-side
    `next`; when no work is ready this plugin MUST emit an empty
    `candidates[]` with `has_more: false`, never a legacy single-object
    shape.
    """
    monkeypatch.chdir(tmp_path)
    rc = next_main(argv=["--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["candidates"] == []
    assert payload["pagination"]["has_more"] is False


def test_scenario_5_ledger_intent_scan_is_read_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Scenario 5: the ledger-intent scan reads through the reduction, never mutates.

    capture-spec-drift's ledger-intent scan reads recent work-items
    through the append-only materialized-view reduction. This exercises
    that read path — materializing the head from the store — and asserts
    the store file bytes are unchanged by the read (the scan never writes
    work-item state).
    """
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "work-items.jsonl"
    original = _ready_item(id_="li-intent01")
    append_work_item(path=path, item=original)
    amended = WorkItem(
        id=original.id,
        type=original.type,
        status="active",  # type: ignore[arg-type]
        title=original.title,
        description="encodes a behavior not yet reflected in the spec",
        origin=original.origin,
        gap_id=original.gap_id,
        rank=original.rank,
        assignee=None,
        depends_on=(),
        captured_at="2026-05-19T03:00:00Z",
        resolution=None,
        reason=None,
        audit=None,
        superseded_by=None,
        supersedes=work_item_record_identity(item=original),
    )
    append_work_item(path=path, item=amended)

    before = path.read_bytes()
    materialized = materialize_work_items(records=iter(_read(path=path)))
    after = path.read_bytes()

    assert after == before
    head = materialized["li-intent01"]
    assert head.status == "active"
    assert head.description == "encodes a behavior not yet reflected in the spec"

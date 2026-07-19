"""Compatibility tests for store_schema public wrappers."""

from pathlib import Path

from livespec_orchestrator_git_jsonl.store_codec import work_item_to_dict
from livespec_orchestrator_git_jsonl.store_schema import parse_work_item
from livespec_orchestrator_git_jsonl.types import WorkItem
from returns.result import Success


def _item() -> WorkItem:
    return WorkItem(
        id="li-wrap1",
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


def test_store_schema_parse_work_item_wrapper(tmp_path: Path) -> None:
    item = _item()
    payload = work_item_to_dict(item=item)

    parsed = parse_work_item(path=tmp_path / "work-items.jsonl", line_number=1, parsed=payload)

    assert isinstance(parsed, Success)
    assert parsed.unwrap() == item


def test_store_schema_work_item_to_dict_wrapper() -> None:
    from livespec_orchestrator_git_jsonl.store_schema import work_item_to_dict as serialize

    payload = serialize(item=_item())

    assert payload["id"] == "li-wrap1"

"""Additional handoff coverage for needs-attention."""

from pathlib import Path

from livespec_orchestrator_git_jsonl.commands.needs_attention import build_attention
from livespec_orchestrator_git_jsonl.store import append_work_item
from livespec_orchestrator_git_jsonl.types import WorkItem


def _item(*, id_: str, status: str, rank: str) -> WorkItem:
    return WorkItem(
        id=id_,
        type="task",
        status=status,  # type: ignore[arg-type]
        title=f"{id_} title",
        description="d",
        origin="freeform",
        gap_id=None,
        rank=rank,
        assignee=None,
        depends_on=(),
        captured_at="2026-05-19T00:00:00Z",
        resolution=None,
        reason=None,
        audit=None,
        superseded_by=None,
    )


def test_handoff_commands_omit_work_items_path_when_using_default_store(tmp_path: Path) -> None:
    append_work_item(
        path=tmp_path / "work-items.jsonl",
        item=_item(id_="gj-approval", status="pending-approval", rank="a2"),
    )
    append_work_item(
        path=tmp_path / "work-items.jsonl",
        item=_item(id_="gj-ready", status="ready", rank="a1"),
    )

    attention = build_attention(project_root=tmp_path, repo_name="repo", include_hygiene=False)

    commands = [item.handoff.command for item in attention]
    assert all("--work-items-path" not in command for command in commands)
    assert any("livespec-orchestrator-git-jsonl:list-work-items" in command for command in commands)
    assert any("livespec-orchestrator-git-jsonl:next" in command for command in commands)

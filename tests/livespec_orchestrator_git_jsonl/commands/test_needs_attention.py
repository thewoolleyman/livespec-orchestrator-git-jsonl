"""Tests for the needs-attention thin binding."""

import json
from pathlib import Path

import pytest
from livespec_orchestrator_git_jsonl.commands.needs_attention import (
    build_attention,
    main,
    render_json,
    render_markdown,
)
from livespec_orchestrator_git_jsonl.store import append_work_item
from livespec_orchestrator_git_jsonl.types import WorkItem


def _item(
    *,
    id_: str,
    status: str,
    rank: str = "a2",
    blocked_reason: str | None = None,
) -> WorkItem:
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
        blocked_reason=blocked_reason,  # type: ignore[arg-type]
    )


def test_build_attention_composes_available_git_jsonl_primitives(tmp_path: Path) -> None:
    path = tmp_path / "work-items.jsonl"
    append_work_item(path=path, item=_item(id_="gj-ready", status="ready", rank="a1"))
    append_work_item(path=path, item=_item(id_="gj-approval", status="pending-approval"))
    append_work_item(path=path, item=_item(id_="gj-accept", status="acceptance", rank="a3"))
    append_work_item(
        path=path,
        item=_item(id_="gj-block", status="blocked", rank="a4", blocked_reason="needs-human"),
    )

    attention = build_attention(
        project_root=tmp_path,
        repo_name="repo",
        work_items_path=str(path),
        include_hygiene=False,
    )

    assert [item.id for item in attention] == [
        "valve:approve:gj-approval",
        "valve:accept:gj-accept",
        "valve:set-admission:gj-block",
        "impl:gj-ready",
        "spec:next:SPECIFICATION",
    ]
    assert {item.kind for item in attention} == {"human-valve", "impl", "spec"}
    assert "plan:needs-attention" not in [item.id for item in attention]
    assert attention[0].handoff.action_id == "approve:gj-approval"
    assert "list-work-items" in attention[0].handoff.command
    assert "next" in attention[3].handoff.command


def test_render_json_wraps_flat_attention_array(tmp_path: Path) -> None:
    attention = build_attention(project_root=tmp_path, repo_name="repo", include_hygiene=False)

    payload = json.loads(render_json(attention=attention))

    assert list(payload) == ["attention"]
    assert payload["attention"][0]["id"] == "spec:next:SPECIFICATION"


def test_render_markdown_lists_handoff_commands(tmp_path: Path) -> None:
    attention = build_attention(project_root=tmp_path, repo_name="repo", include_hygiene=False)

    rendered = render_markdown(attention=attention)

    assert rendered.startswith("# Needs Attention\n")
    assert "`spec:next:SPECIFICATION`" in rendered
    assert "codex exec livespec:next" in rendered


def test_render_markdown_empty_attention() -> None:
    assert render_markdown(attention=[]) == "No attention items.\n"


def test_main_json_output(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = main(
        argv=["--json", "--skip-hygiene", "--project-root", str(tmp_path), "--repo-name", "repo"]
    )

    captured = capsys.readouterr()
    assert rc == 0
    assert json.loads(captured.out)["attention"][0]["id"] == "spec:next:SPECIFICATION"


def test_main_markdown_output(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = main(argv=["--skip-hygiene", "--project-root", str(tmp_path), "--repo-name", "repo"])

    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out.startswith("# Needs Attention\n")

"""Impl-next and human-valve lanes for needs-attention."""

import shlex
from pathlib import Path

from livespec_runtime.attention_item import AttentionItem, Handoff, SourceRef
from livespec_runtime.cross_repo.types import CrossRepoManifest
from livespec_runtime.needs_attention import ImplNextOutput, WorkItemHumanValveLane
from livespec_runtime.work_items.lifecycle import lane_of

from livespec_orchestrator_git_jsonl.commands.next import rank_candidates
from livespec_orchestrator_git_jsonl.types import WorkItem

__all__: list[str] = ["host_only_items", "human_valves", "impl_next"]

_PLUGIN_NAME = "livespec-orchestrator-git-jsonl"


def impl_next(
    *,
    project_root: Path,
    work_items_path: str | None,
    items: list[WorkItem],
    manifest: CrossRepoManifest,
) -> ImplNextOutput | None:
    ranked = rank_candidates(items=items, manifest=manifest)
    if not ranked:
        return None
    candidate = ranked[0]
    work_item = str(candidate["work_item_ref"])
    return ImplNextOutput(
        work_item=work_item,
        summary=str(candidate["reason"]),
        command=_next_command(project_root=project_root, work_items_path=work_items_path),
        urgency="medium",
    )


def host_only_items(
    *,
    repo_name: str,
    project_root: Path,
    work_items_path: str | None,
    items: list[WorkItem],
) -> list[AttentionItem]:
    return [
        AttentionItem(
            id=f"host-only:{item.factory_safety}:{item.id}",
            kind="host-only",
            urgency="high",
            summary=f"Host-only work-item {item.id}: {item.title}",
            source_ref=SourceRef(repo=repo_name, work_item=item.id),
            handoff=Handoff(
                kind="shell",
                command=_list_work_items_command(
                    project_root=project_root,
                    work_items_path=work_items_path,
                ),
            ),
        )
        for item in items
        if item.factory_safety is not None
    ]


def human_valves(
    *,
    project_root: Path,
    work_items_path: str | None,
    items: list[WorkItem],
    index: dict[str, WorkItem],
    manifest: CrossRepoManifest,
) -> list[WorkItemHumanValveLane]:
    lanes: list[WorkItemHumanValveLane] = []
    for item in items:
        lane_reason = lane_of(item=item, index=index, manifest=manifest).reason
        if item.status == "pending-approval":
            lanes.append(
                _valve(
                    verb="approve",
                    work_item=item.id,
                    summary=f"Approve pending work-item {item.id}: {item.title}",
                    project_root=project_root,
                    work_items_path=work_items_path,
                )
            )
        elif item.status == "acceptance":
            lanes.append(
                _valve(
                    verb="accept",
                    work_item=item.id,
                    summary=f"Accept completed work-item {item.id}: {item.title}",
                    project_root=project_root,
                    work_items_path=work_items_path,
                )
            )
        elif item.status == "blocked" and lane_reason in ("needs-human", None):
            lanes.append(
                _valve(
                    verb="set-admission",
                    work_item=item.id,
                    summary=f"Resolve human-needed block for work-item {item.id}: {item.title}",
                    project_root=project_root,
                    work_items_path=work_items_path,
                )
            )
    return lanes


def _valve(
    *,
    verb: str,
    work_item: str,
    summary: str,
    project_root: Path,
    work_items_path: str | None,
) -> WorkItemHumanValveLane:
    action_id = f"{verb}:{work_item}"
    return WorkItemHumanValveLane(
        verb=verb,
        work_item=work_item,
        summary=summary,
        action_id=action_id,
        command=_list_work_items_command(
            project_root=project_root, work_items_path=work_items_path
        ),
    )


def _next_command(*, project_root: Path, work_items_path: str | None) -> str:
    parts = [
        "codex",
        "exec",
        f"{_PLUGIN_NAME}:next",
        "--project-root",
        _quote(path=project_root),
        "--limit",
        "1",
        "--json",
    ]
    if work_items_path is not None:
        parts.extend(["--work-items-path", shlex.quote(work_items_path)])
    return " ".join(parts)


def _list_work_items_command(*, project_root: Path, work_items_path: str | None) -> str:
    parts = [
        "codex",
        "exec",
        f"{_PLUGIN_NAME}:list-work-items",
        "--project-root",
        _quote(path=project_root),
        "--json",
    ]
    if work_items_path is not None:
        parts.extend(["--work-items-path", shlex.quote(work_items_path)])
    return " ".join(parts)


def _quote(*, path: Path) -> str:
    return shlex.quote(str(path))

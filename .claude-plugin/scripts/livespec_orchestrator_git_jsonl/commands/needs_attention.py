"""Thin needs-attention binding over this plugin's gather primitives."""

from __future__ import annotations

import argparse
import contextlib
import json
import shlex
import sys
from dataclasses import asdict
from pathlib import Path

from livespec_runtime.attention_item import AttentionItem
from livespec_runtime.cross_repo.types import CrossRepoManifest
from livespec_runtime.hygiene_scan import scan_hygiene
from livespec_runtime.needs_attention import (
    ImplNextOutput,
    SpecNextOutput,
    WorkItemHumanValveLane,
    compose_needs_attention,
)
from livespec_runtime.work_items.lifecycle import lane_of

from livespec_orchestrator_git_jsonl.commands._config import resolve_store_config
from livespec_orchestrator_git_jsonl.commands._cross_repo import load_manifest
from livespec_orchestrator_git_jsonl.commands.next import rank_candidates
from livespec_orchestrator_git_jsonl.errors import StoreFileMissingError
from livespec_orchestrator_git_jsonl.store import materialize_work_items, read_work_items
from livespec_orchestrator_git_jsonl.types import WorkItem

__all__: list[str] = [
    "build_attention",
    "main",
    "render_json",
    "render_markdown",
]

_PLUGIN_NAME = "livespec-orchestrator-git-jsonl"


def main(*, argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="needs-attention")
    _ = parser.add_argument("--json", dest="as_json", action="store_true")
    _ = parser.add_argument("--project-root", dest="project_root", default=None)
    _ = parser.add_argument("--work-items-path", dest="work_items_path", default=None)
    _ = parser.add_argument("--repo-name", dest="repo_name", default=None)
    _ = parser.add_argument("--skip-hygiene", dest="skip_hygiene", action="store_true")
    args = parser.parse_args(argv)
    project_root = Path(args.project_root) if args.project_root is not None else Path.cwd()
    repo_name = args.repo_name if args.repo_name is not None else project_root.name
    attention = build_attention(
        project_root=project_root,
        repo_name=repo_name,
        work_items_path=args.work_items_path,
        include_hygiene=not args.skip_hygiene,
    )
    if args.as_json:
        _ = sys.stdout.write(render_json(attention=attention))
    else:
        _ = sys.stdout.write(render_markdown(attention=attention))
    return 0


def build_attention(
    *,
    project_root: Path,
    repo_name: str,
    work_items_path: str | None = None,
    include_hygiene: bool = True,
) -> list[AttentionItem]:
    materialized = _load_materialized(project_root=project_root, work_items_path=work_items_path)
    manifest = load_manifest(project_root=project_root)
    index = {item.id: item for item in materialized}
    hygiene_scan = (
        scan_hygiene(repo_path=project_root, repo_name=repo_name) if include_hygiene else []
    )
    return (
        compose_needs_attention(
            repo=repo_name,
            spec_next=_spec_next(project_root=project_root),
            impl_next=_impl_next(
                project_root=project_root,
                work_items_path=work_items_path,
                items=materialized,
                manifest=manifest,
            ),
            human_valve_lanes=_human_valves(
                project_root=project_root,
                work_items_path=work_items_path,
                items=materialized,
                index=index,
                manifest=manifest,
            ),
        )
        + hygiene_scan
    )


def render_json(*, attention: list[AttentionItem]) -> str:
    return (
        json.dumps({"attention": [asdict(item) for item in attention]}, indent=2, sort_keys=True)
        + "\n"
    )


def render_markdown(*, attention: list[AttentionItem]) -> str:
    if not attention:
        return "No attention items.\n"
    lines = ["# Needs Attention", ""]
    for item in attention:
        lines.extend(
            [
                f"- `{item.id}` [{item.urgency}] {item.summary}",
                f"  - Handoff: `{item.handoff.command}`",
            ]
        )
    return "\n".join(lines) + "\n"


def _load_materialized(*, project_root: Path, work_items_path: str | None) -> list[WorkItem]:
    config = resolve_store_config(cwd=project_root, work_items_arg=work_items_path)
    materialized: list[WorkItem] = []
    with contextlib.suppress(StoreFileMissingError):
        materialized = list(
            materialize_work_items(records=read_work_items(path=config.work_items_path)).values()
        )
    return materialized


def _spec_next(*, project_root: Path) -> SpecNextOutput:
    command = f"codex exec livespec:next --json --project-root {_quote(path=project_root)}"
    return SpecNextOutput(
        op="next",
        spec_target="SPECIFICATION",
        summary="Run the spec-side next primitive.",
        command=command,
    )


def _impl_next(
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


def _human_valves(
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

"""Thin needs-attention binding over this plugin's gather primitives."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from livespec_runtime.attention_item import AttentionItem
from livespec_runtime.hygiene_scan import scan_hygiene
from livespec_runtime.needs_attention import (
    compose_needs_attention,
)
from returns.io import IOSuccess
from returns.unsafe import unsafe_perform_io

from livespec_orchestrator_git_jsonl.commands._config import resolve_store_config
from livespec_orchestrator_git_jsonl.commands._cross_repo import load_manifest
from livespec_orchestrator_git_jsonl.commands.attention_impl import (
    human_valves as _human_valves,
)
from livespec_orchestrator_git_jsonl.commands.attention_impl import (
    impl_next as _impl_next,
)
from livespec_orchestrator_git_jsonl.commands.attention_impl import (
    not_factory_safe_items as _not_factory_safe_items,
)
from livespec_orchestrator_git_jsonl.commands.spec_next_bridge import (
    CoreRootBases,
    SpecNextSeam,
)
from livespec_orchestrator_git_jsonl.commands.spec_next_bridge import (
    SpecNextResult as _SpecNextResult,
)
from livespec_orchestrator_git_jsonl.commands.spec_next_bridge import (
    adapt_top_candidate as _adapt_top_candidate,
)
from livespec_orchestrator_git_jsonl.commands.spec_next_bridge import (
    as_str_argv as _as_str_argv,
)
from livespec_orchestrator_git_jsonl.commands.spec_next_bridge import (
    candidate_urgency as _candidate_urgency,
)
from livespec_orchestrator_git_jsonl.commands.spec_next_bridge import (
    claude_installed_core_roots as _claude_installed_core_roots,
)
from livespec_orchestrator_git_jsonl.commands.spec_next_bridge import (
    codex_installed_core_roots as _codex_installed_core_roots,
)
from livespec_orchestrator_git_jsonl.commands.spec_next_bridge import (
    read_spec_clis_next_argv as _read_spec_clis_next_argv,
)
from livespec_orchestrator_git_jsonl.commands.spec_next_bridge import (
    resolve_core_plugin_root as _resolve_core_plugin_root,
)
from livespec_orchestrator_git_jsonl.commands.spec_next_bridge import (
    resolve_spec_next_command as _resolve_spec_next_command,
)
from livespec_orchestrator_git_jsonl.commands.spec_next_bridge import (
    spec_next as _spec_next,
)
from livespec_orchestrator_git_jsonl.commands.spec_next_bridge import (
    spec_output_from_candidate as _spec_output_from_candidate,
)
from livespec_orchestrator_git_jsonl.errors import StoreFileMissingError
from livespec_orchestrator_git_jsonl.store import materialize_work_items, read_work_items
from livespec_orchestrator_git_jsonl.types import WorkItem

__all__: list[str] = [
    "CoreRootBases",
    "SpecNextSeam",
    "_SpecNextResult",
    "_adapt_top_candidate",
    "_as_str_argv",
    "_candidate_urgency",
    "_claude_installed_core_roots",
    "_codex_installed_core_roots",
    "_read_spec_clis_next_argv",
    "_resolve_core_plugin_root",
    "_resolve_spec_next_command",
    "_spec_next",
    "_spec_output_from_candidate",
    "build_attention",
    "main",
    "render_json",
    "render_markdown",
]


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
        + _not_factory_safe_items(
            repo=repo_name,
            project_root=project_root,
            work_items_path=work_items_path,
            items=materialized,
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
    records_result = read_work_items(path=config.work_items_path)
    if isinstance(records_result, IOSuccess):
        records = unsafe_perform_io(records_result.unwrap())
        return list(materialize_work_items(records=iter(records)).values())
    if isinstance(unsafe_perform_io(records_result.failure()), StoreFileMissingError):
        return []
    raise unsafe_perform_io(records_result.failure())

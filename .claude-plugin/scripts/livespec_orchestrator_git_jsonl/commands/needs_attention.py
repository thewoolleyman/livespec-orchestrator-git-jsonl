"""Thin needs-attention binding over this plugin's gather primitives."""

from __future__ import annotations

import argparse
import contextlib
import json
import shlex
import subprocess
import sys
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol, cast

from livespec_runtime.attention_item import AttentionItem, AttentionUrgency
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
from livespec_orchestrator_git_jsonl.io._jsonc import loads_optional as loads_jsonc_optional
from livespec_orchestrator_git_jsonl.io.spec_next import (
    load_json_file_optional,
    loads_json_optional,
    run_capture,
)
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


_LIVESPEC_CONFIG = ".livespec.jsonc"
_PLUGIN_ROOT_PLACEHOLDER = "${CLAUDE_PLUGIN_ROOT}"
_DEFAULT_SPEC_NEXT_ARGV: tuple[str, ...] = (
    "python3",
    f"{_PLUGIN_ROOT_PLACEHOLDER}/scripts/bin/next.py",
)
_CORE_SPEC_NEXT_REL: tuple[str, ...] = ("scripts", "bin", "next.py")
_CLAUDE_CORE_PLUGIN_KEY = "livespec@livespec"
_SPEC_NEXT_TIMEOUT_SECONDS = 60
_NON_ACTIONABLE_ACTIONS = frozenset(("", "none"))


@dataclass(frozen=True, slots=True, kw_only=True)
class _SpecNextResult:
    """Captured stdout + exit code from the spec-`next` CLI runner seam."""

    stdout: str
    returncode: int


class _ResolveSpecNextCommand(Protocol):
    """Seam: resolve the runnable spec-`next` argv, or None when unresolvable."""

    def __call__(self, *, project_root: Path) -> list[str] | None: ...


class _RunSpecNextCli(Protocol):
    """Seam: run a resolved argv and capture its stdout + exit code."""

    def __call__(self, *, argv: list[str]) -> _SpecNextResult: ...


@dataclass(frozen=True, slots=True, kw_only=True)
class SpecNextSeam:
    """Injectable side-effecting seams for the spec-`next` bridge."""

    resolve_command: _ResolveSpecNextCommand
    run: _RunSpecNextCli


def _candidate_urgency(*, value: object) -> AttentionUrgency:
    """Coerce a candidate's `urgency` to the attention scale, defaulting medium."""
    if value == "high":
        return "high"
    if value == "low":
        return "low"
    return "medium"


def _spec_output_from_candidate(*, candidate: object, project_root: Path) -> SpecNextOutput | None:
    """Adapt one spec-`next` candidate into a SpecNextOutput, or None if inert."""
    if not isinstance(candidate, dict):
        return None
    mapping = cast("dict[str, Any]", candidate)
    action = mapping.get("action")
    if not isinstance(action, str) or action in _NON_ACTIONABLE_ACTIONS:
        return None
    reason = mapping.get("reason")
    summary = f"Spec-side {action} is ready."
    if isinstance(reason, str) and reason != "":
        summary = reason
    target = mapping.get("target")
    spec_target = "SPECIFICATION"
    if isinstance(target, str) and target != "":
        spec_target = target
    return SpecNextOutput(
        op=action,
        spec_target=spec_target,
        summary=summary,
        urgency=_candidate_urgency(value=mapping.get("urgency")),
        command=f"codex exec livespec:{action} --project-root {_quote(path=project_root)}",
    )


def _adapt_top_candidate(*, stdout: str, project_root: Path) -> SpecNextOutput | None:
    """Adapt the top non-`none` candidate from spec-`next` stdout, or None."""
    payload = loads_json_optional(text=stdout)
    if not isinstance(payload, dict):
        return None
    candidates = cast("dict[str, Any]", payload).get("candidates")
    if not isinstance(candidates, list):
        return None
    for candidate in cast("list[Any]", candidates):
        output = _spec_output_from_candidate(candidate=candidate, project_root=project_root)
        if output is not None:
            return output
    return None


@dataclass(frozen=True, slots=True, kw_only=True)
class CoreRootBases:
    """Injectable filesystem bases for CORE plugin-root resolution."""

    claude_registry: Path
    codex_cache: Path


def _as_str_argv(*, value: object) -> list[str] | None:
    """Return `value` as a non-empty list of strings, or None for any other shape."""
    if not isinstance(value, list):
        return None
    items = cast("list[Any]", value)
    if not items or not all(isinstance(element, str) for element in items):
        return None
    return [str(element) for element in items]


def _read_spec_clis_next_argv(*, project_root: Path) -> list[str] | None:
    """The governed project's `spec_clis.next` argv, or None when absent/malformed."""
    config_path = project_root / _LIVESPEC_CONFIG
    if not config_path.is_file():
        return None
    parsed = loads_jsonc_optional(text=config_path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        return None
    spec_clis = cast("dict[str, Any]", parsed).get("spec_clis")
    if not isinstance(spec_clis, dict):
        return None
    return _as_str_argv(value=cast("dict[str, Any]", spec_clis).get("next"))


def _claude_installed_core_roots(*, registry: Path) -> Iterator[Path]:
    """Yield CORE roots from a Claude `installed_plugins.json` registry file."""
    parsed = load_json_file_optional(path=registry)
    if not isinstance(parsed, dict):
        return
    plugins = cast("dict[str, Any]", parsed).get("plugins")
    if not isinstance(plugins, dict):
        return
    entries = cast("dict[str, Any]", plugins).get(_CLAUDE_CORE_PLUGIN_KEY)
    if not isinstance(entries, list):
        return
    for entry in cast("list[Any]", entries):
        if isinstance(entry, dict):
            install_path = cast("dict[str, Any]", entry).get("installPath")
            if isinstance(install_path, str) and install_path != "":
                yield Path(install_path)


def _version_key(*, name: str) -> tuple[int, ...]:
    """Sort key for a version-dir name; a non-numeric chunk sorts lowest."""
    return tuple(int(chunk) if chunk.isdigit() else -1 for chunk in name.split("."))


def _codex_installed_core_roots(*, cache: Path) -> Iterator[Path]:
    """Yield Codex-cached CORE roots, highest version first."""
    plugin_dir = cache / "livespec" / "livespec"
    if not plugin_dir.is_dir():
        return
    version_dirs = sorted(
        (child for child in plugin_dir.iterdir() if child.is_dir()),
        key=lambda child: _version_key(name=child.name),
        reverse=True,
    )
    yield from version_dirs


def _core_root_candidates(*, project_root: Path, bases: CoreRootBases) -> Iterator[Path]:
    """Yield CORE plugin-root candidates, most-specific first."""
    yield project_root.parent / "livespec" / ".claude-plugin"
    yield from _claude_installed_core_roots(registry=bases.claude_registry)
    yield from _codex_installed_core_roots(cache=bases.codex_cache)


def _resolve_core_plugin_root(*, project_root: Path, bases: CoreRootBases) -> Path | None:
    """The first candidate root that carries the spec-`next` CLI, or None."""
    for candidate in _core_root_candidates(project_root=project_root, bases=bases):
        if candidate.joinpath(*_CORE_SPEC_NEXT_REL).is_file():
            return candidate
    return None


def _resolve_spec_next_command(*, project_root: Path, bases: CoreRootBases) -> list[str] | None:
    """The runnable spec-`next` argv, or None if CORE is unresolvable."""
    core_root = _resolve_core_plugin_root(project_root=project_root, bases=bases)
    if core_root is None:
        return None
    configured = _read_spec_clis_next_argv(project_root=project_root)
    template = configured if configured is not None else list(_DEFAULT_SPEC_NEXT_ARGV)
    return [element.replace(_PLUGIN_ROOT_PLACEHOLDER, str(core_root)) for element in template]


def _default_core_root_bases() -> CoreRootBases:  # pragma: no cover
    """The production resolution bases under the real HOME."""
    home = Path.home()
    return CoreRootBases(
        claude_registry=home / ".claude" / "plugins" / "installed_plugins.json",
        codex_cache=home / ".codex" / "plugins" / "cache",
    )


def _default_resolve_command(*, project_root: Path) -> list[str] | None:  # pragma: no cover
    """The production `resolve_command` seam."""
    return _resolve_spec_next_command(project_root=project_root, bases=_default_core_root_bases())


def _run_spec_next_cli(*, argv: list[str]) -> _SpecNextResult:  # pragma: no cover
    """Production `run` seam: shell out to CORE's spec-`next` CLI."""
    completed = run_capture(argv=argv, timeout=_SPEC_NEXT_TIMEOUT_SECONDS)
    return _SpecNextResult(stdout=completed.stdout, returncode=completed.returncode)


DEFAULT_SPEC_NEXT_SEAM = SpecNextSeam(
    resolve_command=_default_resolve_command,
    run=_run_spec_next_cli,
)


def _spec_next(
    *,
    project_root: Path,
    seam: SpecNextSeam = DEFAULT_SPEC_NEXT_SEAM,
) -> SpecNextOutput | None:
    """Invoke CORE spec-`next` cross-plane and adapt its top candidate."""
    with contextlib.suppress(OSError, subprocess.SubprocessError):
        command = seam.resolve_command(project_root=project_root)
        if command is None:
            return None
        result = seam.run(argv=[*command, "--project-root", str(project_root)])
        if result.returncode != 0:
            return None
        return _adapt_top_candidate(stdout=result.stdout, project_root=project_root)
    return None


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

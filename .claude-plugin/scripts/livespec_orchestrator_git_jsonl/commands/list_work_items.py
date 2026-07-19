"""`/livespec-orchestrator-git-jsonl:list-work-items` thin-transport command.

CLI surface per SPECIFICATION/contracts.md:

  list-work-items [--filter <name>] [--with-gap-id <id>]
                  [--with-spec-commitment-hint <id_hint>] [--json]
                  [--work-items-path <path>]

Filters:

- `--filter=gap-tied` / `--filter=freeform` — origin filter
- `--filter=blocked` — status == "blocked"
- `--filter=ready` — status == "ready" AND every depends_on item is done
- `--filter=closed` — the terminal status == "done" (the CLI token stays
  `closed`; its predicate matches the renamed terminal state)
- `--filter=all` (default)

`--with-gap-id=<id>` filters to exact gap_id match (combinable with --filter).
`--with-spec-commitment-hint=<id_hint>` filters to exact
spec_commitment_hint match. Both `--with-*` flags are combinable with
`--filter` and with each other.

Output:

- Default: one-line summary per work-item.
- `--json`: an array of work-item materialized views. Each entry
  includes the optional `spec_commitment_hint` field (string or
  `null`) — the pairing surface livespec's
  `unresolved-spec-commitment` doctor invariant matches against
  per livespec PC #4 sub-proposal 3.
"""

import argparse
import json
import sys
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Literal

from livespec_runtime.cross_repo.types import CrossRepoManifest
from returns.io import IOSuccess
from returns.unsafe import unsafe_perform_io

from livespec_orchestrator_git_jsonl.commands._config import resolve_store_config
from livespec_orchestrator_git_jsonl.commands._cross_repo import is_item_ready, load_manifest
from livespec_orchestrator_git_jsonl.errors import StoreFileMissingError
from livespec_orchestrator_git_jsonl.store import materialize_work_items, read_work_items
from livespec_orchestrator_git_jsonl.types import WorkItem

__all__: list[str] = ["main"]

FilterChoice = Literal["all", "gap-tied", "freeform", "blocked", "ready", "closed"]


def main(*, argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="list-work-items")
    _ = parser.add_argument(
        "--filter",
        dest="filter_name",
        default="all",
        choices=["all", "gap-tied", "freeform", "blocked", "ready", "closed"],
    )
    _ = parser.add_argument("--with-gap-id", dest="with_gap_id", default=None)
    _ = parser.add_argument(
        "--with-spec-commitment-hint",
        dest="with_spec_commitment_hint",
        default=None,
    )
    _ = parser.add_argument("--json", dest="as_json", action="store_true")
    _ = parser.add_argument("--work-items-path", dest="work_items_path", default=None)
    _ = parser.add_argument("--project-root", dest="project_root", default=None)
    args = parser.parse_args(argv)
    project_root = Path(args.project_root) if args.project_root is not None else Path.cwd()
    config = resolve_store_config(
        cwd=project_root,
        work_items_arg=args.work_items_path,
    )
    records_result = read_work_items(path=config.work_items_path)
    materialized: list[WorkItem] = []
    if isinstance(records_result, IOSuccess):
        records = unsafe_perform_io(records_result.unwrap())
        materialized = list(materialize_work_items(records=iter(records)).values())
    elif not isinstance(unsafe_perform_io(records_result.failure()), StoreFileMissingError):
        raise unsafe_perform_io(records_result.failure())
    manifest = load_manifest(project_root=project_root)
    filtered = _filter_work_items(
        materialized=materialized,
        name=args.filter_name,
        with_gap_id=args.with_gap_id,
        with_spec_commitment_hint=args.with_spec_commitment_hint,
        manifest=manifest,
    )
    if args.as_json:
        _write_json(items=filtered)
    else:
        _write_human(items=filtered)
    return 0


def _filter_work_items(
    *,
    materialized: list[WorkItem],
    name: str,
    with_gap_id: str | None,
    with_spec_commitment_hint: str | None,
    manifest: CrossRepoManifest,
) -> list[WorkItem]:
    by_name = _filter_by_name(materialized=materialized, name=name, manifest=manifest)
    by_gap = (
        by_name if with_gap_id is None else [item for item in by_name if item.gap_id == with_gap_id]
    )
    if with_spec_commitment_hint is None:
        return by_gap
    return [item for item in by_gap if item.spec_commitment_hint == with_spec_commitment_hint]


def _filter_by_name(
    *,
    materialized: list[WorkItem],
    name: str,
    manifest: CrossRepoManifest,
) -> list[WorkItem]:
    index = {item.id: item for item in materialized}
    predicates: dict[str, Callable[[WorkItem, dict[str, WorkItem]], bool]] = {
        "all": lambda _item, _ix: True,
        "gap-tied": lambda item, _ix: item.origin == "gap-tied",
        "freeform": lambda item, _ix: item.origin == "freeform",
        "blocked": lambda item, _ix: item.status == "blocked",
        "ready": lambda item, ix: is_item_ready(item=item, index=ix, manifest=manifest),
        "closed": lambda item, _ix: item.status == "done",
    }
    predicate = predicates[name]
    return [item for item in materialized if predicate(item, index)]


def _write_json(*, items: list[WorkItem]) -> None:
    payload = [_work_item_to_dict(item=item) for item in items]
    _ = sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _write_human(*, items: list[WorkItem]) -> None:
    if not items:
        _ = sys.stdout.write("(no work-items)\n")
        return
    for item in items:
        gap_marker = f" gap={item.gap_id}" if item.gap_id is not None else ""
        line = f"{item.id}  [{item.status}/{item.origin}{gap_marker}]  {item.title}\n"
        _ = sys.stdout.write(line)


def _work_item_to_dict(*, item: WorkItem) -> dict[str, object]:
    payload = asdict(item)
    payload["depends_on"] = list(item.depends_on)
    if item.audit is not None:
        payload["audit"] = {
            "verification_timestamp": item.audit.verification_timestamp,
            "commits": list(item.audit.commits),
            "files_changed": list(item.audit.files_changed),
        }
    return payload

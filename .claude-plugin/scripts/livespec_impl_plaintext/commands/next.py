"""`/livespec-impl-plaintext:next` thin-transport ranker.

CLI surface per SPECIFICATION/contracts.md §"next":

  next [--json] [--work-items-path <path>] [--project-root <path>]

The ranker is a pure function of work-items JSONL state plus the
cross-repo manifest at `<project-root>/.livespec.jsonc`. Per
`livespec/SPECIFICATION/contracts.md` v072 §"Implementation-plugin
contract — the 9-skill surface" → "next", the ranker MUST consult
`livespec_runtime.cross_repo.resolve_ref` for every candidate's
`depends_on` entries and MUST exclude any candidate with at least
one entry resolving to `RefStatus.OPEN`. Excluded candidates are
absent from the ranked list (not surfaced with a lower urgency).

Algorithm:

1. Load the cross-repo manifest from `<project-root>/.livespec.jsonc`
   (empty manifest when the file or `cross_repo_targets` block is
   absent).
2. Identify ready items: status == "open" AND no `depends_on` entry
   resolves to `OPEN` via `resolve_ref`. Missing local references
   resolve to `UNKNOWN` and therefore do NOT exclude (the doctor's
   `no-orphan-dependency` invariant is the right surface for that).
3. Score by:
   a. priority (lower number = more urgent),
   b. origin (gap-tied beats freeform at the same priority),
   c. captured_at (oldest first),
   d. id (lexicographic tiebreaker).
4. The top-ranked ready item becomes the recommendation. Output
   schema matches the impl-plugin contract for `next`:
   {action, work_item_ref, urgency, reason}.

When no items are ready, the action is "none" and work_item_ref is
null.
"""

import argparse
import json
import sys
from pathlib import Path

from livespec_runtime.cross_repo.types import CrossRepoManifest

from livespec_impl_plaintext.commands._config import resolve_store_config
from livespec_impl_plaintext.commands._cross_repo import is_item_ready, load_manifest
from livespec_impl_plaintext.errors import StoreFileMissingError
from livespec_impl_plaintext.store import materialize_work_items, read_work_items
from livespec_impl_plaintext.types import WorkItem


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="next")
    _ = parser.add_argument("--json", dest="as_json", action="store_true")
    _ = parser.add_argument("--work-items-path", dest="work_items_path", default=None)
    _ = parser.add_argument("--project-root", dest="project_root", default=None)
    args = parser.parse_args(argv)
    project_root = Path(args.project_root) if args.project_root is not None else Path.cwd()
    config = resolve_store_config(
        cwd=project_root,
        work_items_arg=args.work_items_path,
        memos_arg=None,
    )
    materialized = _load_work_items(path=config.work_items_path)
    manifest = load_manifest(project_root=project_root)
    recommendation = rank(items=materialized, manifest=manifest)
    if args.as_json:
        _ = sys.stdout.write(json.dumps(recommendation, indent=2, sort_keys=True) + "\n")
    else:
        line = (
            f"{recommendation['action']}  {recommendation['work_item_ref']}"
            f"  [{recommendation['urgency']}]  {recommendation['reason']}\n"
        )
        _ = sys.stdout.write(line)
    return 0


def rank(
    *,
    items: list[WorkItem],
    manifest: CrossRepoManifest | None = None,
) -> dict[str, object]:
    """Return the JSON-shaped recommendation for the highest-ranked ready item."""
    effective_manifest = manifest if manifest is not None else CrossRepoManifest(targets={})
    index = {item.id: item for item in items}
    ready = [
        item for item in items if is_item_ready(item=item, index=index, manifest=effective_manifest)
    ]
    if not ready:
        return {
            "action": "none",
            "work_item_ref": None,
            "urgency": "low",
            "reason": "no work-items are ready (queue empty or all blocked)",
        }
    ready.sort(key=_sort_key)
    top = ready[0]
    return {
        "action": "implement",
        "work_item_ref": top.id,
        "urgency": _urgency_for(priority=top.priority),
        "reason": (f"highest-ranked ready item (priority P{top.priority}, origin {top.origin})"),
    }


def _sort_key(item: WorkItem) -> tuple[int, int, str, str]:
    origin_rank = 0 if item.origin == "gap-tied" else 1
    return (item.priority, origin_rank, item.captured_at, item.id)


_URGENCY_HIGH_THRESHOLD = 0
_URGENCY_MEDIUM_THRESHOLD = 2


def _urgency_for(*, priority: int) -> str:
    if priority <= _URGENCY_HIGH_THRESHOLD:
        return "high"
    if priority <= _URGENCY_MEDIUM_THRESHOLD:
        return "medium"
    return "low"


def _load_work_items(*, path: Path) -> list[WorkItem]:
    try:
        return list(materialize_work_items(read_work_items(path=path)).values())
    except StoreFileMissingError:
        return []

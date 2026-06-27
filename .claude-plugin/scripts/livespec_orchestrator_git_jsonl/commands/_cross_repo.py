"""Cross-repo manifest + dependency-entry helpers shared by next + list-work-items.

Per `livespec/SPECIFICATION/contracts.md` — the impl-git-jsonl
consumers MUST call
`livespec_runtime.cross_repo.resolve_ref` for every typed `depends_on`
entry and treat `OPEN` as a blocking state. This module bundles:

- `load_manifest(project_root)` — read `.livespec.jsonc` and extract
  the `cross_repo_targets` block as a typed `CrossRepoManifest`.
  Returns an empty manifest when the file or block is absent; this
  is the legitimate "no cross-repo deps configured" state.
- `parse_entry(raw)` — dispatch a raw `depends_on` entry (bare string
  or typed dict) into a typed `DependsOnEntry`. Bare strings are
  converted to `LocalDependency` for forward-compatibility with the
  pre-v072 plaintext stores; the data-migration script has the
  authoritative typed-form conversion.
- `is_item_ready(item, *, index, manifest)` — predicate consumed by
  the next ranker and the list-work-items "ready" filter. An item is
  ready iff its status is "open" AND no typed `depends_on` entry
  resolves to `OPEN` via `resolve_ref`.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from livespec_runtime.cross_repo.resolve import resolve_ref
from livespec_runtime.cross_repo.types import (
    CrossRepoManifest,
    DependsOnEntry,
    LocalDependency,
    RefStatus,
)

from livespec_orchestrator_git_jsonl.io._cross_repo import (
    parse_cross_repo_manifest_optional,
    parse_depends_on_entry_optional,
)
from livespec_orchestrator_git_jsonl.io._jsonc import loads_optional
from livespec_orchestrator_git_jsonl.types import WorkItem

__all__: list[str] = [
    "is_item_ready",
    "load_manifest",
    "parse_entry",
]


_LIVESPEC_CONFIG = ".livespec.jsonc"


def load_manifest(*, project_root: Path) -> CrossRepoManifest:
    """Return the project's CrossRepoManifest, or an empty one if absent.

    Reads `<project_root>/.livespec.jsonc` and extracts the top-level
    `cross_repo_targets` block. A missing file, missing block, or
    malformed manifest all collapse to the empty-manifest sentinel —
    the impl-git-jsonl consumers tolerate degraded manifest views and
    let the spec-side doctor's `cross-repo-targets-wellformedness`
    invariant flag the malformed-config case.
    """
    config_path = project_root / _LIVESPEC_CONFIG
    if not config_path.is_file():
        return CrossRepoManifest(targets={})
    parsed = loads_optional(text=config_path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        return CrossRepoManifest(targets={})
    parsed_dict = cast("dict[str, Any]", parsed)
    block_raw = parsed_dict.get("cross_repo_targets")
    if not isinstance(block_raw, dict):
        return CrossRepoManifest(targets={})
    block = cast("dict[str, Any]", block_raw)
    result = parse_cross_repo_manifest_optional(parsed=block)
    if result is None:
        return CrossRepoManifest(targets={})
    return result


def parse_entry(*, raw: object) -> DependsOnEntry | None:
    """Dispatch a raw entry into a typed `DependsOnEntry`.

    Returns `None` for entries that cannot be parsed (legacy malformed
    shape, unknown discriminator). The caller decides how to treat
    None — the next ranker conservatively treats unparseable entries
    as blocking so a malformed record cannot accidentally surface as
    a "ready" candidate.
    """
    if isinstance(raw, str):
        return LocalDependency(work_item_id=raw)
    if isinstance(raw, dict):
        typed_raw = cast("dict[str, Any]", raw)
        return parse_depends_on_entry_optional(raw=typed_raw)
    return None


def _local_lookup_for(*, index: dict[str, WorkItem]) -> Callable[[str], RefStatus]:
    """Build the `local_status_lookup` callable resolve_ref expects."""
    return lambda work_item_id: (
        RefStatus.UNKNOWN
        if work_item_id not in index
        else (RefStatus.CLOSED if index[work_item_id].status == "closed" else RefStatus.OPEN)
    )


def _entry_blocks(
    *,
    raw: object,
    index: dict[str, WorkItem],
    manifest: CrossRepoManifest,
) -> bool:
    """Return True iff the raw entry resolves to `OPEN` via `resolve_ref`.

    Unparseable entries (per `parse_entry` returning None) are treated
    as blocking — a malformed depends_on cell must not let a candidate
    slip through the ranker.
    """
    entry = parse_entry(raw=raw)
    if entry is None:
        return True
    status = resolve_ref(
        entry=entry,
        manifest=manifest,
        local_status_lookup=_local_lookup_for(index=index),
    )
    return status == RefStatus.OPEN


def is_item_ready(
    *,
    item: WorkItem,
    index: dict[str, WorkItem],
    manifest: CrossRepoManifest,
) -> bool:
    """Return True iff the item is OPEN and no depends_on entry is OPEN.

    Mirrors the contract: only `RefStatus.OPEN` entries exclude a
    candidate. `CLOSED` and `UNKNOWN` resolutions do not exclude;
    they signify the dependency has cleared (or its state can't be
    determined, which the doctor invariants surface separately).
    """
    if item.status != "open":
        return False
    return not any(
        _entry_blocks(raw=raw, index=index, manifest=manifest) for raw in item.depends_on
    )

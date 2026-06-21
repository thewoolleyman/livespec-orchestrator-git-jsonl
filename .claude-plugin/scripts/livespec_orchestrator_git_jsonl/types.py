"""Dataclasses for Spec Reader outputs, plus re-exports of the shared
work-item model.

The work-item MODEL (the unified `WorkItem`, `AuditRecord`, and the
schema enums/aliases) is the SHARED surface that lives in
`livespec_runtime.work_items.types` — this repo donated it byte-faithfully
to the W7 shared-surface extraction, so it is RE-EXPORTED here rather than
re-declared. Every call site importing these names from
`livespec_orchestrator_git_jsonl.types` keeps working unchanged. The work-item
schema is codified by SPECIFICATION/contracts.md §"Work-items JSONL record
schema".

SpecSnapshot, SpecDiff, and FileDiff are the Spec Reader's return types
per SPECIFICATION/contracts.md §"Spec Reader internal API"; they are NOT
reachable from `WorkItem` and stay LOCAL with the Spec Reader. StoreConfig
is the local JSONL store-path configuration and also stays local.
"""

from dataclasses import dataclass, field
from pathlib import Path

from livespec_runtime.work_items.types import (
    AuditRecord,
    DependsOnRaw,
    Origin,
    Resolution,
    WorkItem,
    WorkItemStatus,
    WorkItemType,
)

__all__: list[str] = [
    "AuditRecord",
    "DependsOnRaw",
    "FileDiff",
    "Origin",
    "Resolution",
    "SpecDiff",
    "SpecSnapshot",
    "StoreConfig",
    "WorkItem",
    "WorkItemStatus",
    "WorkItemType",
]


@dataclass(frozen=True, kw_only=True)
class SpecSnapshot:
    """A read-only view of a Specification at a particular version.

    `files` maps spec_root-relative file paths to their full text content.
    `version` is the snapshot's vNNN integer (1-indexed). For the live
    specification (the top-level spec_root tree), `version` is the latest
    history version the snapshot corresponds to per
    SPECIFICATION/contracts.md §"Spec Reader internal API" capability 3.
    """

    version: int
    files: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, kw_only=True)
class SpecDiff:
    """Structured diff between two SpecSnapshot versions.

    `per_file` maps each file path that differs between the two snapshots
    to a per-file summary carrying added and removed line counts plus a
    unified-diff body. Files present only in one snapshot appear with the
    other side's count zero. Files identical in both snapshots are NOT
    included.
    """

    version_a: int
    version_b: int
    per_file: dict[str, "FileDiff"] = field(default_factory=dict)


@dataclass(frozen=True, kw_only=True)
class FileDiff:
    """Per-file diff summary inside a SpecDiff."""

    path: str
    added_lines: int
    removed_lines: int
    unified_diff: str


@dataclass(frozen=True, kw_only=True)
class StoreConfig:
    """Configured path for the JSONL store, read from .livespec.jsonc.

    Per SPECIFICATION/contracts.md §"`compat` block", the
    livespec-orchestrator-git-jsonl configuration block declares work_items_path;
    the default is work-items.jsonl at the consumer project root.
    """

    work_items_path: Path

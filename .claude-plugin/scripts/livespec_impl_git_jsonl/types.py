"""Dataclasses for work-items, memos, and Spec Reader outputs.

The work-item and memo schemas are codified by SPECIFICATION/contracts.md
§"Work-items JSONL record schema" / §"Memos JSONL record schema". Every
field below has an entry there; field types here are the Python-level
realization.

SpecSnapshot and SpecDiff are the Spec Reader's return types per
SPECIFICATION/contracts.md §"Spec Reader internal API".
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

__all__: list[str] = [
    "AuditRecord",
    "DependsOnRaw",
    "Disposition",
    "FileDiff",
    "Memo",
    "MemoState",
    "Origin",
    "Resolution",
    "SpecDiff",
    "SpecSnapshot",
    "StoreConfig",
    "WorkItem",
    "WorkItemStatus",
    "WorkItemType",
]

DependsOnRaw = str | dict[str, Any]

WorkItemStatus = Literal["open", "in_progress", "blocked", "closed", "deferred"]
WorkItemType = Literal["bug", "feature", "task", "chore", "epic"]
Origin = Literal["gap-tied", "freeform"]
Resolution = Literal[
    "completed",
    "wontfix",
    "duplicate",
    "spec-revised",
    "no-longer-applicable",
    "resolved-out-of-band",
]

MemoState = Literal["untriaged", "dispositioned"]
Disposition = Literal[
    "spec-bound",
    "impl-bound",
    "persistent-knowledge",
    "discard",
]


@dataclass(frozen=True, kw_only=True)
class AuditRecord:
    """Audit-trail fields captured at completed-resolution closure time.

    `merge_sha` and `pr_number` are the merge-evidence fields landed for
    li-tenpup (the `work-item-merge-evidence` child PC). Per
    SPECIFICATION/contracts.md "Work-items JSONL record schema" -> audit,
    `merge_sha` is the required, non-empty SHA of the merge commit on the
    canonical branch that introduced the work; `pr_number` is the optional
    GitHub PR number (int or `None`) for traceability. Audit objects authored
    before `pr_number` landed read back as `None` without firing a schema
    violation; `merge_sha` is required-on-read for any audit object the
    merge-evidence static check will later attest.
    """

    verification_timestamp: str
    commits: tuple[str, ...]
    files_changed: tuple[str, ...]
    merge_sha: str
    pr_number: int | None = None


@dataclass(frozen=True, kw_only=True)
class WorkItem:
    """A single JSONL work-item record (one line of the work-items file).

    `spec_commitment_hint` is the OPTIONAL pairing field landed for
    livespec PC #4 sub-proposal 3 (livespec v083). When the work-item
    is filed in response to a spec-side `spec_commitments.impl_followups[]`
    declaration, this field carries the originating `id_hint` verbatim.
    For freeform work-items unrelated to any spec commitment, it is
    `None`. Legacy records lacking the field on disk read back as
    `None` (no in-place migration required); the field is OPTIONAL on
    the read path but always written explicitly on append (as `null`
    or the value).

    `supersedes` is the append-only supersession pointer (the sixteenth
    schema key, per SPECIFICATION/contracts.md "Work-items JSONL record
    schema" -> supersedes and "Append-only store disciplines"). `None`
    marks an original record; a non-None value carries the stable
    per-record identity (`store.work_item_record_identity`) of the
    single prior record this record amends. Required-on-write,
    optional-on-read with the same legacy-record treatment as
    `spec_commitment_hint`.
    """

    id: str
    type: WorkItemType
    status: WorkItemStatus
    title: str
    description: str
    origin: Origin
    gap_id: str | None
    priority: int
    assignee: str | None
    depends_on: tuple[DependsOnRaw, ...]
    captured_at: str
    resolution: Resolution | None
    reason: str | None
    audit: AuditRecord | None
    superseded_by: str | None
    spec_commitment_hint: str | None = None
    supersedes: str | None = None


@dataclass(frozen=True, kw_only=True)
class Memo:
    """A single JSONL memo record (one line of the memos file).

    `supersedes` carries the same append-only supersession-pointer
    semantics as the work-items schema's key (per
    SPECIFICATION/contracts.md "Memos JSONL record schema" ->
    supersedes): required-on-write, optional-on-read, `None` for an
    original record, the stable per-record identity
    (`store.memo_record_identity`) of the amended record otherwise.
    """

    id: str
    text: str
    state: MemoState
    disposition: Disposition | None
    captured_at: str
    work_item_id: str | None
    knowledge_file: str | None
    propose_change_topic: str | None
    supersedes: str | None = None


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
    """Configured paths for the JSONL store, read from .livespec.jsonc.

    Per SPECIFICATION/contracts.md §"`compat` block", the
    livespec-impl-git-jsonl configuration block declares work_items_path
    and memos_path; defaults are work-items.jsonl and memos.jsonl at the
    consumer project root.
    """

    work_items_path: Path
    memos_path: Path

"""Translate a beads issues.jsonl export into work-items.jsonl records.

Reads each line as a beads issue record (matching the schema produced by
`bd list --status=all --format=json` and the on-disk `.beads/issues.jsonl`
export view), maps the fields onto livespec-orchestrator-git-jsonl's WorkItem
schema (defined in SPECIFICATION/contracts.md), and appends to the
output file.

The migration produces one final-state record per beads issue (not a Red
→ Green pair). This is the materialized view at migration time; future
state transitions append new records per the standard append-only
discipline.

The script is one-shot — re-running on the same input produces duplicate
records (no idempotency built in). Callers MUST run it exactly once
during the Phase D.10 cutover; subsequent edits go through the regular
heavyweight skills.
"""

import argparse
import json
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from livespec_runtime.work_items.rank import key_between
from returns.io import IOFailure
from returns.unsafe import unsafe_perform_io

from livespec_orchestrator_git_jsonl.store import append_work_item
from livespec_orchestrator_git_jsonl.types import AuditRecord, WorkItem, WorkItemStatus

__all__: list[str] = ["main", "translate_record"]

_GAP_ID_LABEL_PREFIX = "gap-id:"
_RESOLUTION_LABEL_PREFIX = "resolution:"

# Map the legacy beads built-in statuses onto the v013 livespec lifecycle
# states. The 7-state names (and `blocked`, name-matched) pass through via
# the `.get(raw, raw)` default. `deferred` is removed → `backlog`.
_BEADS_STATUS_MAP: dict[str, WorkItemStatus] = {
    "open": "ready",
    "in_progress": "active",
    "closed": "done",
    "deferred": "backlog",
}


def main(*, argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="migrate-beads")
    _ = parser.add_argument(
        "--beads-jsonl",
        dest="beads_jsonl",
        required=True,
        help="Path to .beads/issues.jsonl (the beads export view).",
    )
    _ = parser.add_argument(
        "--work-items-out",
        dest="work_items_out",
        required=True,
        help="Destination work-items.jsonl path. Records are appended.",
    )
    args = parser.parse_args(argv)
    beads_path = Path(args.beads_jsonl)
    out_path = Path(args.work_items_out)
    count = 0
    # `priority` is gone in v013; `rank` is the sole ordering key. The
    # converter assigns evenly-increasing fractional keys in file order by
    # threading the previous key into `key_between`, so every migrated head
    # carries a real (non-sentinel) rank and order is deterministic.
    prev_rank: str | None = None
    for record in _iter_beads_records(path=beads_path):
        rank = key_between(a=prev_rank, b=None)
        work_item = translate_record(parsed=record, rank=rank)
        append_result = append_work_item(path=out_path, item=work_item)
        if isinstance(append_result, IOFailure):
            failure = unsafe_perform_io(append_result.failure())
            _ = sys.stderr.write(f"ERROR: failed to append {work_item.id}: {failure}\n")
            return 1
        prev_rank = rank
        count += 1
    _ = sys.stdout.write(f"migrated {count} beads issues → {out_path}\n")
    return 0


def translate_record(*, parsed: dict[str, Any], rank: str = "a0") -> WorkItem:
    """Map a single beads issue dict to a WorkItem dataclass.

    `rank` is the v013 fractional ordering key (default `"a0"` — a valid
    first key — for direct callers; `main` threads evenly-increasing keys
    across the batch). The legacy beads `status` is mapped onto the
    7-state lifecycle enum via `_BEADS_STATUS_MAP`.
    """
    labels = list(parsed.get("labels", []))
    gap_id = _extract_label_value(labels=labels, prefix=_GAP_ID_LABEL_PREFIX)
    resolution_value = _extract_label_value(labels=labels, prefix=_RESOLUTION_LABEL_PREFIX)
    origin = "gap-tied" if gap_id is not None else "freeform"
    raw_status = parsed.get("status", "open")
    status = _BEADS_STATUS_MAP.get(raw_status, raw_status)
    return WorkItem(
        id=parsed["id"],
        type=parsed.get("issue_type", "task"),
        status=status,
        title=parsed.get("title", ""),
        description=parsed.get("description", ""),
        origin=origin,
        gap_id=gap_id,
        rank=rank,
        assignee=parsed.get("assignee"),
        depends_on=(),
        captured_at=parsed.get("created_at", ""),
        resolution=resolution_value if status == "done" else None,  # type: ignore[arg-type]
        reason=parsed.get("close_reason") if status == "done" else None,
        audit=_extract_audit(parsed=parsed, status=status, gap_id=gap_id),
        superseded_by=None,
    )


def _iter_beads_records(*, path: Path) -> Iterator[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for raw_line in handle:
            stripped = raw_line.rstrip("\n")
            if stripped == "":
                continue
            parsed = json.loads(stripped)
            if not isinstance(parsed, dict):
                continue
            yield parsed


def _extract_label_value(*, labels: list[object], prefix: str) -> str | None:
    for label in labels:
        if isinstance(label, str) and label.startswith(prefix):
            return label[len(prefix) :]
    return None


def _extract_audit(
    *,
    parsed: dict[str, Any],
    status: str,
    gap_id: str | None,
) -> AuditRecord | None:
    if status != "done":
        return None
    if gap_id is None:
        return None
    # The beads notes field carries 'Verification run_id: ...' / 'Verification
    # timestamp: ...' lines for gap-tied closures. We reconstruct a minimal
    # AuditRecord when those markers are present; missing markers yield None
    # so the migrated record still parses (the no-extra-keys constraint is
    # honored either way).
    notes = parsed.get("notes")
    if not isinstance(notes, str):
        return None
    verification_timestamp = _extract_notes_field(notes=notes, key="Verification timestamp")
    if verification_timestamp is None:
        return None
    return AuditRecord(
        verification_timestamp=verification_timestamp,
        commits=(),
        files_changed=(),
        merge_sha="<pre-schema-bootstrap>",
        pr_number=None,
    )


def _extract_notes_field(*, notes: str, key: str) -> str | None:
    marker = f"{key}: "
    for line in notes.splitlines():
        stripped = line.strip()
        if stripped.startswith(marker):
            return stripped[len(marker) :]
    return None

"""One-shot migration: bare-string + blocked_by → typed depends_on entries.

Per `livespec/SPECIFICATION/contracts.md` + work-item li-f5wmjr:

For every WorkItem record in a work-items.jsonl store:

1. Merge `blocked_by` entries into `depends_on` (deduplicating).
2. Convert every bare-string `depends_on` entry to the typed
   `{"kind": "local", "work_item_id": "<id>"}` form.
3. Drop the `blocked_by` field entirely (it's been absorbed by
   `depends_on` per Model B).

The migration runs ONCE per repo; subsequent appends use the typed
shape natively (per `livespec_orchestrator_git_jsonl.store.append_work_item`'s
JSON-schema validation, landed via li-7zxnhw).

Records that already use the typed shape pass through unchanged.

Append-only invariant: the migration writes a single transition
record per migrated work-item id (latest-record-per-id wins). Records
with no legacy data to migrate are NOT re-emitted.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

__all__: list[str] = ["main", "migrate_file"]


def _coerce_list(*, raw: object) -> list[Any]:
    """Return raw if it's a list, else an empty list."""
    return list(raw) if isinstance(raw, list) else []  # type: ignore[arg-type]


def _needs_migration(*, record: dict[str, Any]) -> bool:
    """Return True if the record carries legacy bare-strings or a blocked_by field."""
    if "blocked_by" in record:
        return True
    deps: list[Any] = _coerce_list(raw=record.get("depends_on"))
    return any(isinstance(entry, str) for entry in deps)


def _typed_dep(*, entry: Any) -> dict[str, Any]:
    """Return the typed form for a depends_on entry.

    Bare strings → {"kind": "local", "work_item_id": "<str>"}.
    Already-typed dicts pass through unchanged.
    Other shapes (defensive) pass through unchanged for the doctor's
    `depends_on-ref-wellformedness` invariant to flag.
    """
    if isinstance(entry, str):
        return {"kind": "local", "work_item_id": entry}
    return entry


def _merge_blocked_by_into_depends_on(*, record: dict[str, Any]) -> list[Any]:
    """Build the merged depends_on list (existing + blocked_by, deduplicated)."""
    existing: list[Any] = _coerce_list(raw=record.get("depends_on"))
    blocked_by: list[Any] = _coerce_list(raw=record.get("blocked_by"))
    merged: list[Any] = []
    seen: set[str] = set()
    for entry in existing + blocked_by:
        typed = _typed_dep(entry=entry)
        key = json.dumps(typed, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        merged.append(typed)
    return merged


def _migrate_record(*, record: dict[str, Any]) -> dict[str, Any]:
    """Return a new record with merged + typed depends_on; blocked_by dropped."""
    migrated = dict(record)
    migrated["depends_on"] = _merge_blocked_by_into_depends_on(record=record)
    migrated.pop("blocked_by", None)
    return migrated


def _materialize_index(*, lines: list[str]) -> dict[str, dict[str, Any]]:
    """Build the latest-record-per-id index from raw JSONL lines."""
    index: dict[str, dict[str, Any]] = {}
    for line in lines:
        stripped = line.strip()
        if stripped == "":
            continue
        record = json.loads(stripped)
        item_id = record.get("id")
        if isinstance(item_id, str):
            index[item_id] = record
    return index


def _migrate_lines(*, lines: list[str]) -> tuple[list[str], int]:
    """Materialize the index, emit transition records for legacy entries.

    Returns (new_lines, migrated_count). new_lines preserves the
    original append-only history and appends one transition record
    per id whose materialized view needs migration.
    """
    index = _materialize_index(lines=lines)
    transition_lines: list[str] = []
    migrated_count = 0
    for record in index.values():
        if not _needs_migration(record=record):
            continue
        migrated = _migrate_record(record=record)
        transition_lines.append(json.dumps(migrated, separators=(",", ":"), sort_keys=True))
        migrated_count += 1
    new_lines = list(lines)
    if transition_lines:
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines[-1] = new_lines[-1] + "\n"
        for transition in transition_lines:
            new_lines.append(transition + "\n")
    return new_lines, migrated_count


def migrate_file(*, path: Path, dry_run: bool = False) -> int:
    """Migrate a work-items.jsonl file in place; return the migrated count."""
    raw = path.read_text(encoding="utf-8")
    lines = raw.splitlines(keepends=True)
    new_lines, migrated_count = _migrate_lines(lines=lines)
    if migrated_count and not dry_run:
        _ = path.write_text("".join(new_lines), encoding="utf-8")
    return migrated_count


def main(*, argv: list[str] | None = None) -> int:
    """CLI entry: --path <work-items.jsonl> [--dry-run]."""
    parser = argparse.ArgumentParser(
        description=(
            "Migrate a work-items.jsonl store from the pre-v072 bare-string + "
            "blocked_by schema to the v072 typed DependsOnEntry schema. "
            "Runs once per repo; idempotent."
        ),
    )
    _ = parser.add_argument("--path", type=Path, required=True)
    _ = parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    target_path: Path = args.path
    dry_run: bool = args.dry_run
    if not target_path.exists():
        _ = sys.stderr.write(f"ERROR: {target_path} does not exist\n")
        return 1
    migrated = migrate_file(path=target_path, dry_run=dry_run)
    verb = "would migrate" if dry_run else "migrated"
    _ = sys.stdout.write(f"{verb} {migrated} record(s) in {target_path}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

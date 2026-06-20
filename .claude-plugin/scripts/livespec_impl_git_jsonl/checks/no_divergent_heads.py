"""`check-no-divergent-heads` store-integrity check.

Per SPECIFICATION/contracts.md §"Append-only store disciplines" →
"Store-integrity checks (orchestrator-private)" (v008), this check
materializes the declared backing store (work-items) via the canonical
reducer (`reduce_work_item_heads` — the ONE reduction implementation
every query wrapper and check consumes; the one-canonical-reducer
obligation) and fires fail when any entity id resolves to more than one
un-superseded head, naming the offending entity id and the conflicting
record identities so the operator can append a reconciling record.

Wired into this repo's `just check` aggregate (NOT livespec's doctor —
the store is orchestrator-private under the re-steered contract) as
`check-no-divergent-heads`, invoked through the
`.claude-plugin/scripts/bin/check_no_divergent_heads.py` wrapper.

An absent store file is a pass (nothing to reduce; noted in output). A
malformed or schema-violating store is a failure — the reducer cannot
materialize it — reported as a finding, never an uncaught traceback.
"""

import argparse
import sys
from pathlib import Path

from livespec_impl_git_jsonl.commands._config import resolve_store_config
from livespec_impl_git_jsonl.errors import (
    MalformedRecordLineError,
    SchemaViolationError,
    StoreFileMissingError,
)
from livespec_impl_git_jsonl.store import (
    read_work_items,
    reduce_work_item_heads,
    work_item_record_identity,
)
from livespec_impl_git_jsonl.types import StoreConfig, WorkItem

__all__: list[str] = ["main"]


_CHECK_NAME = "check-no-divergent-heads"


def _parse_config(*, argv: list[str] | None) -> StoreConfig:
    parser = argparse.ArgumentParser(prog=_CHECK_NAME)
    _ = parser.add_argument("--work-items-path", dest="work_items_path", default=None)
    args = parser.parse_args(argv)
    return resolve_store_config(
        cwd=Path.cwd(),
        work_items_arg=args.work_items_path,
    )


def main(*, argv: list[str] | None = None) -> int:
    config = _parse_config(argv=argv)

    wi_notes: list[str] = []
    wi_failures: list[str] = []
    wi_heads: dict[str, tuple[WorkItem, ...]] = {}
    try:
        wi_heads = reduce_work_item_heads(records=read_work_items(path=config.work_items_path))
    except StoreFileMissingError:
        wi_notes = [_absent_note(kind="work-items", path=config.work_items_path)]
    except (MalformedRecordLineError, SchemaViolationError) as exc:
        wi_failures = [
            _unreadable_failure(kind="work-items", path=config.work_items_path, detail=str(exc))
        ]
    else:
        wi_failures = _divergence_failures(
            kind="work-items",
            path=config.work_items_path,
            labeled_heads={
                eid: tuple(work_item_record_identity(item=r) for r in group)
                for eid, group in wi_heads.items()
            },
        )

    failures = wi_failures
    for line in (*wi_notes, *failures):
        _ = sys.stdout.write(line + "\n")
    if failures:
        _ = sys.stdout.write(f"{_CHECK_NAME}: FAIL — {len(failures)} finding(s)\n")
        return 1
    _ = sys.stdout.write(f"{_CHECK_NAME}: OK — no divergent un-superseded heads\n")
    return 0


def _divergence_failures(
    *,
    kind: str,
    path: Path,
    labeled_heads: dict[str, tuple[str, ...]],
) -> list[str]:
    """Name every entity whose reduction yields more than one head.

    The canonical reducer surfaces divergence rather than silently
    choosing a winner; this check turns that surfaced state into a
    `fail` finding carrying the entity id and each conflicting
    record identity (ascending tie-break order, as the reducer
    emits them).
    """
    failures: list[str] = []
    for entity_id in sorted(labeled_heads):
        identities = labeled_heads[entity_id]
        if len(identities) > 1:
            joined = ", ".join(identities)
            prefix = f"{_CHECK_NAME}: {kind} store '{path}': entity '{entity_id}'"
            failures.append(f"{prefix} resolves to {len(identities)} un-superseded heads: {joined}")
    return failures


def _absent_note(*, kind: str, path: Path) -> str:
    return f"{_CHECK_NAME}: {kind} store '{path}' absent — skipped"


def _unreadable_failure(*, kind: str, path: Path, detail: str) -> str:
    return f"{_CHECK_NAME}: {kind} store '{path}' unreadable — {detail}"

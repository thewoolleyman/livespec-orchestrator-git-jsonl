"""JSONL store primitives for work-items.

Per SPECIFICATION/contracts.md, the store is
append-only at the write boundary and the materialized view of an
entity is its supersession-chain head, computed from the in-record
`supersedes` pointers independently of the physical order of records in
the file (git may reorder lines during a merge; the legacy "latest
record by file order wins" reduction is retired).

The canonical PURE reduction — `work_item_record_identity`,
`reduce_work_item_heads`, `materialize_work_items` — is the SHARED
surface this repo donated byte-faithfully to the W7 extraction; it now
lives in `livespec_runtime.work_items.reduce` and is RE-EXPORTED here so
every consumer keeps importing it from `livespec_orchestrator_git_jsonl.store`
unchanged. What stays LOCAL is the JSONL-specific backend I/O
(`read_work_items` / `append_work_item` over `io/store.py`), the
JSONL-schema validators (`_validate_work_item_payload` / `_check_*` /
`_validate_audit_payload`), and the dict<->WorkItem boundary
(`_parse_work_item` on read, `_work_item_to_dict` on write).

`JsonlWorkItemStore` is the thin facade that conforms this repo's
backend to the shared `livespec_runtime.work_items.store.WorkItemStore`
Protocol (a stream of records out, one record in) without rewriting any
call site; the module-level `_: type[WorkItemStore]` binding makes
pyright attest that conformance statically.

Public API:

- `read_work_items(*, path)` — stream WorkItem records from the file
  (raises StoreFileMissingError if absent).
- `append_work_item(*, path, item)` — write a new record line.
- `work_item_record_identity(*, item)` — re-exported canonical
  per-record identity (`sha256:<hex-digest>` over the canonical
  serialization).
- `reduce_work_item_heads(*, records)` — re-exported canonical
  order-independent head reduction.
- `materialize_work_items(*, records)` — re-exported reduction to the
  current-head-per-id dict.
- `JsonlWorkItemStore` — the WorkItemStore-conforming facade over the
  free functions above.

The reader functions validate every record against the schema; a
violation raises SchemaViolationError carrying the offending line
number. A non-JSON line raises MalformedRecordLineError. Both are
EXPECTED errors per the Result-vs-bugs split.
"""

from pathlib import Path
from typing import Any

from livespec_runtime.work_items.reduce import (
    materialize_work_items,
    reduce_work_item_heads,
    work_item_record_identity,
)
from returns.io import IOFailure, IOResult, IOSuccess
from returns.result import Failure
from returns.unsafe import unsafe_perform_io

from livespec_orchestrator_git_jsonl.io.store import (
    append_record as _io_append_record,
)
from livespec_orchestrator_git_jsonl.io.store import (
    iter_records as _io_iter_records,
)
from livespec_orchestrator_git_jsonl.store_codec import parse_work_item, work_item_to_dict
from livespec_orchestrator_git_jsonl.store_schema import validate_work_item_payload
from livespec_orchestrator_git_jsonl.types import WorkItem

__all__: list[str] = [
    "JsonlWorkItemStore",
    "append_work_item",
    "materialize_work_items",
    "read_work_items",
    "reduce_work_item_heads",
    "work_item_record_identity",
]


def read_work_items(*, path: Path) -> IOResult[list[WorkItem], Exception]:
    """Read WorkItem records from the JSONL file at `path` on the IOResult railway."""
    records_result = _iter_records(path=path)
    if isinstance(records_result, IOFailure):
        return IOFailure(unsafe_perform_io(records_result.failure()))
    work_items: list[WorkItem] = []
    for line_number, parsed in unsafe_perform_io(records_result.unwrap()):
        parsed_item = parse_work_item(path=path, line_number=line_number, parsed=parsed)
        if isinstance(parsed_item, Failure):
            return IOFailure(parsed_item.failure())
        work_items.append(parsed_item.unwrap())
    return IOSuccess(work_items)


def append_work_item(*, path: Path, item: WorkItem) -> IOResult[None, Exception]:
    """Append a single WorkItem as a new line in the JSONL file.

    Validates the dict-serialized payload against the same schema the
    read path enforces before writing; raises SchemaViolationError when
    the payload would not round-trip through `read_work_items`. The
    write is symmetric with the read so a record landing on disk is
    guaranteed to parse back cleanly.
    """
    payload = work_item_to_dict(item=item)
    validation = validate_work_item_payload(path=path, line_number=0, parsed=payload)
    if isinstance(validation, Failure):
        return IOFailure(validation.failure())
    return _append_record(path=path, payload=payload)


class JsonlWorkItemStore:
    """WorkItemStore-conforming facade over this repo's JSONL backend.

    Conforms structurally to
    `livespec_runtime.work_items.store.WorkItemStore` by exposing the two
    Protocol operations over the module-level free functions, binding the
    single JSONL `Path` (git-jsonl's `StoreConfig` wraps exactly one
    `Path`, `work_items_path`, which is passed here directly). No call site
    is rewritten: tools that want the Protocol view construct this facade;
    everything else keeps calling the free functions.
    """

    def __init__(self, *, path: Path) -> None:
        self._path = path

    def read_work_items(self) -> IOResult[list[WorkItem], Exception]:
        """Read every WorkItem record the backing JSONL file holds."""
        return read_work_items(path=self._path)

    def append_work_item(self, *, item: WorkItem) -> IOResult[None, Exception]:
        """Append a single WorkItem record to the backing JSONL file."""
        return append_work_item(path=self._path, item=item)


_REDUCTION_EXPORTS = (materialize_work_items, reduce_work_item_heads, work_item_record_identity)


def _iter_records(*, path: Path) -> IOResult[list[tuple[int, dict[str, Any]]], Exception]:
    return _io_iter_records(path=path)


def _append_record(*, path: Path, payload: dict[str, Any]) -> IOResult[None, Exception]:
    return _io_append_record(path=path, payload=payload)


_validate_work_item_payload = validate_work_item_payload
_parse_work_item = parse_work_item
_work_item_to_dict = work_item_to_dict

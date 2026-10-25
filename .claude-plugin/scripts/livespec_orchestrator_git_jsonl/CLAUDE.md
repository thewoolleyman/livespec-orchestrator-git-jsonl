# livespec_orchestrator_git_jsonl/

The Python package the shebang wrappers import. This is the
JSONL-backed implementation plugin for livespec; the package name is
`livespec_orchestrator_git_jsonl` (NOT `livespec`).

Top-level modules:

- `types.py` — RE-EXPORTS the shared work-item model (`WorkItem`,
  `AuditRecord`, the enums/aliases) from
  `livespec_runtime.work_items.types`, plus the LOCAL Spec Reader
  snapshot / diff dataclasses and `StoreConfig`. Consumed by every
  skill and every thin-transport CLI. Dataclasses are `kw_only=True`.
- `store.py` — append-only JSONL store primitives (append + read) for
  the work-items file, plus the `JsonlWorkItemStore` facade conforming
  to `livespec_runtime.work_items.store.WorkItemStore`. The canonical
  reduce + materialize + per-record-identity surface is RE-EXPORTED
  from `livespec_runtime.work_items.reduce` (this repo donated it
  byte-faithfully to the W7 extraction). The materialized view is the
  supersession-chain head per `id`, computed order-independently from
  the in-record `supersedes` pointers with the deterministic tie-break
  (`captured_at`, then the sha256 per-record identity); that runtime
  reducer is the ONE canonical reducer every consumer MUST delegate to
  (per `SPECIFICATION/contracts.md` §"Materialized view" /
  §"Append-only store disciplines").
- `spec_reader.py` — read-only Spec Reader adapter implementing the
  four required capabilities from `livespec/SPECIFICATION/
  contracts.md` §"Spec Reader required-capability surface". MUST NOT
  mutate the spec tree (§"Spec Reader implementation constraints").
- `spec_change_tier.py` — the codec for the `spec_change_tier` record
  key: the JSON serialization of the vendored
  `livespec_runtime.spec_stated.SpecChangeTier` the two capture skills
  file a judged work-item with. The tier is NOT a `WorkItem` field —
  the shared model carries none — so it travels beside the item
  through `append_work_item`'s own keyword argument. `None` (no
  classification ran) and `tier: "none"` (one ran and reported no spec
  change owed) are DIFFERENT answers and must never be collapsed.
- `errors.py` — the EXPECTED-error exception surface (missing file,
  malformed line, schema violation, version not found).
- `_ids.py` — work-item id generation helper.

Module-level rules an agent editing this tree must follow:

- Every module declares `__all__: list[str]` enumerating its public
  surface.
- The append-only discipline is load-bearing: NO code may truncate,
  rewrite, or delete records in the work-items JSONL. State
  transitions are new appended records, not edits.
- Records conform exactly to the schema in
  `SPECIFICATION/contracts.md` §"Work-items JSONL record schema";
  extra keys are forbidden.
- Domain errors vs bugs: surface EXPECTED errors as the `errors.py`
  exception types and catch them at the supervisor (`commands/<cmd>.
  main()`); raise built-in exceptions for bugs and let them
  propagate.
- No off-substrate persistence (no sidecar JSON/SQLite, no env-var
  state) — per §"Forbidden patterns".

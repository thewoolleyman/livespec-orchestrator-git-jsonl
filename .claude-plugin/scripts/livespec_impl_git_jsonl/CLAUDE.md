# livespec_impl_git_jsonl/

The Python package the shebang wrappers import. This is the
JSONL-backed implementation plugin for livespec; the package name is
`livespec_impl_git_jsonl` (NOT `livespec`).

Top-level modules:

- `types.py` — work-item dataclasses, plus the Spec Reader
  snapshot / diff dataclasses. Consumed by every skill and every
  thin-transport CLI. Dataclasses are `kw_only=True`.
- `store.py` — append-only JSONL store primitives (append + read +
  reduce + materialize) for the work-items file. The
  materialized view is the supersession-chain head per `id`, computed
  order-independently from the in-record `supersedes` pointers with
  the deterministic tie-break (`captured_at`, then the sha256
  per-record identity); `_reduce_heads` is the ONE canonical reducer
  every consumer MUST delegate to (per `SPECIFICATION/contracts.md`
  §"Materialized view" / §"Append-only store disciplines").
- `spec_reader.py` — read-only Spec Reader adapter implementing the
  four required capabilities from `livespec/SPECIFICATION/
  contracts.md` §"Spec Reader required-capability surface". MUST NOT
  mutate the spec tree (§"Spec Reader implementation constraints").
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

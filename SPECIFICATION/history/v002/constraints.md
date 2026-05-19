# constraints.md — livespec-impl-plaintext

Architecture-level constraints this plugin operates under. Each
constraint is a binary, mechanically-checkable rule; lint /
type-check / test failures are the enforcement mechanism.

## Inherited from livespec

Every constraint in
`livespec/SPECIFICATION/non-functional-requirements.md`
applies to this plugin without restatement. The list below
captures only the constraints that are PLUGIN-LOCAL refinements
or that bear directly on the JSONL substrate.

Inherited (verbatim, NOT re-stated here):

- Toolchain pins (mise + uv); `just` as the single dev-tooling
  entry point.
- Ruff rule set; Pyright strict mode plus the seven strict-plus
  diagnostics.
- 100% line + branch coverage; pytest discipline; hypothesis
  property-based test coverage on pure modules.
- Conventional Commits subjects; rebase-merge-only master.
- Lefthook pre-commit / commit-msg / pre-push step ordering.
- Comment discipline (Ruff ERA; no historical references inline).
- Keyword-only arguments and dataclasses (Python K4).
- Domain errors vs bugs split — Result-track for expected errors;
  raised exceptions for unexpected (Python K10).
- ROP-style composition of expected errors at the supervisor
  boundary.
- No relative imports; no banned-API surface (`abc.ABC`, `pickle`,
  etc.); typing.Protocol over abc.
- Vendored dependencies in `.claude-plugin/scripts/_vendor/`; no
  PyPI runtime dependencies.

## JSONL substrate constraints

- The work-items and memos files are append-only at the write
  boundary. No skill code MAY truncate, rewrite, or delete records
  in either file. State transitions are new records, not edits.
- Each record line is a single JSON object terminated with `\n`.
  Empty lines between records are FORBIDDEN. A trailing newline
  after the last record is REQUIRED.
- Records MUST conform to the schema in `contracts.md` §"Work-items
  JSONL record schema" / §"Memos JSONL record schema" exactly;
  extra keys are not permitted. The doctor `no-extra-keys` invariant
  (a plugin-side check, not a livespec check) fires `fail` on
  violation.
- The materialized view is the LAST record per `id` by file order.
  All readers MUST implement this reduction; in-place state queries
  are FORBIDDEN.
- File-system isolation: skills MUST NOT shell out to read or
  write `.beads/`, GitHub APIs, Linear APIs, or any other tracking
  substrate. The plugin's substrate is JSONL files only.

## Process boundaries

- Each skill invocation is a single Python process; no daemons,
  no long-lived state, no in-memory caches that span invocations.
  The on-disk JSONL is the only persistent state.
- Concurrent invocations on the same JSONL file are not guarded by
  the plugin (no lockfile, no advisory lock). Git's commit
  serialization is the conflict-resolution boundary; consumer
  workflows that produce racing writes MUST resolve the race via
  git merge.

## Spec Reader implementation constraints

- The initial implementation is a thin file pass-through; caching
  layers, indexes, embeddings, RAG adapters, and similar
  optimizations are explicitly OUT-OF-SCOPE for v001. Future
  revisions MAY introduce them so long as the four-capability API
  surface remains identical.
- The Spec Reader MUST be a Python module; the implementation
  language is not implementation-dependent at this granularity
  even though the upstream contract allows it — keeping all
  plugin code in one language reduces the toolchain surface.
- The Spec Reader MUST NOT mutate the spec tree. Read-only is
  the only mode of operation.

## Skill orchestration constraints

- Heavyweight skills (capture-impl-gaps, capture-spec-drift,
  capture-work-item, implement, capture-memo, process-memos)
  carry their orchestration logic in the SKILL.md prose; thin
  Python helpers MAY exist for utilities (record-formatting,
  schema validation) but the dialogue logic lives in markdown.
- Thin-transport skills (list-memos, list-work-items, next) carry
  ZERO orchestration in SKILL.md beyond a one-line invocation of
  the wrapper script. All logic lives in
  `.claude-plugin/scripts/bin/<skill>.py`. This is the upstream
  thin-transport doctrine, enforced here.

## Persistent Agent Knowledge constraints

- The `.ai/<topic>.md` files MUST be referenced from `CLAUDE.md`
  and/or `AGENTS.md` (orphaned files are forbidden).
- `process-memos`'s `persistent-knowledge` disposition MUST create
  the `.ai/<topic>.md` file AND add the reference if missing in
  one atomic skill operation. A partial state (file written,
  reference missing) is a bug.
- Doctor's `memo-hygiene` invariant from `livespec` does NOT
  apply to dispositioned-into-store content; the `.ai/<topic>.md`
  files are durable-pending, not transient.

## Forbidden patterns

- No mutating CLI flags on `list-*` or `next` skills. These are
  query-only by contract; adding `--update` / `--write` / similar
  flags is a contract violation.
- No silent close of work-items. Every `status: closed` record
  MUST carry `resolution` and `reason` non-null; doctor catches
  violations.
- No memo deletion. `disposition: discard` is the only path for
  "do not act on this"; the memo stays on disk.
- No off-substrate persistence. State that doesn't go in the
  JSONL files (and the Spec Reader's read-only view of the spec
  tree) MUST be re-derivable from the on-disk substrate. Skills
  MUST NOT store sidecar JSON, sidecar SQLite, environment-
  variable state, or similar.

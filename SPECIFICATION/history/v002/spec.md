# spec.md — livespec-impl-plaintext

This is the natural-language specification for `livespec-impl-plaintext`,
the JSONL-backed implementation plugin for `livespec`. The plugin
dogfoods `livespec` — this `SPECIFICATION/` tree evolves through
`/livespec:seed` / `propose-change` / `revise` / `doctor` /
`prune-history` / `critique`, exactly the same lifecycle every consumer
project uses.

## Purpose

`livespec-impl-plaintext` is one realization of the abstract
implementation-plugin contract that `livespec` publishes in
`livespec/SPECIFICATION/contracts.md` §"Implementation-plugin
contract — the 9-skill surface". Other realizations exist on paper
(`livespec-impl-beads`, `livespec-impl-gitlab`, `livespec-impl-gascity`,
`livespec-impl-darkfactory-kilroy`) and are out of scope here. This
plugin's substrate is plain JSONL files committed alongside the
consumer project's other source code — no embedded database, no
external service, nothing the user can't read with `cat` or grep with
`git grep`. That property is the principal reason it is `livespec`'s
designated dogfood target.

## Scope boundary

The substrate is the only thing this spec describes that is unique to
the plugin. Everything else — the names of the nine skills, the
cross-boundary handoffs, the Spec Reader's required-capability surface,
the `compat` block format, the per-plugin Persistent Agent Knowledge
store realization slot — is FIXED by `livespec`'s published
contract. This `SPECIFICATION/` MUST NOT re-state `livespec`'s
contract; it MUST concretize the contract for the JSONL substrate and
point upstream for anything else.

When `livespec`'s contract changes, this plugin's `compat` block
pin moves forward in a discrete bump-pin PR (per `livespec`'s
pin-and-bump mechanism), at which point this `SPECIFICATION/` may
require companion revisions to honor the new surface. The current
pinned `livespec` reference is recorded in `.copier-answers.yml`
(`livespec_release_tag`) and in `.livespec.jsonc`'s
`livespec-impl-plaintext.compat` block.

## Terminology

This spec adopts every term defined in
`livespec/SPECIFICATION/spec.md` §"Terminology" verbatim
(Specification, Specification History, Work Items, Memos, Disposition,
Persistent Agent Knowledge, Gap, Gap-id, Origin, Spec Reader,
Transient, Durable-pending, etc.). The terms below are plugin-local
additions or refinements; they extend the upstream glossary, never
contradict it.

**JSONL record (work-item)** — One JSON object per line in the
work-items file. Schema is defined in `contracts.md` §"Work-items
JSONL record schema". Records are append-only: state transitions write
new records carrying the same `id`; the latest record by file order
wins. Closed records remain in the file as audit trail; deletion is
NEVER performed by skill code.

**JSONL record (memo)** — One JSON object per line in the memos file.
Schema is defined in `contracts.md` §"Memos JSONL record schema".
Same append-only discipline as work-items.

**Append-only file** — A file to which the plugin only appends new
lines; never edits, never truncates, never rewrites in place. The
append-only constraint exists so two concurrent skill invocations
can't corrupt each other's writes mid-stream; resolution of
conflicting concurrent appends is git's job, not the plugin's.

**Latest-record-wins reduction** — The materialized view of a
work-item or memo at any moment is the LAST record in the JSONL file
keyed by `id`. Earlier records remain present (for audit) but do not
contribute to current state.

**Persistent Agent Knowledge file** — A markdown file under
`.ai/<topic>.md` referenced from `CLAUDE.md` and/or `AGENTS.md` in the
consumer project. Per `contracts.md` §"Persistent Agent Knowledge
realization", `livespec-impl-plaintext` realizes the
upstream-mandated Persistent Agent Knowledge store as these files
plus the harness instruction files that load them progressively.

## Substrate properties

- Files live at paths configured in the consumer project's
  `.livespec.jsonc` under the `livespec-impl-plaintext` section.
  Default paths: `work-items.jsonl`, `memos.jsonl`, both at the
  project root. The defaults MAY be overridden via the configuration
  block.
- Files are git-tracked. Every skill that writes to them produces
  a commit (either inline or via the consumer's PR cycle). This is
  the audit trail.
- Files are UTF-8, one JSON object per line, terminated with `\n`.
  Empty lines are NOT permitted between records. A trailing newline
  after the last record is REQUIRED (POSIX text-file convention).
- The `latest-record-wins reduction` is computed lazily by reader
  code; nothing on disk reflects the materialized state separately.

## What this spec is not

- Not a re-statement of `livespec`'s contract. When in doubt,
  defer to `livespec/SPECIFICATION/`.
- Not a Python implementation manual. Implementation details live
  in code under `.claude-plugin/scripts/` (the wrapper layer for
  thin-transport skills) and in the SKILL.md prose for heavyweight
  skills.
- Not a substitute for the upstream invariant catalog. Doctor
  invariants that span the spec ⇆ impl boundary (per
  `livespec/SPECIFICATION/contracts.md` §"Doctor cross-boundary
  invariants") apply uniformly across all impl-plugins; this spec
  describes what the plugin offers, not what doctor enforces.

## Lifecycle and evolution

This `SPECIFICATION/` is governed by `livespec`. Changes land
through the standard livespec lifecycle:

- Propose: `/livespec:propose-change --spec-target SPECIFICATION/`
  drops a file under `proposed_changes/`.
- Critique: `/livespec:critique --spec-target SPECIFICATION/`
  surfaces issues before they ratify.
- Revise: `/livespec:revise --spec-target SPECIFICATION/`
  accepts, modifies, or rejects each pending proposal and snapshots
  a new `history/vNNN/`.
- Doctor: `/livespec:doctor --spec-target SPECIFICATION/` runs
  static + LLM-driven invariants.
- Prune: `/livespec:prune-history --spec-target SPECIFICATION/`
  collapses old history entries.

Every spec change MUST flow through this loop. Direct edits to the
top-level files outside a `revise` snapshot are out-of-process.

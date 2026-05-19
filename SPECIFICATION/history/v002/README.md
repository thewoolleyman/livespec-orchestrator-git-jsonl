# livespec-impl-plaintext — SPECIFICATION/

This directory holds the natural-language specification for
`livespec-impl-plaintext`, the JSONL-backed implementation plugin
for `livespec`. Per
`livespec/SPECIFICATION/non-functional-requirements.md`
§"Implementation plugin ecosystem", every `livespec-impl-*`
plugin dogfoods its own `SPECIFICATION/`; this is ours.

## Files

- [`spec.md`](spec.md) — intent, scope boundary, terminology, and
  substrate properties. The "what / why" surface.
- [`contracts.md`](contracts.md) — the 9-skill surface, the Spec
  Reader internal API, JSONL record schemas, `compat` block,
  cross-boundary handoffs. The wire-level surface.
- [`constraints.md`](constraints.md) — architecture-level rules
  (substrate, process boundaries, forbidden patterns). Mostly
  references upstream `livespec` non-functional requirements;
  enumerates plugin-local refinements only.
- [`scenarios.md`](scenarios.md) — end-to-end behavioral journeys
  illustrating cross-skill flows.
- [`proposed_changes/`](proposed_changes/) — pending propose-change
  files awaiting `/livespec:revise`.
- [`history/`](history/) — snapshot of each accepted revision.
  v001 is the initial baseline.

## What this spec governs

Only the JSONL substrate and how this plugin concretizes the
upstream contract. The 9-skill names, the Spec Reader's four
required capabilities, the cross-boundary handoff edges, the
`compat` block format, the persistent-knowledge slot — all are
FIXED by `livespec`. This `SPECIFICATION/` describes the
plugin-local realizations.

## Lifecycle

Evolve the spec through the standard livespec sub-commands:

- `/livespec:propose-change --spec-target SPECIFICATION/`
- `/livespec:critique --spec-target SPECIFICATION/`
- `/livespec:revise --spec-target SPECIFICATION/`
- `/livespec:doctor --spec-target SPECIFICATION/`
- `/livespec:prune-history --spec-target SPECIFICATION/`
- `/livespec:next --spec-target SPECIFICATION/`

Direct edits to the top-level files outside a `revise` snapshot
are out-of-process.

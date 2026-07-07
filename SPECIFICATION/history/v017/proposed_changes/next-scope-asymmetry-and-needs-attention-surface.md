---
topic: next-scope-asymmetry-and-needs-attention-surface
author: claude-opus-4-8
created_at: 2026-07-06T22:41:29Z
spec_commitments:
  impl_followups:
    - id_hint: needs-attention-thin-binding
      description: |
        Ship this plugin's `needs-attention` thin binding — a Markdown skill plus a JSON `bin/needs_attention.py` CLI — as a thin pass-through over the SHARED `livespec-runtime` compose function (the orchestrator-agnostic pure function both reference orchestrators reuse), gathering this plugin's own primitives (impl-side `next`, the `list-work-items` human-valve lanes, and a per-repo hygiene read) together with the spec-side `/livespec:next`, and normalizing them into the dedicated stateless, point-in-time attention shape (no timestamps/events/history). This is the OR3 code sub-slice; it is ALREADY tracked in the fleet's `needs-attention` epic ledger as work-item `bd-gj-8nh`, so this commitment is satisfied by that item and NO new work-item is owed by this propose-change.
---

## Proposal: Document the `next` scope-asymmetry and the `needs-attention` read/awareness surface

### Target specification files

- SPECIFICATION/contracts.md

### Summary

Document, in `SPECIFICATION/contracts.md` §"`next`", the `next` scope-asymmetry and the `needs-attention` read/awareness surface this plugin ships. The impl-side `next` is a pure `implement`-only ranker of dispatchable `ready` work that deliberately excludes the impl-side human valves (`pending-approval`, `acceptance`, `blocked`), whereas the spec-side `/livespec:next` includes human actions like `revise`; composing only the two `next`s is therefore an incomplete attention picture, and the wider composition belongs to `needs-attention` — the stateless, point-in-time per-repo read/awareness surface (Markdown skill + JSON CLI) that this plugin ships as a thin binding over the SHARED `livespec-runtime` compose function. Both docs are inserted as two paragraphs into the existing `#### next` subsection; no heading is added/changed/removed.

### Motivation

This is the GOVERNED-SPECIFICATION part of slice OR3 of the cross-repo `needs-attention` epic (anchored by the plan thread `plan/needs-attention/` in the `livespec` core repo; design record `plan/needs-attention/research/design.md`). The design extracts "what needs attention" into a first-class reusable read surface (`needs-attention`) that both reference orchestrators ship as a thin binding over a SHARED `livespec-runtime` compose function, and documents the `next` scope-asymmetry "so no one rebuilds the incomplete two-`next` composition" (design record §"Why the two `next` primitives are NOT mis-designed"). This git-jsonl slice is REDUCED relative to the beads-fabro orchestrator: git-jsonl ships no `orchestrate`/`drive` operator surface (so there is no `orchestrate`→`drive` rename) and no `plan/` thread store (so there is no `list-plan-threads` primitive) — per the design record's Rollout bullet, git-jsonl gets only the `needs-attention` thin binding plus the (reduced) `next` scope-asymmetry documentation. Spec-first ordering: the contract text documents the surface before/as the thin binding is built (the OR3 code sub-slice, tracked as `bd-gj-8nh`), so building the binding first would create impl→spec drift that `capture-spec-drift` would flag.

### Proposed Changes

All target text below is quoted verbatim from the live `SPECIFICATION/contracts.md` at branch `needs-attention-or3-spec` (off `origin/master`). This proposal makes ONE insertion into the existing `#### next` subsection of `SPECIFICATION/contracts.md`; it adds, changes, or removes NO `## ` (H2) or `### ` (H3) heading, so `tests/heading-coverage.json` (which enumerates H2 headings only) needs NO co-edit.

**A. Insert the `next` scope-asymmetry and `needs-attention` surface paragraphs — `SPECIFICATION/contracts.md` §"`next`".** Immediately AFTER the paragraph that ends the `#### next` subsection body — quoted verbatim:

> When `offset >= total`, the wrapper MUST emit `candidates: []`
> and `has_more: false`. The wrapper MUST always emit a valid
> (possibly empty) `candidates` array.

— and immediately BEFORE the `##### Layer 3 discoverability nudge — not applicable under v089 recast` H5 sub-subsection, the following two paragraphs MUST be inserted:

```markdown
**Scope asymmetry with the spec-side `next`.** This impl-side `next` is a pure ranker of *dispatchable `ready` work* — its only `action` type is `implement`, and it deliberately EXCLUDES the impl-side human valves: items resting at `pending-approval` (awaiting a human approval), at `acceptance` (awaiting the human leg of an acceptance decision), or at `blocked` (awaiting a human to clear the block). The spec-side `/livespec:next`, by contrast, includes human actions (e.g. `revise`). This asymmetry is correct per each primitive's job and MUST be preserved. Its consequence: composing ONLY the two `next` outputs (spec-side plus impl-side) yields an INCOMPLETE attention picture — it misses the impl-side human valves. A complete "what needs attention" view therefore composes a WIDER primitive set (the human-valve lanes via `list-work-items`, plus per-repo hygiene) in the read/awareness surface (`needs-attention`), NOT here. No caller SHOULD rebuild the incomplete two-`next` composition: the composition role belongs to the awareness surface, and `next` MUST remain a pure `implement`-only ranker.

**The `needs-attention` read/awareness surface.** The wider composition named above is the job of `needs-attention`, the per-repo read/awareness surface this plugin ships as a thin binding — a Markdown skill for humans and a JSON CLI for machines — over the SHARED `livespec-runtime` compose function, an orchestrator-agnostic pure function both reference orchestrators reuse so the composition logic is single-sourced rather than re-implemented per plugin. `needs-attention` is **stateless / point-in-time**: it answers exactly one question — *"what needs attention right now"* — over current state (the work-items JSONL store, the spec tree, and per-repo hygiene), with NO timestamps, events, or history; any event-sourcing or snapshot diffing belongs to the Control-Plane console that consumes `needs-attention` snapshots, never to this surface. It re-detects nothing of its own: it delegates to the cohesive primitives (spec-side `/livespec:next`, this plugin's impl-side `next` and `list-work-items`, plus a per-repo hygiene read) and normalizes their findings into one dedicated attention shape. This subsection documents the surface at forward-reference altitude; its full CLI contract and skill-inventory inclusion land together across the reference orchestrators in a coordinated slice of the `needs-attention` epic.
```

**Reduced scope (git-jsonl).** Unlike the beads-fabro orchestrator's analogous spec change, this proposal deliberately does NOT rename any operator surface (git-jsonl ships no `orchestrate`/`drive` surface) and does NOT add a `list-plan-threads` primitive (git-jsonl has no `plan/` thread store). It documents only (1) the `next` scope-asymmetry and (2) the `needs-attention` surface at forward-reference altitude — matching the lead orchestrator's current altitude (`livespec-orchestrator-beads-fabro` documents `needs-attention` as a forward reference, not yet a counted skill). The full `needs-attention` CLI contract and its skill-inventory inclusion land in a coordinated cross-repo slice, not here; the `#### next` subsection is an H4, so no `## The seven-skill surface` count is touched and no heading-coverage entry changes.

**Drift sweep.** The existing `#### next` cross-reference stating that "cross-side composition of impl-side `next` with spec-side `/livespec:next` is a Layer 3 (project-local orchestration) concern," and the later "empty-queue handoff ... is a Layer 3 (project-local orchestration) concern" sentence, are LEFT INTACT: `needs-attention` is an ADDITIVE read/awareness composer (it does not move where `next`-ranking composition lives, and `next` still bakes in no cross-side weighting), so the insertion introduces no contradiction. A fuller reconciliation of git-jsonl's Layer-2/Layer-3 framing with the `needs-attention` model is out of this reduced slice's scope. No other statement in `contracts.md`, `spec.md`, `constraints.md`, or `scenarios.md` contradicts the insertion.

**Spec→impl commitment.** The `needs-attention` thin binding this surface doc documents is the OR3 code sub-slice, already tracked in the fleet's `needs-attention` epic ledger as work-item `bd-gj-8nh`; the `spec_commitments` block records this so no NEW work-item is owed by this propose-change.

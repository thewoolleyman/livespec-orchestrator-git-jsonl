# L1b — overview and read-first chain

This is the **`livespec-orchestrator-git-jsonl` (L1b)** track of the
fleet-wide **work-item-lifecycle** epic — the deterministic work-item
state machine. L1b migrates this repo's JSONL realization to the new
shared schema; its **code gates on the L0 release** (livespec-runtime
v0.5.0, already shipped).

- **Ledger anchor (this repo's tenant):** epic **`bd-gj-45liqm`**
  (`livespec-orchestrator-git-jsonl` beads tenant). This repo tracks its
  OWN work-items in beads via the `livespec-orchestrator-beads-fabro`
  orchestrator (decision 37); only its tests/acceptance exercise the
  JSONL backend.
- **Fleet anchor (prose reference, NOT a typed cross-tenant
  `depends_on`):** `livespec-35s3zo` in the livespec core tenant
  (decisions 41/44/45 — a cross-tenant id would dangle in the flat
  same-tenant id list and pollute the `blocked:dependency` derivation).
- **Branch / worktree for the thread:** `wism-plan-thread`.

## Autonomy posture (this track)

Maintainer is ASLEEP; full autonomous wrap-up authorized. The design is
LOCKED (decisions 1–46), so this track **AUTO-PROCEEDS through its
`revise` + `groom` gates per the locked design** — it does NOT pause for
approval. Halt + report ONLY on a genuine blocker or a new decision the
design does not resolve. (This is the one posture difference from the L0
overview, which held those gates for the maintainer.)

## The reframe (load-bearing finding)

This redesign is **overwhelmingly a `livespec-runtime` + orchestrator
change; livespec CORE's own spec is barely touched** (decision 44).
CORE's `SPECIFICATION/` explicitly delegates the entire lifecycle /
schema surface to the orchestrators as NON-normative. So the L1b
contract lands in **THIS repo's `SPECIFICATION/contracts.md`**, not in
CORE. The epic stays *anchored* in core, but core is the anchor, not
the work site.

## Read-first chain (cold-start)

Read in order, then execute the next action in `../handoff.md`:

1. **This file** — the slice, the anchor, the reframe, the autonomy posture.
2. `01-spec-delta.md` — the exact `SPECIFICATION/contracts.md` delta
   (the propose-change payload, human-readable) + the heading-coverage
   reasoning. The `revise` gate (auto-ratified) lands this.
3. Cross-repo design of record (already on disk, authoritative):
   - `/data/projects/livespec/plan/work-item-state-machine/research/02-design.md`
     (§2 states, §3 `lane_of`, §5 `rank`, §6 schema — esp. the
     "Backend mapping" git-jsonl column + consequence (d))
   - `/data/projects/livespec/plan/work-item-state-machine/research/03-decision-log.md`
     (decisions 1–46; authoritative on any conflict)
   - `/data/projects/livespec/plan/work-item-state-machine/research/04-slice-plan.md`
     (the "L1b — livespec-orchestrator-git-jsonl" section)
   - `/data/projects/livespec-runtime/plan/work-item-state-machine/handoff.md`
     (the L0 worked example: propose-change → revise → groom → implement →
     release, end-to-end)

## The L1b slice (what lands in this repo)

**Spec** (propose-change → `SPECIFICATION/contracts.md`; see `01`):
- `## Work-items JSONL record schema` — 16 → 17 keys (`+ rank`,
  `− priority`); the `status` enum prose
  (`open/in_progress/blocked/closed/deferred`) → the 7 livespec states
  (`backlog, pending-approval, ready, active, acceptance, blocked, done`).
- Reconcile the downstream prose that referenced the dropped `priority`
  / old status enum: `#### next` ranking (priority → rank), the
  `#### list-work-items` `--filter` lane prose, `#### capture-work-item`
  (priority → create position), and the `urgency` derivation.
- **No `## ` (H2) heading is added/changed/removed**, so
  `tests/heading-coverage.json` needs **no co-edit** (the check tracks H2
  only; `## Work-items JSONL record schema` already has a row).

**Code** (this repo; gates on the L0 v0.5.0 release):
- Re-vendor / re-pin `livespec_runtime` v0.4.0 → **v0.5.0** (adds
  `work_items/{lifecycle,rank,_fractional_indexing}.py`; rebuilds
  `types.py` to the 7-state + `rank` shape; ships `BOTTOM_SENTINEL`).
- `store.py` — required-keys (17) + `rank` + the **bottom-sentinel
  adapter** for rank-less legacy lines (reads `rank` absent →
  `livespec_runtime.work_items.rank.BOTTOM_SENTINEL`); status validated
  against the vendored 7-state `WorkItemStatus`.
- `commands/next.py` — `_sort_key` lead key `priority → rank` (then `id`
  tie-break); `urgency` re-expressed off the new shape.
- Tests + the golden-master + e2e-cli fixtures updated to the new schema.

**Gate:** cut a `livespec-orchestrator-git-jsonl` release — the artifact
the L2 migration consumes.

## Dogfooding order

propose-change → revise (auto-ratify) → groom (auto-cut) → implement
(red-green-replay) → cut a release. Every change via worktree → PR →
rebase-merge; `mise exec -- git`; never `--no-verify`; halt + report on
any hook failure.

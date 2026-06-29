# Handoff — work-item-state-machine (L1b, livespec-orchestrator-git-jsonl)

**Thread:** `plan/work-item-state-machine/` · **Ledger anchor:** epic
`bd-gj-45liqm` (`livespec-orchestrator-git-jsonl` beads tenant) ·
**Fleet anchor (prose ref):** `livespec-35s3zo` (livespec core tenant).

> Status is **derived from the ledger**, never stored here. To read it:
> ```bash
> with-livespec-env.sh bd show bd-gj-45liqm
> with-livespec-env.sh bd children bd-gj-45liqm --json   # the groomed slices
> ```
> (`with-livespec-env.sh` injects the tenant password; run from this repo
> root so `bd` resolves `.beads/config.yaml`.)

## Autonomy posture

Maintainer ASLEEP; full autonomous wrap-up authorized; design LOCKED
(decisions 1–46). **AUTO-PROCEED through `revise` + `groom` per the
locked design** — do NOT pause for approval. Halt + report ONLY on a
genuine blocker or a new decision the design does not resolve. Report at
each milestone.

## Read-first chain (cold-start)

1. `research/00-l1b-overview.md` — the slice, the anchor, the reframe,
   the autonomy posture, and the full read-first chain (incl. the
   cross-repo design of record + the L0 worked example).
2. `research/01-spec-delta.md` — the drafted `contracts.md` delta (the
   propose-change payload, human-readable).

## State as of this handoff

- ✅ Epic `bd-gj-45liqm` anchored (prose-linked to `livespec-35s3zo`; no
  typed cross-tenant `depends_on`).
- ✅ Thread created; `00-l1b-overview.md` + this handoff committed.
- ⏳ L0 dependency: livespec-runtime **v0.5.0** is RELEASED (tag
  `dda6a40`) — the artifact this track re-vendors. Code is unblocked.

## Next action (ONE path)

Re-vendor `livespec_runtime` v0.4.0 → v0.5.0 (`.vendor.jsonc` +
`.claude-plugin/scripts/_vendor/livespec_runtime/` source tree + the
verbatim-port pyproject gate exclusions + a `NOTICES` line), then run the
L1b dogfooding order end-to-end per `research/00-l1b-overview.md`
"The L1b slice": propose-change `SPECIFICATION/contracts.md` (schema
16→17 keys: `+rank`, `−priority`; status-enum → the 7 states) → revise
(auto-ratify) → groom (auto-cut the epic into ready children) →
implement (red-green-replay: `store.py` required-keys + `rank` +
bottom-sentinel adapter; `commands/next.py` `_sort_key` priority→rank;
tests + golden-master + e2e-cli fixtures) → cut an L1b release.

## Discipline (non-negotiable)

- Every change via **worktree → PR → rebase-merge**; `mise exec -- git …`;
  **never `--no-verify`**; halt + report on any hook failure.
- Product `.py` follows this repo's **red-green-replay** ritual.
- Co-edit `tests/heading-coverage.json` for any `## `-heading change
  (this slice changes NO H2 heading, so no co-edit is required).
- Operate only in worktrees you create.

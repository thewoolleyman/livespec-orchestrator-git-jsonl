# Handoff — local-model-acceptance-tier (livespec-orchestrator-git-jsonl) — 🟡 NOT STARTED

**Thread:** `plan/local-model-acceptance-tier/` · **Ledger anchor:** epic
**TO BE FILED** in the `livespec-orchestrator-git-jsonl` beads tenant
(`bd-gj-*` prefix) — see FIRST ACTION. **Cross-plane ref:** core's
deferred option `local-bundled-model-e2e` (livespec v014 N9-D1).

> Status is **derived from the ledger**, never stored here. Once the epic
> is filed, read it live:
> ```bash
> with-livespec-env.sh bd show <epic-id>
> with-livespec-env.sh bd children <epic-id> --json   # the groomed slices
> ```
> (`with-livespec-env.sh` injects the tenant password; run from this repo
> root so `bd` resolves `.beads/config.yaml`.) Ranked next impl action:
> `/livespec-orchestrator-beads-fabro:next`.

## Purpose

Give `livespec-orchestrator-git-jsonl` a **local, offline, no-API-key
model executor tier** for acceptance testing: implement the
`hello-world-greets-a-name` fixture with a real (tiny) model so the
`spec → prompt → model → parse → write → run → verify` pipeline is
actually exercised — the missing rung between the hardcoded tautology
(`test_git_jsonl_golden_master.py`, proves nothing) and the mock CLI
round-trip (`test_cli_e2e_round_trip.py`, prompt-blind), and below the
gated real-model capability E2E. Full rationale + the LOCKED decisions
D1–D9 are in `research/design.md`; read it before acting.

This doc is the single resumable entry point — a fresh session should be
able to execute the NEXT ACTION from this file alone (via the read-first
chain), no chat history required.

Repo: `thewoolleyman/livespec-orchestrator-git-jsonl`
(host checkout `/data/projects/livespec-orchestrator-git-jsonl`).

## Autonomy posture

Fresh plan; **no standing auto-accept authorization exists for this
track.** Surface gates until the maintainer grants one. The design is
LOCKED (D1–D9 in `research/design.md`) — proceed through anchor + groom +
dispatch of the pre-authorized slices without re-litigating settled
decisions, but HALT + report on: a new decision the design does not
resolve, any spec ratification, or any irreversible/outward-facing act.
"Done means exercised live" applies (§ Standing disciplines).

## NEXT ACTION (execute from this file alone)

**FIRST ACTION — anchor the epic + file the slices** (not yet done):

1. Anchor a ledger epic in the `bd-gj` tenant:
   *"local-model acceptance smoke tier — a real tiny local model
   implements the hello-world fixture offline, no API key"* — prose-link
   to core's `local-bundled-model-e2e` deferred option; no typed
   cross-tenant `depends_on`.
2. File the six proposed slices below as `ready` children, with the
   `depends_on` layering shown. Confirm slicing with the maintainer if
   any cut is a real judgment call; the cuts below are drafted, not yet
   maintainer-ratified.
3. Then dispatch the ready, non-conflicting slices (S1/S2 have no
   inter-dep and may run in parallel). Sequence only genuine file
   conflicts.

### Proposed slices (draft — ratify before filing)

- **S1 — `Executor` port + `LocalModelExecutor` (single-shot).**
  Define the minimal `Executor` port (`spec/prompt → produce program →
  status`) and a `LocalModelExecutor` that shells to the pinned local
  runtime, single-shot (D2, D7). *Product `.py` → Red-Green-Replay.*
- **S2 — model fetch / cache / verify plumbing.** Pinned llamafile (or
  `ollama pull`), hash-verified, cached OUTSIDE the repo; offline at test
  run time; a `skip-if-unavailable` helper for the pytest tier (D5, D6).
  *`.py` + shell/config.* No inter-dep with S1.
- **S3 — prompt assembly from the fixture SPECIFICATION + response
  extraction.** Build the prompt from
  `acceptance/fixtures/hello-world-greets-a-name/SPECIFICATION/` (never
  hardcoded, D9); strip markdown fences/prose → program text. Shared with
  the real launchers (D7). *Product `.py`.* Depends on S1.
- **S4 — `just e2e-test-local-model` + pytest binding.** New target NOT
  in `just check` (D8); pytest SKIPS loudly when the model is uncached;
  greedy/temp-0 + fixed seed (D4); behavior-assert `greet("Ada") ==
  "Hello, Ada!"` (D3); a repeated-run determinism guard. *Product `.py`
  + justfile.* Depends on S1, S2, S3.
- **S5 — CI wiring (alternate cadence).** A CI job (merge-queue / master
  push / `workflow_dispatch`) that fetches the model then runs
  `e2e-test-local-model`; kept OUT of per-commit `just check`; a fetch
  failure FAILS the job (never a silent skip) (D8). *CI config.* Depends
  on S4.
- **S6 — tier-ladder doc + honest labeling.** Document the ladder
  (tautology → mock → local-model smoke → gated real-model E2E) in the
  repo's testing notes (e.g. a `tests/e2e-cli/CLAUDE.md`-style note or
  README testing section); label tier 3 a SMOKE tier, NOT capability
  (D1). Route a note upstream reconciling core's `local-bundled-model-e2e`
  deferred option. *Docs (+ spec touch only if a contract actually
  changes — then `tests/heading-coverage.json` co-edit + independent
  Fable review before ratification).* Can run in parallel; land last.

## Read-first chain (open these, in order, before acting)

1. **THIS handoff.**
2. `research/design.md` — the problem, the tier ladder, the LOCKED
   decisions D1–D9, and the honest limits.
3. `live-adversarial-review-prompt.md` — the attack points a second
   session uses to keep the driver honest (the "green-because-skipped"
   trap, tautology-at-the-prompt-layer, determinism proof, etc.).
4. The live ledger epic (once filed) + `/livespec-orchestrator-beads-fabro:next`.
5. The code this tier sits above / beside:
   `acceptance/test_git_jsonl_golden_master.py`,
   `.claude-plugin/scripts/livespec_orchestrator_git_jsonl/acceptance.py`
   (the `_PROGRAM_TEXT` tautology + `run_acceptance`),
   `tests/e2e-cli/test_cli_e2e_round_trip.py` (the prompt-blind mock).
6. The sibling precedent for a gated real acceptance tier:
   `../../../livespec-orchestrator-beads-fabro/acceptance/test_beads_fabro_live_golden_master.py`
   + its `run_live_acceptance` + `just acceptance-live-golden-master`.

## What is DONE (context — do NOT redo)

- Nothing implemented yet. This thread + its `design.md` +
  `live-adversarial-review-prompt.md` are the only artifacts; they land
  via worktree → PR (docs-only).

## Standing disciplines (apply throughout)

- **Repo mutation:** worktree → PR → rebase-merge → cleanup; always
  `mise exec -- git …`; NEVER `--no-verify`; halt + report on hook
  failure. Product `.py` (S1/S3/S4) uses the **Red-Green-Replay** ritual
  (genuine failing-assertion Red — stub the new module so the test runs
  and FAILS rather than ImportErrors — then Green amend; the hook reads
  the ON-DISK module).
- **Done means exercised live.** No slice is "done" on merge + CI-green
  alone: run `just e2e-test-local-model` against a real cached model and
  journal the evidence (the runtime process actually launched, its
  output, the passing behavior assert). A skipped tier is NOT evidence.
- **Secrets probe-only** (`printenv NAME | wc -c`); beads via the
  credential wrapper. No model weights or tokens committed.
- **Independent Fable review before any spec ratification** (only S6, and
  only if it changes a contract); a heading change co-edits
  `tests/heading-coverage.json`.
- **No local memory** for durable guidance — use `AGENTS.md` / `.ai/` if
  any durable note is warranted.

## Clean state at handoff

Thread created; `design.md` + this handoff + `live-adversarial-review-prompt.md`
authored, landing via worktree → PR (docs-only, `docs(plan):`). No ledger
epic filed yet (FIRST ACTION). No implementation slices exist. Verify no
orphaned worktrees + the primary checkout current on `origin/master` at
session end.

# Handoff — make-git-jsonl-real (livespec-orchestrator-git-jsonl) — 🟡 NOT STARTED

**Thread:** `plan/make-git-jsonl-real/` · **Ledger anchor:** epic **TO BE
FILED** in the `livespec-orchestrator-git-jsonl` beads tenant (`bd-gj-*`
prefix) — see FIRST ACTION.

> Status is **derived from the ledger**, never stored here. Once the epic
> is filed, read it live:
> ```bash
> with-livespec-env.sh bd show <epic-id>
> with-livespec-env.sh bd children <epic-id> --json
> ```
> (`with-livespec-env.sh` injects the tenant password; run from this repo
> root so `bd` resolves `.beads/config.yaml`.) Ranked next impl action:
> `/livespec-orchestrator-beads-fabro:next`.

## Purpose

Make `livespec-orchestrator-git-jsonl` a **real orchestrator**: today it
ships a JSONL substrate + per-item skills but has **no loop, no executor,
and no real verification** — it can't drive work, and its top acceptance
test is a tautology. This epic gives it a deterministic **serial `drive`
loop** with a **pluggable, observable executor**, plus the **test tiers**
that prove the loop works — reaching functional parity with the sibling
`livespec-orchestrator-beads-fabro` on the axes that matter, **WITHOUT
reinventing its factory** (no sandboxes, no parallelism, no
auto-resolving valves, no cost machinery). Full rationale + LOCKED
decisions **D1–D14** are in `research/design.md`; read it before acting.

This doc is the single resumable entry point — a fresh session should be
able to execute the NEXT ACTION from this file alone (via the read-first
chain), no chat history required.

Repo: `thewoolleyman/livespec-orchestrator-git-jsonl`
(host checkout `/data/projects/livespec-orchestrator-git-jsonl`).

## Autonomy posture

Fresh plan; **no standing auto-accept authorization exists.** Design is
LOCKED (D1–D14). Proceed through anchor + groom + dispatch of
pre-authorized slices without re-litigating settled decisions, but HALT +
report on: a new decision the design does not resolve, any spec
ratification (Phase 5), or any irreversible/outward-facing act. "Done
means exercised live" applies (§ Standing disciplines).

## NEXT ACTION (execute from this file alone)

**FIRST ACTION — anchor the epic + file the phased slices** (not yet
done):

1. Anchor a ledger epic in the `bd-gj` tenant: *"make git-jsonl a real
   orchestrator — deterministic serial drive loop + observable pluggable
   executor + real test tiers (loop, not a factory)."* Prose-link, no
   typed cross-tenant `depends_on`.
2. File the slices below as `ready` children with the `depends_on`
   layering shown. Confirm any judgment-call cut with the maintainer; the
   cuts are drafted, not yet ratified.
3. Dispatch ready, non-conflicting slices; sequence only genuine file
   conflicts. Phases are ordered by dependency, but independent slices
   within a phase may run in parallel.

### Phased slice plan (draft — ratify before filing)

**Phase 1 — the loop + first executor** (the spine)
- **S1 — `Executor` port.** The abstraction: `(work-item, spec) → produce
  implementation → pass/fail status`, plus the shared prompt-assembly +
  response-extraction seam (D6). *Product `.py`.*
- **S2 — `drive.py` loop + thin `drive` SKILL.md.** select (`next`) →
  execute → gate (`just check` + `/livespec:doctor`) → close (merge-
  evidence, append) → advance/stop; valves = hard stops (D1–D3).
  *Product `.py` + SKILL.md.* Depends on S1.
- **S3 — `claude -p` headless launcher adapter.** The primary supported
  runtime, behind the S1 port (D6). *Product `.py`.* Depends on S1.

**Phase 2 — observability** (the operator-trust layer, D4/D5)
- **S4 — live stream + per-item run dir.** Tee the runtime event stream
  to console + `transcript.jsonl`/`diff.patch`/`gate.log`/`status.json`.
  *Product `.py`.* Depends on S2/S3.
- **S5 — status heartbeat + escalation channel.** Per-item phase line;
  non-interactive contract → STOP-and-emit escalation → loop pauses +
  surfaces (pause-and-handoff). *Product `.py`.* Depends on S2.
- **S6 — budget guards + gate-backstop proof.** Turn/time caps → kill →
  `blocked` → surface; a test proving the executor cannot close/merge.
  *Product `.py`.* Depends on S2.

**Phase 3 — multi-runtime + config**
- **S7 — `.livespec.jsonc` `executor` block + `codex exec` launcher.**
  Runtime selection over the orchestrator's own packaging set (D7); the
  Codex adapter behind the S1 port. Launcher stays in THIS plugin, NOT the
  Driver repos (D8). *Product `.py` + config.* Depends on S1/S3.

**Phase 4 — real test tiers** (prove it's real)
- **S8 — `LocalModelExecutor` + local-model smoke tier.** Adapter behind
  S1 (single-shot); `just e2e-test-local-model` (off `just check`); model
  fetch-cache-verify (weights NOT in git); prompt from the fixture
  SPECIFICATION; behavior-assert; greedy + pinned; skip-loud + CI
  fail-on-fetch-miss (D9). *Product `.py` + justfile + CI.* Depends on
  S1/S6.
- **S9 — integration tier.** Drive the real `drive.main([...])` against
  the real JSONL store with only the executor leaf mocked (the beads-fabro
  `tests/integration/` analog); runs in `just check` (D10). *Product
  `.py`.* Depends on S2–S6.
- **S10 — gated real full-lifecycle acceptance + tier-ladder doc.** A
  `run_live_acceptance` binding + `just acceptance-live-*` operator flow
  (keyed on `ANTHROPIC_API_KEY`) that drives the WHOLE loop on the
  hello-world fixture; honestly relabel the tautology; document the tier
  ladder (D11). *Product `.py` + shell + docs.* Depends on S2–S8.

**Phase 5 — contract**
- **S11 — spec the loop.** Constrain the `drive` invocation surface, the
  Executor port contract, the observability guarantees, and the tier
  ladder in `SPECIFICATION/` — architecture, not mechanism (D13).
  Independent Fable review before ratification; `tests/heading-coverage.json`
  co-edit for any `## ` change. *Spec.* Depends on Phases 1–4 landing.

## Read-first chain (open these, in order, before acting)

1. **THIS handoff.**
2. `research/design.md` — thesis, the "not a factory" boundary, the
   three-layer architecture, the loop, observability, the tier ladder,
   and LOCKED decisions D1–D14.
3. `live-adversarial-review-prompt.md` — the attack points a second
   session uses to keep the driver honest across ALL layers (control-plane
   determinism, "not a factory" creep, escalation actually pausing, the
   local-model traps, live-exercise evidence).
4. The live ledger epic (once filed) + `/livespec-orchestrator-beads-fabro:next`.
5. The sibling shapes to lift (minus fabro/beads):
   `../../../livespec-orchestrator-beads-fabro/.claude-plugin/scripts/livespec_orchestrator_beads_fabro/commands/dispatcher.py`,
   `../../../livespec-orchestrator-beads-fabro/tests/integration/`,
   `../../../livespec-orchestrator-beads-fabro/acceptance/test_beads_fabro_live_golden_master.py`.
6. What git-jsonl has today (build ON these): the `implement`, `next`,
   `list-work-items` skills; the tautology + mock
   (`acceptance/test_git_jsonl_golden_master.py`,
   `.claude-plugin/scripts/livespec_orchestrator_git_jsonl/acceptance.py`,
   `tests/e2e-cli/test_cli_e2e_round_trip.py`).

## What is DONE (context — do NOT redo)

- Nothing implemented. This thread + `design.md` +
  `live-adversarial-review-prompt.md` are the only artifacts; they land
  via worktree → PR (docs-only).

## Standing disciplines (apply throughout)

- **Repo mutation:** worktree → PR → rebase-merge → cleanup; always
  `mise exec -- git …`; NEVER `--no-verify`; halt + report on hook
  failure. Product `.py` uses the **Red-Green-Replay** ritual (genuine
  failing-assertion Red via a stub module, then Green amend; the hook
  reads the ON-DISK module).
- **Done means exercised live.** Loop-behavior slices require a real
  `drive` run journaled; the local-model tier requires a real model run
  (not a skip). Merge + CI-green is not "done".
- **Not a factory (D1).** Reject any sandbox / parallelism / cost /
  auto-valve creep. Serial, in-process/headless only.
- **Secrets probe-only** (`printenv NAME | wc -c`); beads via the
  credential wrapper. No weights or tokens committed.
- **Independent Fable review before any spec ratification** (Phase 5);
  heading changes co-edit `tests/heading-coverage.json`.
- **No local memory** for durable guidance — use `AGENTS.md` / `.ai/`.

## Clean state at handoff

Thread created; `design.md` + this handoff + `live-adversarial-review-prompt.md`
authored, landing via worktree → PR (docs-only, `docs(plan):`). No ledger
epic filed yet (FIRST ACTION). No implementation slices exist. Verify no
orphaned worktrees + the primary checkout current on `origin/master` at
session end.

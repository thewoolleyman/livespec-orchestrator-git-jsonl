# Design — make-git-jsonl-real (livespec-orchestrator-git-jsonl)

The reasoning of record for the thread. `handoff.md` is the resumable
entry point; this file is the "why". Design is LOCKED at decisions D1–D14
below; deviations require a new decision recorded here.

## Thesis — what "real" means

`livespec-orchestrator-git-jsonl` today ships a **substrate** (JSONL
work-items) and **per-item skills** (`capture-*`, `next`, `list-work-items`,
`implement`) — but it has **no loop, no executor, and no real
verification**. Consequences established in the design conversation:

- It cannot drive work; a human (or an outer loop that does not exist
  here) must invoke `implement` by hand, one item at a time.
- Its `next` emits only a **dispatch signal** (rank order); nothing
  consumes it.
- Its top-of-pyramid acceptance test is a **tautology** — it writes a
  hardcoded `Hello, {name}!` and asserts it, touching zero orchestrator
  code. The mid-tier CLI "e2e" is a **prompt-blind mock**. So nothing
  proves the orchestrator actually works end to end.

**Making it real** = give it a deterministic **serial `drive` loop** with
a **pluggable, observable executor**, and the **test tiers** that prove
the loop works — reaching functional parity with the sibling
`livespec-orchestrator-beads-fabro` on the axes that matter, WITHOUT
reinventing its factory.

## What this is NOT — deliberately not a factory

The whole point of git-jsonl is the low-infra, legible, attended-capable
path. So this epic explicitly does **NOT** build (these are what make
beads-fabro a 2,600-line factory, and they are out of scope):

- **No docker sandboxes** — the executor runs as a headless subprocess
  (or in-session), never a container; the host owns the git state.
- **No parallelism** — serial, one work-item at a time. (`merge=union`
  already makes the store safe for a *future* parallel driver, but we do
  not build one.)
- **No auto-resolving admission/acceptance valves** — the human-decision
  valves (`pending-approval` / `acceptance` / `blocked`) are **hard stops
  that surface**, never LLM-auto-resolved. Auto-resolving them IS the
  factory; we don't.
- **No cost-observability / calibration machinery**, no OTel endpoints,
  no beads/Dolt.

git-jsonl becomes real as a **loop, not a factory**: the deterministic
serial dispatcher and nothing heavier.

## Architecture — three layers

1. **The loop** (`drive.py` + a thin `drive` SKILL.md) — runtime-agnostic,
   deterministic. Owns select → gate → close → advance/stop. Calls the
   Executor port; never reads the agent's reasoning.
2. **The Executor port + per-runtime launchers** — `claude -p`,
   `codex exec`, future `pi`, and `local-model` (for the test tier).
   Config-selected via `.livespec.jsonc`. Lives **in the orchestrator
   plugin** (NOT the Driver repos — see D8).
3. **The payload** — the existing `implement` skill, unchanged. Once
   launched, the agent runs it.

Only `livespec_runtime`'s pure functions (`is_item_ready`,
`ready_sort_key`) are shared with beads-fabro; git-jsonl supplies its own
execution adapter (serial/in-place) alongside beads-fabro's (fabro/
parallel). The shared runtime is NOT dual-purposed — this is
ports-and-adapters, the pattern already in use.

## The deterministic loop

Per item: **select** (`next`, pure, no LLM) → **execute** (the one
irreducible LLM boundary) → **gate** (`just check` + `/livespec:doctor`,
branch on exit code) → **close** (verify merge-evidence, append the
closed record) → **advance or stop**. Everything except execute is plain
code. Valves are hard stops that halt + surface.

## Observability — the load-bearing concern

"Black-box" is about **control coupling** (the loop doesn't trust the
agent's judgment), NOT visibility. The executor is fully observable:

- **Live stream** — tee the runtime's structured event stream
  (`claude -p --output-format stream-json`, `codex exec` equivalent) to
  console + a per-item log, in real time.
- **Per-item run dir** — `transcript.jsonl` + `diff.patch` + `gate.log` +
  `status.json`; an audit trail (analog of the beads-fabro dispatcher's
  iteration journal).
- **Status heartbeat** — each item's phase (`queued` / `executing[turn N,
  last tool]` / `gating` / `closed` / `escalated`).
- **Escalation channel** — the executor runs under a strict
  **non-interactive contract**: never ask a human; on a genuine blocker,
  STOP and emit a structured escalation. The loop **pauses that item and
  surfaces it** (pause-and-handoff, not live-attach — a one-shot
  `claude -p` cannot be attached to like a fabro sandbox). Serial → one
  escalation at a time.
- **Budget guards** — turn / time caps; on blowout, kill → mark
  `blocked` → surface.
- **Gate backstop** — the agent **cannot close or merge**; the
  deterministic gate runs in the loop's control. Worst case is a failed
  gate + a halt for review, never a bad merge.

This maps the two operator worries directly: a **human question** →
escalation pause; **tool errors** → visible in the stream + bounded by
budgets + non-destructive behind the gate.

## Verification — making "real" testable (the tier ladder)

| Tier | Proves | Runs |
|---|---|---|
| 1. Hermetic tautology (hardcoded) | nothing | per-commit gate |
| 2. Mock CLI round-trip | CLI/skill wiring; prompt-blind | per-commit |
| **3. Local-model smoke tier (NEW)** | a real tiny model closes `spec→prompt→model→parse→write→run→verify` offline, no secret; catches prompt/transport/extraction bugs 1–2 can't | alt cadence |
| **4. Integration tier (NEW)** | the real `drive.main([...])` loop behavior against the real JSONL store, executor leaf mocked (the beads-fabro dispatcher-integration analog, minus fabro) | per-commit (`just check`) |
| **5. Gated real full-lifecycle (NEW)** | a real agent implements the fixture through the WHOLE loop + merge (the `run_live_acceptance` / live-golden-master analog) | operator-gated, needs API key |

Tiers 3–5 are what make the orchestrator provably real. They exist in
beads-fabro (16-file integration suite + live golden-master); git-jsonl
lacks them today **because it has no loop to drive** — building the loop
(layers 1–2 above) is the prerequisite that unlocks tier 4 and 5.

## Locked decisions

- **D1 — Loop, not a factory.** No sandboxes, no parallelism, no
  auto-resolving valves, no cost machinery. Serial only.
- **D2 — Deterministic control plane.** No LLM in select/gate/close/
  advance; the LLM lives only inside the executor, behind a pass/fail
  contract.
- **D3 — Valves are hard stops.** `pending-approval` / `acceptance` /
  `blocked` halt the loop and surface to the human — never auto-resolved.
- **D4 — Observable, not attached.** Live stream + per-item transcript +
  heartbeat + escalation channel + budget guards + gate backstop.
  Pause-and-handoff on escalation, not live-attach.
- **D5 — Gate backstop is inviolable.** The executor cannot close or
  merge; the gate runs in loop control; a bad diff halts, never merges.
- **D6 — One `Executor` port.** `claude -p` / `codex exec` / future `pi`
  / `local-model` are adapters behind ONE port sharing ONE prompt-
  assembly + response-extraction path. No bespoke per-adapter paths.
- **D7 — Config-selected runtime.** `.livespec.jsonc` gains an `executor`
  block; the supported set is the orchestrator's OWN per-runtime
  packaging (Claude / Codex / future Pi), not the core Driver set.
- **D8 — Launcher home is the orchestrator plugin.** The Driver repos
  bind only core's spec-side `/livespec:*` prose; the orchestrator owns
  its own skills + per-runtime packaging, so the launcher lives here — NOT
  in `livespec-driver-claude` / `-codex`.
- **D9 — Local-model tier = SMOKE, not capability.** Single-shot
  generation (no tiny-model tool loop); behavior-assert (not source);
  greedy + fixed seed + hash-pinned model + pinned runtime; weights
  fetch-cached, NEVER in git; prompt DERIVED from the fixture
  SPECIFICATION, never hardcoded; offline + secret-free at run time.
  (These are the former D1–D9 of the narrow plan, folded in.)
- **D10 — Integration tier drives the REAL loop.** Tier 4 calls
  `drive.main([...])` against the real JSONL store with only the executor
  leaf mocked — not a toy re-implementation.
- **D11 — Gated real E2E replaces the tautology's job.** Tier 5 is
  operator-gated (`just acceptance-live-*` + a `run_live_acceptance`
  binding, keyed on `ANTHROPIC_API_KEY`); the tautology may remain the
  cheap always-on smoke placeholder but must be honestly labeled as such.
- **D12 — "Done" means exercised live.** No loop-behavior slice is done
  on merge + CI alone; a real `drive` run must be journaled.
- **D13 — Architecture, not mechanism, in the spec.** Any `SPECIFICATION/`
  work constrains the `drive` invocation surface, the Executor port
  contract, the observability guarantees, and the tier ladder — not
  internal composition. Independent Fable review before ratification;
  heading-coverage co-edit for any `## ` change.
- **D14 — Reuse, don't fork, `livespec_runtime`.** git-jsonl consumes the
  shared pure functions; the serial execution adapter is git-jsonl's own.
  Never branch/flag the runtime to serve both substrates.

## Relationship to beads-fabro

Same shared pure core (`livespec_runtime`); git-jsonl's serial/in-place
executor is the counterpart of beads-fabro's fabro/parallel one. This
epic is the "de-factory'd dispatcher": the identical deterministic loop,
minus the sandbox, the threads, the cost sink, and the auto-resolving
valves. beads-fabro's `dispatcher.py`, its 16-file `tests/integration/`
suite, and its `test_beads_fabro_live_golden_master.py` are the reference
shapes to lift (minus the fabro-specific parts).

## Cross-references

- Sibling loop + tests to mirror:
  `livespec-orchestrator-beads-fabro`'s `commands/dispatcher.py`,
  `tests/integration/`, `acceptance/test_beads_fabro_live_golden_master.py`.
- The tautology + mock this epic supersedes:
  `acceptance/test_git_jsonl_golden_master.py`,
  `.claude-plugin/scripts/livespec_orchestrator_git_jsonl/acceptance.py`,
  `tests/e2e-cli/test_cli_e2e_round_trip.py`.
- Core deferred option realized by tier 3: `local-bundled-model-e2e`
  (livespec v014 N9-D1); core gated real tier: `e2e-test-claude-code-real`.
- Shared pure core: `livespec_runtime.work_items.lifecycle`
  (`is_item_ready`, `ready_sort_key`).

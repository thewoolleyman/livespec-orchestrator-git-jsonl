# Design — local-model-acceptance-tier (livespec-orchestrator-git-jsonl)

The reasoning of record for the thread. The `handoff.md` is the
resumable entry point; this file is the "why" a cold-start reader opens
second. Design is LOCKED at decisions D1–D9 below; deviations require a
new decision recorded here.

## Problem

`livespec-orchestrator-git-jsonl`'s top-of-pyramid acceptance test is a
**tautology**. `acceptance/test_git_jsonl_golden_master.py` calls
`run_acceptance` (in
`.claude-plugin/scripts/livespec_orchestrator_git_jsonl/acceptance.py`),
which:

1. reads the first line of the fixture `spec.md` (only to get the
   fixture name);
2. writes a **hardcoded constant** program to disk —
   `_PROGRAM_TEXT` literally contains
   `def greet(name): return f"Hello, {name}!"`;
3. imports it and asserts `greet("Ada") == "Hello, Ada!"`.

It touches **zero** orchestrator code — no store, no skills, no
executor, no model. It passes regardless of implementation state
because it never invokes the system. The mid-tier
`tests/e2e-cli/test_cli_e2e_round_trip.py` is better but is a **mock**:
it drives each skill through an injected stand-in that materializes each
fixture's declared `expected_files` **regardless of the prompt**. So the
mock proves CLI/skill-discovery **wiring**, but it is prompt-blind — a
garbage prompt-builder still passes.

Net: there is **no tier where a real model closes the loop** from the
SPECIFICATION to a runnable program — and the one place a real model
does close it (the gated `e2e-test-claude-code-real` philosophy in core,
and the sibling `livespec-orchestrator-beads-fabro`'s
`acceptance/test_beads_fabro_live_golden_master.py` +
`just acceptance-live-golden-master`) requires an `ANTHROPIC_API_KEY`,
the production container, and real cost/time.

## Goal

Add a **local, offline, no-API-key model executor tier** that implements
the `hello-world-greets-a-name` fixture with a real (if tiny) model,
exercising the whole `spec → prompt → model → parse → write → run →
verify` pipeline. This is the git-jsonl realization of core's captured
deferred option `local-bundled-model-e2e` (livespec v014 N9-D1; recorded
in `livespec/archive/brainstorming/approach-2-nlspec-based/`).

## The tier ladder (where this sits)

| Tier | What it proves | Runs |
|---|---|---|
| 1. Hermetic tautology (hardcoded `_PROGRAM_TEXT`) | nothing (never calls the system) | per-commit merge gate |
| 2. Mock CLI round-trip (`expected_files` materialized) | CLI/skill wiring + completeness; **prompt-blind** | per-commit (`just check`) |
| **3. Local-model smoke tier (NEW)** | the **real executor + prompt + parse path** with a real, variable output; catches prompt-correctness / transport / extraction bugs tiers 1–2 **cannot** | alternate cadence, offline, no secret |
| 4. Gated real-model E2E (`e2e-test-claude-code-real` / live golden-master) | **capability** — a capable agent implements real specs | alternate cadence, needs API key |

Tier 3 is the missing rung: the first thing that makes a real model
close the loop, without a secret or the network. It is explicitly a
**smoke / wiring tier**, NOT a capability tier — see "Honest limits".

## Why a tiny model buys real signal over tiers 1–2

Established in the design conversation and worth pinning, because it is
the whole justification:

- The **tautology** exercises `write_text` + `runpy` + assert; it cannot
  fail unless Python breaks.
- The **mock** materializes the right answer **regardless of the
  prompt** — so a broken prompt-builder still passes.
- A **real model** (even 0.5–1.5B) forces the real chain: spec is read,
  a prompt is assembled *from it*, the runtime is launched, a **variable**
  response is captured, the program is **extracted** from that response
  (models wrap code in fences + prose), written, run, and verified. A
  broken prompt, launcher, or extractor makes it fail. So tier 3 catches
  a **prompt-correctness / transport / extraction** bug class that
  neither the tautology nor the mock can structurally detect.

## Honest limits (what tier 3 does NOT buy)

- **Not capability.** Hello-world is trivial enough that a 0.5B model
  passing it says nothing about implementing a real spec. Tier 3 is not a
  substitute for tier 4; keep the gated real-model E2E for capability.
- **Shallow prompt signal on THIS fixture.** Almost any prompt that says
  "greet returning `Hello, <name>!`" elicits the right answer, so the
  prompt-quality signal is weak *until the fixture is less trivial*.
  Prompt-quality testing is bounded by fixture triviality, not model
  size. The value on hello-world is precisely "a real model closes the
  loop, offline, secret-free."

## Locked decisions

- **D1 — Smoke tier, not capability.** Tier 3 sits between the mock and
  the gated real-model E2E. It MUST NOT be documented or presented as a
  full-lifecycle / capability E2E, and MUST NOT replace tier 4.
- **D2 — Single-shot generation, no agentic tool loop.** For hello-world
  the harness does the file I/O deterministically; the model only emits
  the program. Do NOT drive the multi-step `implement` tool loop with a
  tiny model — that is where small models thrash and go flaky.
- **D3 — Behavior-assert, never source-assert.** Assert
  `greet("Ada") == "Hello, Ada!"` by running the produced program. Never
  assert exact generated source (flaky, and re-hardcodes the tautology).
- **D4 — Determinism knobs.** Greedy decoding (temperature 0) + fixed
  seed + model pinned by content hash + pinned runtime version.
  Behavior-assert absorbs residual floating-point variation across
  arch/BLAS backends.
- **D5 — Weights are NOT committed to git.** Fetch-and-cache on first
  run, hash-verified, into a cache dir OUTSIDE the repo. No network at
  test run time (the fetch is a separate, cached step). Preferred form:
  a **llamafile** pinned by release URL + hash (a single bundled
  executable — the closest match to "bundled model"); `ollama pull` is an
  acceptable alternative.
- **D6 — Tiny instruct/coder model, license-clean.** Candidate:
  Qwen2.5-Coder-1.5B-Instruct or Llama-3.2-1B-Instruct (Q4 GGUF, ~0.6–1
  GB). The chosen model's license MUST permit CI use / redistribution.
- **D7 — `LocalModelExecutor` behind the shared `Executor` port.** The
  same port the `drive`-loop launchers (`claude -p` / `codex exec` /
  future `pi`) implement — one more adapter, NOT a bespoke toy path. It
  MUST share the prompt-assembly and response-extraction code with the
  real launchers, so tier 3 exercises the **production** executor path.
  (This is the seam from the `drive` / Executor-port design; tier 3 is
  its first offline consumer. Cross-reference that epic.)
- **D8 — `just e2e-test-local-model`, alternate cadence.** A new target,
  NOT in `just check` (mirrors `e2e-test-claude-code-real`). The pytest
  binding SKIPS loudly when the model isn't cached; the CI job that owns
  this tier FAILS (not skips) if it can't fetch the model.
- **D9 — Prompt derived from the fixture SPECIFICATION.** The model
  prompt MUST be built from
  `acceptance/fixtures/hello-world-greets-a-name/SPECIFICATION/`, never a
  hardcoded string. If the prompt embeds the answer or ignores the spec,
  it is the tautology moved up one layer.

## Relationship to the broader `drive` / Executor-port epic

Tier 3's `LocalModelExecutor` is one adapter behind the `Executor` port
introduced for the deterministic `drive` loop (the offline / no-secret
variant alongside the `claude -p` / `codex exec` / future `pi`
launchers). If the `drive` epic lands first, tier 3 reuses its port and
prompt/extraction code verbatim; if tier 3 lands first, it defines the
minimal port and the `drive` launchers adopt it. Either way there is ONE
port and ONE prompt/extraction path — never two.

## Cross-references

- Core deferred option: `local-bundled-model-e2e` (livespec v014 N9-D1).
- Core gated real tier: `e2e-test-claude-code-real`
  (`livespec/SPECIFICATION/non-functional-requirements.md`,
  `contracts.md`).
- Sibling precedent for a gated real acceptance tier:
  `livespec-orchestrator-beads-fabro/acceptance/test_beads_fabro_live_golden_master.py`
  + `run_live_acceptance` + `just acceptance-live-golden-master`.
- The tautology + mock this tier sits above:
  `acceptance/test_git_jsonl_golden_master.py`,
  `.claude-plugin/scripts/livespec_orchestrator_git_jsonl/acceptance.py`,
  `tests/e2e-cli/test_cli_e2e_round_trip.py`.

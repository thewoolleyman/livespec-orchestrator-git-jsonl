---
topic: full-autonomous-mode
author: claude-opus-4-8
created_at: 2026-07-03T00:27:22Z
spec_commitments:
  impl_followups:
    - id_hint: git-jsonl-autonomous-mode
      description: |
        Implement full autonomous mode in the git-jsonl plugin: the dangerous default-off --autonomous flag on the four heavyweight skills (capture-impl-gaps, capture-spec-drift, capture-work-item, implement) that LLM-resolves each per-item consent gate and auto-authors closure narration; the new decided_by human|autonomous JSONL key (required-on-write, optional-on-read); the escalate-don't-guess path for unresolvable decisions; and the constraint that thin-transport skills never accept --autonomous. Each behavior linked heading->scenario->test.
---

## Proposal: Full autonomous mode (dangerous, consent-gate scoped)

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/contracts.md
- SPECIFICATION/constraints.md
- SPECIFICATION/scenarios.md

### Summary

Add full autonomous mode to the git-jsonl impl-plugin as a dangerous, default-OFF, per-invocation opt-in (--autonomous) on the four heavyweight skills, in which an LLM auto-answers this plugin's own per-item consent gates and auto-supplies closure narration, recording each auto-decision on the append-only JSONL via a new decided_by human|autonomous key and escalating any truly-unresolvable decision to a human. The mode MUST NOT touch the admission/acceptance orchestration this plugin does not run; thin-transport query skills MUST NOT accept the flag.

### Motivation

Operator request for a dangerous 'full autonomous mode' toggle so an LLM handles all possible human decisions, blocking only on the truly-unresolvable. SCOPE: filed against the git-jsonl orchestrator plugin, which does NOT run the Dispatcher/admission/acceptance valves (those policy fields are unpersisted here), so this proposal covers only the consent gates this plugin owns (its four heavyweight skills) plus the decided_by audit key. The deep autonomy over the manual admission and ai-then-human acceptance valves belongs to the sibling livespec-orchestrator-beads-fabro (filed separately) and upstream livespec; that out-of-scope boundary is stated in spec.md rather than over-reached here.

### Proposed Changes

This proposal adds **full autonomous mode** to the git-jsonl impl-plugin,
scoped to the human-decision surface this plugin actually owns: the
per-item **consent gates** of its four heavyweight skills. It touches
`spec.md`, `contracts.md`, `constraints.md`, and `scenarios.md`; the
clause, contract, constraint, and scenario edits MUST land atomically.

**Scope boundary (critical).** This plugin does NOT run the orchestrator
Dispatcher/admission/acceptance machinery — its `admission_policy`,
`acceptance_policy`, and `blocked_reason` fields are unpersisted
(`contracts.md` §"Work-items JSONL record schema"). Therefore full
autonomous mode HERE means only that an LLM auto-answers this plugin's own
per-item consent gates and auto-supplies closure narration, blocking only
on a decision it judges truly unresolvable. The deep autonomy over the
`manual` admission valve and the `ai-then-human` acceptance valve is owned
by the sibling `livespec-orchestrator-beads-fabro` and MUST be specified
there, not here.

---

### `SPECIFICATION/spec.md`

**(a)** Add a new H2 `## Autonomous mode` AFTER §"Substrate properties"
and BEFORE §"What this spec is not", stating:

- The plugin MUST support two modes. The default is **interactive** —
  every store-write consent gate is presented to the user per item.
  **Full autonomous mode** is an opt-in, dangerous, default-OFF mode in
  which an LLM stands in for the user at each consent gate this plugin
  owns and auto-supplies closure narration.
- Full autonomous mode MUST be labelled "dangerous / use with caution"
  wherever it is offered.
- The mode MUST NOT cross into the admission/acceptance orchestration this
  plugin does not run; that autonomy is owned by
  `livespec-orchestrator-beads-fabro` (and upstream `livespec`).
- The mode MUST still **escalate** any **unresolvable decision** to a
  human rather than guess.

**(b)** Add three `## Terminology` entries (extending the existing
glossary): **Autonomous mode**, **Unresolvable decision** (a decision the
LLM cannot make with sufficient confidence, or that requires information
the plugin cannot obtain — the residual class the mode still surfaces to a
human), and **Escalation** (surfacing an unresolvable decision to the
human instead of resolving it).

---

### `SPECIFICATION/contracts.md`

**(a)** Add an autonomous-mode contract as a shared preamble to
`### Heavyweight authored skills (4)` (binding all four uniformly), plus a
per-skill note:

- Each of the four heavyweight skills MUST accept a dangerous opt-in flag
  `--autonomous`. When set, the skill MUST resolve its per-item consent
  gate(s) with an LLM decision instead of prompting the user, and MUST
  record every autonomously-resolved decision on the append-only JSONL.
  When a decision is unresolvable, the skill MUST NOT guess; it MUST
  escalate it to the user and, absent a user present to resolve it, MUST
  block and surface it.
- `capture-impl-gaps`: auto-consents which detected gap-ids to file.
- `capture-spec-drift`: auto-consents which drift findings to hand off to
  `/livespec:propose-change`.
- `capture-work-item`: auto-authors the freeform title/description/type.
- `implement`: auto-selects the work-item and auto-supplies the closure
  `--reason` and `resolution`.
- The three thin-transport skills (`list-work-items`, `next`,
  `detect-impl-gaps`) MUST NOT accept `--autonomous`; they are query-only.

**(b)** In `## Work-items JSONL record schema`, add one new key
`decided_by` — string, one of `human` | `autonomous` — following the SAME
required-on-write / optional-on-read accommodation the schema already
documents for `spec_commitment_hint` / `acceptance_criteria` / `notes` (a
legacy record authored before this field reads back as `null` without
firing a schema violation). Update the canonical count from "nineteen
keys" to "twenty keys" consistently. `decided_by` records whether the
record's decision was made by a human or by the autonomous engine.

**(c)** In `#### next`, note that a candidate MAY carry an advisory
`auto_resolvable` boolean hint (permitted under the existing
"MAY include additional impl-git-jsonl-specific fields" clause); it MUST
remain advisory and MUST NOT change the ranking.

---

### `SPECIFICATION/constraints.md`

**(a)** Add a new H2 `## Autonomous mode constraints` AFTER §"Skill
orchestration constraints" and BEFORE §"Persistent Agent Knowledge
constraints", as binary mechanically-checkable rules:

- Autonomous mode MUST default off: it MUST be an explicit per-invocation
  opt-in (the `--autonomous` flag); its absence MUST mean interactive.
- Enabling autonomous mode MUST require an explicit dangerous-mode
  acknowledgement.
- Every autonomously-resolved decision MUST be recorded in the append-only
  JSONL (via `decided_by: autonomous`); it MUST NOT be recorded in any
  sidecar (reinforcing §"Forbidden patterns" → "No off-substrate
  persistence").
- The engine MUST NOT auto-resolve a decision it classifies as
  unresolvable; it MUST block and surface such a decision to a human
  (mirroring Scenario 3's "no silent skips").

**(b)** Add a `## Forbidden patterns` bullet: the `--autonomous` flag MUST
NOT be added to the thin-transport (`list-*` / `next` /
`detect-impl-gaps`) skills — extending the existing "No mutating CLI flags
on `list-*` or `next` skills" rule.

---

### `SPECIFICATION/scenarios.md`

Add `## Scenario 5 — Full autonomous fix cycle` AFTER §"Scenario 4",
as a NUMBERED-STEP PROSE journey (house style; NOT Gherkin): the user
enables autonomous mode; `capture-impl-gaps --autonomous` auto-consents
each detected gap and files it with `decided_by: autonomous`; `implement
--autonomous` auto-runs Red → Green → closure with an LLM-authored
`reason`; and when one decision is unresolvable, the engine blocks and
escalates it to the human rather than guessing.

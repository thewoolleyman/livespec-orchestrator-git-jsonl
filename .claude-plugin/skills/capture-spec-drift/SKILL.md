---
name: capture-spec-drift
description: Detect impl→spec drift from two sources — the impl-tree heuristic and a read-only ledger-intent scan — judging every candidate through the shared spec-stated judgement, and hand off each finding to /livespec:propose-change with user consent. Required heavyweight authored skill per livespec/SPECIFICATION/contracts.md. Invoke as `/livespec-orchestrator-git-jsonl:capture-spec-drift`.
allowed-tools: Bash, Read, Grep, Glob, Write
---

# capture-spec-drift

Asymmetric counterpart to `capture-impl-gaps`. Where impl-gap detection
is mechanical, drift detection is heuristic — the implementation may
have evolved beyond what the spec documents, in ways no static
pattern-match can flag. The skill surfaces each candidate finding to
the user and hands the confirmed findings off to
`/livespec:propose-change` via the cross-boundary handoff (red-edge
handoff 1 per livespec/SPECIFICATION/contracts.md).

Drift has TWO sources, and this skill MUST detect both:

1. The **impl → spec heuristic** — candidate behaviour statements an
   LLM pass extracts from the implementation tree.
2. The **ledger-intent scan** — a read-only pass over recent
   work-items whose recorded intent encodes behaviour the spec does
   not state.

## One judgement, shared with every other orchestrator

Both sources ask the SAME question — does the ratified specification
state this behaviour? — and both MUST obtain the answer from the one
place that owns it: the `livespec_runtime.spec_stated` module of the
livespec-runtime release this plugin vendors.

This skill MUST NOT define a stated/unstated prompt, a verdict schema
or a verdict parser of its own. The module owns all three. Two
orchestrators running two readings of one question is the drift this
shared module exists to prevent, and the divergence is SILENT: a
finding a private reading produced is well-formed and routes through
the per-finding consent flow exactly as a judged one does, costing the
maintainer a proposed change against a clause that already states the
behaviour.

### Supplying the model — capture, answer, replay

This plugin runs no Dispatcher and holds no model credential, so the
module's injected `run_model` callable is supplied by YOU, the invoking
agent session: you answer the module's own rendered prompt yourself.
Call `judge` TWICE so the prompt is never rendered outside the module:

```python
from livespec_runtime.spec_stated import judge

captured: list[str] = []
_ = judge(spec_tree=spec_tree, statement=statement, run_model=captured.append)
# `captured[0]` is the module's rendered prompt. Read it, answer it as
# yourself, and bind that answer as `answer`.
verdict = judge(spec_tree=spec_tree, statement=statement, run_model=lambda _: answer)
```

The first call captures; you answer; the second call parses your answer
through the module's own parser. `run_model=captured.append` returns
`None`, so the first call rides the module's `Failure` track — that is
expected and its value is discarded. Only the SECOND call's `Result` is
a verdict.

A `Failure` from the second call means the judgement could not run (a
verdict the module's parser refuses, a heading the spec tree does not
carry). Say so to the user and move on; never substitute a reading of
your own for a verdict the module refused.

## Pre-requisites

- A `<spec-root>/` containing ratified spec content at the path
  declared in `.livespec.jsonc` (default: `SPECIFICATION/`).
- The consumer project's impl tree (the rest of the repo besides
  `<spec-root>/`).
- The work-items JSONL store path is reachable (the ledger-intent
  scan reads it).
- livespec installed and accessible — the
  `/livespec:propose-change` cross-boundary handoff requires it.

## Flags

**`--since-version <vN>`** (optional), mirroring `capture-impl-gaps`.
When set, the ledger-intent scan considers ONLY work-items captured on
or after the cut of spec version `<vN>`. When omitted, it considers
every live (non-`done`) work-item plus every work-item captured on or
after the most-recently-cut spec version. The flag scopes only the
ledger-intent source; the impl → spec heuristic is unaffected.

## Flow

### Step 1 — Load the comparison baseline

Use the Spec Reader to load the current specification:

```python
from livespec_orchestrator_git_jsonl.spec_reader import read_current_specification
from pathlib import Path

snapshot = read_current_specification(spec_root=Path("SPECIFICATION"))
spec_tree = snapshot.files
```

`spec_tree` maps each spec-root-relative file path to its text, which
is exactly the shape `judge` takes. Pass it VERBATIM: the module
derives the governing-heading set a verdict may cite from the tree it
was handed, so a trimmed tree makes it refuse headings the real spec
carries.

### Step 2 — Survey the impl tree for candidates

Scan the consumer project's impl tree (excluding `<spec-root>/`,
`.venv/`, `_vendor/`, generated artifacts) for:

- Public API surfaces (function signatures, CLI flag declarations,
  config schema entries, REST/gRPC endpoint definitions, etc.).
- Behavior documented inline in code (docstrings, comments tagged
  `# spec:`, etc.).
- Tests that assert behavior visible to external consumers.

Express each candidate as ONE behaviour statement — a sentence naming
the observable behaviour, not a pointer to the code that implements it.
A statement the judge cannot read as a behaviour cannot be judged
against clauses that describe behaviour.

### Step 3 — Judge each impl candidate through the shared judgement

For each candidate statement from Step 2, obtain its verdict from
`livespec_runtime.spec_stated` using the capture-answer-replay call
above:

```python
verdict = judge(spec_tree=spec_tree, statement=candidate, run_model=lambda _: answer)
```

Then branch on the verdict's `kind`:

- `stated` — the ratified text already states the behaviour. This
  produces no finding. Move on.
- `partial` — the spec states part of the behaviour. A finding, framed
  as a refinement.
- `unstated` — the spec does not state the behaviour. A finding.

Never substitute your own reading of the spec for the verdict's
`kind`. Deciding reflectedness here instead of in the module is the
private second authority this skill is forbidden to become.

For every finding, carry the verdict's `generalization_target` when it
is non-`None`: it names the one EXISTING heading whose generalization
would state the behaviour, and the recommended proposed change MUST
name that heading as the one to amend in preference to adding a new
clause. Carry `stated_by` and `rationale` into the finding too, so the
user sees which clauses the judgement read and why it answered as it
did.

### Step 4 — Ledger-intent scan

A read-only pass over recent work-items that surfaces work-item intent
encoding an observable behavior, decision, or invariant NOT reflected
in the current spec.

Read the store through the append-only materialized-view reduction
only — never the raw record sequence:

```python
from livespec_orchestrator_git_jsonl.store import materialize_work_items, read_work_items
from pathlib import Path

records = read_work_items(path=Path("work-items.jsonl"))
heads = materialize_work_items(records=iter(records_list))
```

The scan NEVER mutates a work-item and never writes spec-side state.

**Population.** Per `--since-version` above: the scoped set, or every
live work-item plus everything captured on or after the latest cut.
An item's `type` is NEVER a detection exclusion — a behaviour recorded
on an item somebody typed `chore` is still behaviour the spec does not
state, and the stored type is routinely wrong.

**The statement.** For each item in the population, render its four
intent fields as ONE statement — `title`, `description`,
`acceptance_criteria`, and the closure `reason`:

```python
statement = "\n\n".join(
    [
        f"Work item {head.id}",
        f"Title: {head.title}",
        f"Description: {head.description}",
        f"Acceptance criteria: {head.acceptance_criteria or '(none recorded)'}",
        f"Closure reason: {head.reason or '(none recorded)'}",
    ]
)
```

One statement, not four. The four fields are halves of one behaviour —
a title and its acceptance criteria judged in isolation each read as
unstated for intent the other states. Name an absent field rather than
dropping it, so a statement that omits the criteria is distinguishable
from one whose criteria the renderer failed to read. Do NOT render the
stored `type`: it is the one piece of evidence the population rule
tells the judgement to ignore.

**The verdict.** Judge each statement through the same
`livespec_runtime.spec_stated` module, with the same
capture-answer-replay call:

```python
verdict = judge(spec_tree=spec_tree, statement=statement, run_model=lambda _: answer)
```

Intent the judgement reports `stated` is already reflected in the spec
and produces no finding, so the scan raises no spurious proposed
changes. `partial` and `unstated` are ledger-intent drift findings,
carrying the same `generalization_target`, `stated_by` and `rationale`
as the impl-side findings.

### Step 5 — Per-finding propose-change handoff

Every finding from Step 3 and Step 4 goes through the SAME per-finding
consent flow:

1. Draft a one-sentence proposed-change framing the missing behaviour,
   naming the verdict's `generalization_target` as the heading to amend
   when one was returned.
2. Surface it to the user with the recommended action ("file a
   propose-change targeting `<spec-root>/`?"), showing the verdict's
   `kind`, `stated_by` and `rationale`.
3. On consent, invoke the cross-boundary handoff:

```bash
/livespec:propose-change --spec-target SPECIFICATION/ --topic <slug> --body <draft>
```

The proposed-change file lands under `<spec-root>/proposed_changes/`
awaiting a subsequent `/livespec:revise` pass.

### Step 6 — Summary

When all candidates are processed, print a summary:

- N impl behaviours surveyed, M work-items scanned
- Of those, K classified `partial` or `unstated`, of which J were
  filed as propose-changes
- S judgements that could not run

## Important properties

- **One shared judgement, no private reading** — both sources obtain
  every verdict from `livespec_runtime.spec_stated`. The skill defines
  no prompt, no verdict schema and no parser of its own.
- **LLM-assisted, user-in-the-loop** — every drift finding requires
  explicit user consent before a propose-change is filed. The skill
  does NOT auto-file.
- **Read-only on the impl tree AND on the ledger** — the skill never
  modifies source code and never mutates a work-item. Spec authorship
  happens through `/livespec:propose-change`, not here.
- **Spec-side write goes through the cross-boundary handoff** — this
  plugin never writes to `<spec-root>/proposed_changes/` directly. The
  handoff invocation is the surface contract.

## What this skill does NOT do

- Does NOT modify the impl tree.
- Does NOT modify or close any work-item. The ledger-intent scan is a
  read.
- Does NOT modify the spec tree directly. Routes through
  `/livespec:propose-change`.
- Does NOT detect spec→impl gaps. That's `capture-impl-gaps`.
- Does NOT auto-accept findings. User confirms every handoff.

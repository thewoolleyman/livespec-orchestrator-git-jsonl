---
topic: spec-stated-judgement-consumer
author: claude-opus-5-5
created_at: 2026-10-25T00:54:20Z
---

## Proposal: Drift detection and filing take their verdicts from the shared spec-stated judgement

### Target specification files

- SPECIFICATION/contracts.md
- SPECIFICATION/spec.md

### Summary

Amend `capture-spec-drift` so both of its drift sources (the impl-drift front-end and the ledger-intent scan) decide whether behaviour is stated through `livespec_runtime.spec_stated`, and amend `capture-work-item` so filing classifies the item through the same module and records the spec-change tier, with a linked proposal for a feature the spec does not state. Amend `## Scope boundary` so the judgement is consumed, never restated. No new clause is added where an existing one generalizes.

### Motivation

Plan spec-implementation-lockstep (epic bd-ib-ax3rds in the livespec-orchestrator-beads-fabro tenant) carries the assertion that both orchestrators, livespec-orchestrator-beads-fabro and livespec-orchestrator-git-jsonl, run the same is-this-stated-by-the-spec judgement from livespec-runtime. That plan's research note 003 outlines this proposal as P5, filed with its implementing child C7 (bd-ib-jik5ko). livespec-runtime has ratified the shared component: its contracts.md section `livespec_runtime.spec_stated` defines `judge`, `classify`, `parse_verdict`, the `SpecStatedVerdict` and `SpecChangeTier` dataclasses, and the `JUDGE_PROMPT` and `CLASSIFY_PROMPT` constants. It names this plugin's ledger-intent scan, impl-drift front-end and filing as consuming producers, and it says the `SpecChangeTier` fields are "the persisted fields both orchestrators store on a work-item". livespec-orchestrator-beads-fabro already states its side (its contracts.md, `capture-spec-drift` and "The spec-stated judgement is one shared component"). This specification still describes drift detection as a free heuristic, says nothing about classifying a filed item, and its record schema forbids every key beyond nineteen, so it has nowhere to store the tier. bd-ib-jik5ko's two assertions (the scan, the impl-drift front-end and the filing obtain their verdicts from `livespec_runtime.spec_stated`; a feature judged `partial` or `unstated` is filed with the shared spec-change tier fields and its linked proposal topic) are therefore not governed by any ratified clause here. VENDORED-RUNTIME FINDING, measured 2026-10-25 on origin/master: this plugin vendors livespec-runtime v0.20.0 (pyproject `tag = "v0.20.0"`, `.claude-plugin/scripts/_vendor/livespec_runtime/`), which has no `spec_stated` module. The module first shipped in livespec-runtime v0.28.0. Bumping the vendored pin to v0.28.0 or later is a prerequisite of IMPLEMENTING this proposal, not of ratifying it, so the bump belongs to the implementing work, not to this specification. Deliberately NOT proposed: a dispatch or ready hold. This plugin runs no Dispatcher and no admission valve (its record schema says the abstract policy fields are not persisted), so the beads-fabro hold has no surface here. The tier is recorded so a human or a later consumer can act on it.

### Proposed Changes

**1. `contracts.md`, `#### `capture-spec-drift``, first paragraph.** Replace

```
Detect impl → spec drift heuristically (LLM-driven). For each
finding, present it to the user with a recommended action; on
```

with

```
Detect impl → spec drift through the spec-stated judgement of the
`livespec_runtime.spec_stated` module of the livespec-runtime
release this plugin vendors (the one judgement every orchestrator
shares, which answers whether a behaviour is stated by the ratified
specification and names the heading whose generalization would
state it). The skill MUST obtain that verdict from the module's
`judge` function, rendering the module's own `JUDGE_PROMPT` and
supplying the model only through the module's injected
`run_model` callable; it MUST NOT define a prompt, a verdict
schema or a parser of its own. A behaviour the judgement reports
`stated` MUST NOT become a finding. For each finding the skill
MUST name the judgement's `generalization_target`, when one is
returned, as the existing heading the recommended proposed change
amends in preference to a new clause. For each
finding, present it to the user with a recommended action; on
```

The rest of that paragraph is unchanged.

**2. `contracts.md`, the ledger-intent paragraph of `capture-spec-drift`.** Replace

```
encoding an observable behavior, decision, or invariant NOT reflected in
the current spec. Each ledger-intent finding MUST be surfaced through the
```

with

```
encoding an observable behavior, decision, or invariant NOT reflected in
the current spec. Whether intent is reflected MUST be decided by the
same spec-stated judgement, reading the four fields named above; an
item's `type` is never a detection exclusion. Each ledger-intent
finding MUST be surfaced through the
```

The rest of that paragraph, and the `--since-version` paragraph, are unchanged.

**3. `contracts.md`, `#### `capture-work-item``.** After its first paragraph (the one ending "Closure is via the freeform path in `implement`."), insert:

```
Before appending, the skill MUST classify the item as `feature`,
`bug`, `chore` or `non_functional` through the `classify` function
of the same `livespec_runtime.spec_stated` module, passing the
supplied `type` as evidence rather than as the answer, and MUST
record the outcome in the record's `spec_change_tier` field
(§"Work-items JSONL record schema"). An item classified `feature`
MUST then be judged through `judge` against the ratified
specification for its asked-for behaviour; when the verdict is
`partial` or `unstated` the item is spec-change tier: the skill
MUST offer to file a linked proposed change through the
`/livespec:propose-change` cross-boundary handoff, naming the
verdict's `generalization_target` as the heading to amend when one
is returned, and MUST record the resulting canonical topic as the
tier's `linked_proposal_topic`. An item classified `bug`, `chore`
or `non_functional`, or a `feature` judged `stated`, is not
spec-change tier. When the classification or the judgement cannot
run (no model, a timeout, or a verdict the module's parser refuses),
the skill MUST say so to the user and append the record with
`spec_change_tier: null`. An `epic` is not classified.
```

**4. `spec.md`, `## Scope boundary`, first paragraph.** After the sentence ending "point upstream for anything else.", append:

```
The same holds for the shared livespec-runtime contracts this plugin
consumes: the spec-stated judgement — its prompt, its inputs, its
verdict schema and its parser — is FIXED by livespec-runtime's
`livespec_runtime.spec_stated` contract, and this `SPECIFICATION/`
MUST NOT restate it; it states only where this plugin's skills
obtain and store its verdicts.
```


## Proposal: The work-item record carries the shared spec-change tier

### Target specification files

- SPECIFICATION/contracts.md

### Summary

Add one optional-on-read key, `spec_change_tier`, to the JSONL record schema, so the record can hold the `SpecChangeTier` fields that livespec-runtime declares as the persisted shape both orchestrators store.

### Motivation

The record schema forbids any key beyond its nineteen, so the tier the amended `capture-work-item` records has nowhere to live. livespec-runtime's `SpecChangeTier` (`tier`, `linked_proposal_topic`, `verdict`, `judged_at`) is declared as the persisted fields both orchestrators store, so this realization stores exactly that shape under one key rather than inventing field names. See the first proposal in this file for the plan context.

### Proposed Changes

**1. `contracts.md`, `## Work-items JSONL record schema`, opening paragraph.** Replace "nineteen keys enumerated below" with "twenty keys enumerated below"; replace "`spec_commitment_hint`, `supersedes`, `acceptance_criteria`, and\n`notes` are required-on-write but optional-on-read" with "`spec_commitment_hint`, `supersedes`, `acceptance_criteria`,\n`notes`, and `spec_change_tier` are required-on-write but optional-on-read"; and replace "Additional keys beyond this nineteen are forbidden" with "Additional keys beyond these twenty are forbidden". Every other sentence of the paragraph is unchanged.

**2. `contracts.md`, the field list, immediately after the `notes` bullet.** Insert:

```
- `spec_change_tier` — object or `null`. OPTIONAL on the read path
  (records authored before this field's introduction read back as
  `null`); always written explicitly on append. Carries the
  `livespec_runtime.spec_stated.SpecChangeTier` fields that every
  orchestrator persists, under the same names: `tier` (string, one
  of `spec-change`, `none`; required), `linked_proposal_topic`
  (string or `null`; required; the canonical topic of the linked
  proposed change), `verdict` (object or `null`; required; the
  `SpecStatedVerdict` fields `kind`, `stated_by`,
  `generalization_target` and `rationale`), and `judged_at` (string,
  UTC ISO-8601 seconds; required). A record whose `tier` is
  `spec-change` MUST carry a non-null `verdict` whose `kind` is
  `partial` or `unstated`. `null` when the classification did not
  run (an `epic`, a legacy record, or a judgement that could not
  run per §"`capture-work-item`").
```


## Proposal: A scenario for filing a feature the spec does not state

### Target specification files

- SPECIFICATION/scenarios.md

### Summary

Add Scenario 6, which walks the amended `capture-work-item` through a feature the spec does not state, and amend Scenario 5 so its drift finding comes from the shared judgement.

### Motivation

Load-bearing filing behaviour needs a Given/When/Then scenario, not prose alone. Scenario 2 is a bug fix and Scenario 5 is drift, so neither carries the feature filing path. See the first proposal in this file.

### Proposed Changes

**1. `scenarios.md`, `## Scenario 5 — Ledger-intent drift surfaces missing spec behavior`, step 2.** Replace "It finds a recent work-item whose `description` encodes a behavior\n   that never made it into the spec, and surfaces it" with "It finds a recent work-item whose `description` encodes a behavior\n   that the shared spec-stated judgement reports `unstated`, and surfaces it". Step 4 MUST read: "Intent the judgement reports `stated` produces no finding, so the scan\n   raises no spurious propose-changes."

**2. `scenarios.md`, new final section.** Append:

```
## Scenario 6 — A feature the spec does not state is filed at spec-change tier

The user files a feature whose asked-for behaviour no ratified clause
states.

1. The user invokes
   `/livespec-orchestrator-git-jsonl:capture-work-item` with title,
   description and `type: feature`.
2. The skill classifies the item through
   `livespec_runtime.spec_stated.classify` as `feature`, then judges
   its asked-for behaviour through `judge`; the verdict is `unstated`
   and names an existing heading as its `generalization_target`.
3. The skill offers the linked proposed change; on consent it hands
   off to `/livespec:propose-change`, naming that heading as the one
   to amend.
4. The appended record carries `spec_change_tier` with `tier:
   spec-change`, the proposal's canonical topic as
   `linked_proposal_topic`, the verdict, and `judged_at`.
5. Filing the same item with `type: bug` instead yields a record
   whose `spec_change_tier.tier` is `none` and whose
   `linked_proposal_topic` is `null`; no proposal is offered.
```

Because this adds a `## ` heading, `tests/heading-coverage.json` MUST gain an entry for it in the same revision; until a test exercises it, that entry MAY be `test: "TODO"` with a non-empty `reason` and an owning `work_item`.


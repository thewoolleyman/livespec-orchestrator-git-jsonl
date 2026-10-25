---
name: capture-work-item
description: Freeform direct filing of an impl-side work item (bugs, refactors, tactical tasks). Required heavyweight authored skill per livespec/SPECIFICATION/contracts.md. Filed records carry `origin: freeform` and `gap_id: null`. Invoke as `/livespec-orchestrator-git-jsonl:capture-work-item`.
allowed-tools: Bash, Read, Grep, Write
---

# capture-work-item

The freeform direct-filing skill. Use this for bugs, refactors,
tactical tasks, and anything else that doesn't trace back to a spec
rule. For spec-traceable items, use `capture-impl-gaps` instead.

## Pre-requisites

- The work-items JSONL store path is reachable.
- `livespec_orchestrator_git_jsonl` package on import path.

## Flow

### Step 1 — Gather inputs

Ask the user (one question at a time):

1. **Title** — one-line summary.
2. **Description** — multi-line free-form (markdown permitted).
3. **Type** — one of `bug`, `feature`, `task`, `chore`, `epic`.
4. **Priority** — integer 0–4 (default 2). Re-state semantics if asked:
   0 critical, 1 high, 2 medium, 3 low, 4 backlog.

Optional follow-ups (skip-confirmable):

- **Assignee** — string or null (default null).
- **Depends-on** — comma-separated `li-` ids; empty list permitted.
- **Spec-commitment-hint** — string `id_hint` or null (default null).
  Supplied via `--spec-commitment-hint <id_hint>` when the work-item
  is being filed in response to a spec-side
  `spec_commitments.impl_followups[].id_hint` declaration (per livespec
  `SPECIFICATION/contracts.md`). When
  supplied, the resulting record's `spec_commitment_hint` MUST equal
  the verbatim `id_hint`; when omitted, the field defaults to `null`
  (the freeform case). This is the surface livespec's
  `unresolved-spec-commitment` doctor invariant queries via
  `list-work-items --json` to verify each declared spec→impl
  commitment maps to a filed work-item.

### Step 2 — Classify the item through the shared spec-stated judgement

Before appending, classify the item through the `classify` function of
the `livespec_runtime.spec_stated` module of the livespec-runtime
release this plugin vendors — the one judgement every orchestrator
shares. The class decides whether the record carries a spec-change
tier, so it MUST be settled while the record can still carry it: a
record appended first and classified afterwards can only be amended by
a second record, and until that lands the materialized view carries a
filing with no tier at all.

The four classes are the module's own vocabulary, and nothing else:
`feature` (new observable behaviour), `bug` (behaviour contradicting
what is already stated), `chore` (work changing no observable
behaviour), and `non_functional` (a constraint on HOW the system
behaves rather than on what it does). `classify` refuses any other
answer, so a fifth class or a misspelled one reports as a judgement
that could not run rather than as the typo it is.

An `epic` is not classified. It is a container for other items rather
than a behaviour of its own, so the judgement has nothing to read.

The supplied `type` from Step 1 is passed **as evidence**, never as the
answer:

```python
from livespec_runtime.spec_stated import classify

captured: list[str] = []
_ = classify(
    title=title,
    description=description,
    item_type=type_,
    run_model=captured.append,
)
# `captured[0]` is the module's rendered prompt. Read it, answer it as
# yourself, and bind that one-word answer as `answer`.
item_class = classify(
    title=title,
    description=description,
    item_type=type_,
    run_model=lambda _: answer,
)
```

This plugin runs no Dispatcher and holds no model credential, so the
module's injected `run_model` callable is supplied by YOU, the invoking
agent session: the first call captures the module's own rendered
prompt, you answer it, and the second call parses that answer through
the module's own parser. `run_model=captured.append` returns `None`, so
the first call rides the module's `Failure` track — expected, and its
value is discarded. Only the SECOND call's `Result` is a class.

Weigh the supplied `type` against the title and the description, and
disagree with it when they say otherwise. The stored type is whatever
a human happened to record, so trusting it as the answer would skip
the judgement for exactly the items that need it.

**When the classification cannot run** — no model, a timeout, or an
answer the module's parser refuses (a `Failure` from the second call) —
say so to the user and append the record with `spec_change_tier: null`.
Both halves matter: a silent null tier is indistinguishable from a
legacy record authored before the field existed, and refusing to file
at all loses the work-item the user asked for.

### Step 3 — Branch on the class

Only a `feature` asks for new observable behaviour, so only a `feature`
raises the question of whether the spec already states it. The other
three classes answer that question by what they are, and are filed
without a spec-change tier.

**A `bug`, `chore` or `non_functional` is NOT spec-change tier.** Skip
the judgement below entirely and record `tier: none` with
`verdict: null`; no proposal is offered. Each class is already a
statement about the spec rather than a question for it: a `bug` is
behaviour contradicting what is stated, so the clause it offends
exists; a `chore` changes no observable behaviour, so there is nothing
for a clause to state; and a `non_functional` constrains HOW the
system behaves, which the specification's constraints already govern.
Judging one anyway would put a verdict on a question it does not ask,
and a `partial` or `unstated` answer would route a bug report to a
proposed change while the behaviour it contradicts stays broken.

The `verdict` is null here rather than a `stated` verdict, and the
difference is readable: a null verdict says no judgement was owed,
while a `stated` verdict says one ran and found the behaviour already
specified. Only a `feature` can produce the latter.

**A `feature` is judged against the ratified specification.**
An item the classification reports `feature` asks for NEW observable
behaviour, so the next question is whether the ratified specification
already states it. Judge it through the `judge` function of the SAME
`livespec_runtime.spec_stated` module, with the item's title and
description as the statement:

```python
from livespec_orchestrator_git_jsonl.spec_reader import read_current_specification
from livespec_runtime.spec_stated import judge
from pathlib import Path

spec_tree = read_current_specification(spec_root=Path("SPECIFICATION")).files
statement = f"{title}\n\n{description}"

captured: list[str] = []
_ = judge(spec_tree=spec_tree, statement=statement, run_model=captured.append)
# `captured[0]` is the module's rendered prompt. Read it, answer it as
# yourself, and bind that answer as `answer`.
verdict = judge(spec_tree=spec_tree, statement=statement, run_model=lambda _: answer)
```

The same capture-answer-replay shape as Step 2, and for the same
reason: this plugin holds no model credential, so the session is the
`run_model`, and the prompt is never rendered outside the module. Pass
`spec_tree` VERBATIM — the module derives the heading set a verdict may
cite from the tree it was handed, so a trimmed tree makes it refuse
headings the real spec carries.

Branch on the verdict's `kind`:

- **`partial` or `unstated` — the item is SPEC-CHANGE TIER.** The spec
  states part of the behaviour, or none of it, so a spec change is
  owed before the implementation can be spec-governed. Offer to file a
  linked proposed change through the `/livespec:propose-change`
  cross-boundary handoff, naming the verdict's
  `generalization_target` as the heading to amend when one was
  returned:

  ```bash
  /livespec:propose-change --spec-target SPECIFICATION/ --topic <slug> --body <draft>
  ```

  Record the resulting canonical topic as the tier's
  `linked_proposal_topic`. That topic is the only thread from the
  filing back to the proposal that would state its behaviour — without
  it the record claims a spec change is owed and names nothing anybody
  can open.

  When the user DECLINES the linked proposal, or the handoff does not
  complete, the record still carries `tier: "spec-change"` and the
  verdict, with `linked_proposal_topic=None`. The judgement happened
  and its answer stands; only the proposal is missing, and downgrading
  the tier would erase the one signal that says so.

- **`stated` — not spec-change tier.** The ratified text already
  states the behaviour, so no proposal is owed. Record
  `tier: "none"` carrying the `stated` verdict, so a later reader can
  see that the question was asked and answered rather than skipped.

Assemble the tier as the vendored dataclass, never as a hand-built
dict — the store serializes it, and a hand-built dict is a second
account of a schema this plugin does not own. `verdict` is bound only
on the `feature` path, so bind it to `None` on the other three rather
than reading a name Step 3's judgement never set:

```python
from datetime import datetime, timezone
from livespec_runtime.spec_stated import SpecChangeTier

# `verdict` is the judged verdict for a `feature`, and None for a
# `bug`, `chore` or `non_functional`, which skipped the judgement.
spec_change_tier = SpecChangeTier(
    tier=(
        "spec-change"
        if verdict is not None and verdict.kind in ("partial", "unstated")
        else "none"
    ),
    linked_proposal_topic=topic,  # str | None; None when declined or not filed.
    verdict=verdict,  # SpecStatedVerdict | None.
    judged_at=datetime.now(tz=timezone.utc).isoformat(),
)
```

`judged_at` is the time of the LAST judgement or classification that
ran — for a feature that is this judgement, for every other class it
is the classification in Step 2.

### Step 4 — Confirm and file

Show the user the assembled record and ask "file?". On `yes`, append:

```python
from livespec_orchestrator_git_jsonl._ids import new_work_item_id
from livespec_orchestrator_git_jsonl.store import append_work_item
from livespec_orchestrator_git_jsonl.types import WorkItem
from datetime import datetime, timezone
from pathlib import Path

item = WorkItem(
    id=new_work_item_id(),
    type=type_,
    status="ready",
    title=title,
    description=description,
    origin="freeform",
    gap_id=None,
    rank=rank,
    assignee=assignee,
    depends_on=tuple(depends_on),
    captured_at=datetime.now(tz=timezone.utc).isoformat(),
    resolution=None,
    reason=None,
    audit=None,
    superseded_by=None,
    spec_commitment_hint=spec_commitment_hint,  # str | None; None for freeform.
)
append_work_item(
    path=Path("work-items.jsonl"),
    item=item,
    spec_change_tier=spec_change_tier,  # SpecChangeTier | None.
)
```

`spec_change_tier` is a SEPARATE argument rather than a `WorkItem`
field: the work-item model is the shared surface
`livespec_runtime.work_items.types` owns, and the tier is persisted
per orchestrator realization — labels on a beads tenant, this record
key here. Pass `None` only when no classification ran at all (an
`epic`, or a judgement that could not run); it is written as an
explicit `null`.

Print the assigned id back to the user.

## Important properties

- **`origin: freeform`** — never `gap-tied`. Use `capture-impl-gaps`
  for gap-traceable items.
- **`gap_id: null`** — REQUIRED. The schema check fires on any
  non-null value combined with `origin: freeform`.
- **Closure path** — closed via `implement`'s freeform fix path (a
  user-supplied `--reason` with no re-detection step). At closure
  time `implement` MUST populate the audit merge-evidence
  (`merge_sha` reachable from `origin/<canonical_branch>`, plus
  `pr_number` when the merge came from a PR) for `completed` /
  `spec-revised` / `resolved-out-of-band` resolutions — see
  `implement` Step 6; the `work_item_merge_evidence` static check
  enforces it. Filing-time records always carry `audit: null`.

## What this skill does NOT do

- Does NOT close work-items. Use `implement`.
- Does NOT detect gaps. Use `capture-impl-gaps`.
- Does NOT auto-set `assignee` or `depends_on`. User supplies both.

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

### Step 3 — Confirm and file

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
    status="open",
    title=title,
    description=description,
    origin="freeform",
    gap_id=None,
    priority=priority,
    assignee=assignee,
    depends_on=tuple(depends_on),
    captured_at=datetime.now(tz=timezone.utc).isoformat(),
    resolution=None,
    reason=None,
    audit=None,
    superseded_by=None,
    spec_commitment_hint=spec_commitment_hint,  # str | None; None for freeform.
)
append_work_item(path=Path("work-items.jsonl"), item=item)
```

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

---
name: capture-impl-gaps
description: Detect spec→impl gaps mechanically via the Spec Reader and file gap-tied work-items into the JSONL store with per-gap user consent. Required heavyweight authored skill per livespec/SPECIFICATION/contracts.md §"Heavyweight authored skills (6)". Invoke as `/livespec-impl-plaintext:capture-impl-gaps`.
allowed-tools: Bash, Read, Grep, Glob, Write
---

# capture-impl-gaps

Mechanical detection of spec→impl gaps. Heavyweight skill — orchestration
lives here in the SKILL.md prose per
SPECIFICATION/constraints.md §"Skill orchestration constraints". The
plugin's `Spec Reader` adapter and `store` module are the load-bearing
Python primitives this skill composes.

## Pre-requisites

- The consumer project has a `<spec-root>/` directory at the path
  declared in `.livespec.jsonc` (default: `SPECIFICATION/`).
- The `livespec-impl-plaintext` Python package is on the import path
  (uv-managed; verified by `uv run python3 -c "import
  livespec_impl_plaintext"`).
- The work-items JSONL store path is reachable (created on first
  append if absent).

## Flow

### Step 1 — Enumerate spec rules

Read every MUST / SHOULD clause from the canonical spec files using the
Spec Reader's "read current spec" capability:

```python
from livespec_impl_plaintext.spec_reader import read_current_specification
from pathlib import Path

snapshot = read_current_specification(spec_root=Path("SPECIFICATION"))
```

For each file in `snapshot.files`, scan for lines matching the rule
patterns (regex: `\bMUST\b`, `\bMUST NOT\b`, `\bSHOULD\b`, `\bSHOULD
NOT\b`, and lower-cased variants when in code-block contexts). Each
match is a candidate rule.

Surface each candidate to the user as a one-line summary:

```
[<spec-file>:<line>] <rule-text>
```

### Step 2 — Per-rule gap classification

For each candidate, ask the user:

> Is the implementation honoring this rule? (yes / no / skip)

- `yes` — no gap; move on.
- `no` — a gap exists. Proceed to Step 3.
- `skip` — defer judgment; move on without filing.

### Step 3 — Per-gap consent + filing

For each `no` rule:

1. Derive a stable `gap_id` from the rule location (e.g.,
   `gap-<spec-file-slug>-<line-number>`).
2. Check the work-items store: if a record with this `gap_id` already
   exists and is not closed, surface "already filed as `<li-id>`" and
   skip filing.
3. Otherwise, ask the user to confirm title + description (auto-drafted
   from the rule text). Defaults are pre-filled; the user accepts or
   edits.
4. On confirm, append a new work-item JSONL record:

```python
from livespec_impl_plaintext._ids import new_work_item_id
from livespec_impl_plaintext.store import append_work_item
from livespec_impl_plaintext.types import WorkItem
from datetime import datetime, timezone
from pathlib import Path

item = WorkItem(
    id=new_work_item_id(),
    type="task",
    status="open",
    title=user_confirmed_title,
    description=user_confirmed_description,
    origin="gap-tied",
    gap_id=stable_gap_id,
    priority=2,
    assignee=None,
    depends_on=(),
    captured_at=datetime.now(tz=timezone.utc).isoformat(),
    resolution=None,
    reason=None,
    audit=None,
    superseded_by=None,
)
append_work_item(path=Path("work-items.jsonl"), item=item)
```

### Step 4 — Summary

When all candidates are processed, print a summary:

- N candidate rules surfaced
- M classified as gaps, of which K were newly filed and J were already-tracked
- Skipped: S

## Important properties

- **In-memory ephemeral detection state** — no persistent intermediate
  artifact. The candidate list is discarded at skill exit per
  livespec/SPECIFICATION/contracts.md §"Heavyweight authored
  skills (6)" → capture-impl-gaps.
- **Per-gap user consent is REQUIRED** — never auto-file without
  explicit confirmation.
- **Idempotent** — re-running surfaces no duplicates for gaps already
  tracked (status≠closed).
- **No LLM in the detection path itself** — pattern-matching of MUST /
  SHOULD clauses is deterministic. LLM dialogue is used only for the
  classification and authoring steps (and only with user-in-the-loop).

## What this skill does NOT do

- Does NOT close work-items. Use `implement` for that.
- Does NOT modify the spec tree. Read-only on `<spec-root>/`.
- Does NOT detect impl→spec drift. That's `capture-spec-drift`.

---
name: implement
description: Drive Red→Green for a single work-item. For gap-tied items, verify closure by re-running capture-impl-gaps in dry-run mode. Required heavyweight authored skill per livespec/SPECIFICATION/contracts.md §"Heavyweight authored skills (6)". Invoke as `/livespec-orchestrator-git-jsonl:implement [<work-item-id>]`.
allowed-tools: Bash, Read, Grep, Glob, Edit, Write
---

# implement

The Red→Green driver. Walks a single work-item from open through
implementation to closed-with-audit. Closure branches on `origin ×
disposition` per livespec/SPECIFICATION/contracts.md
§"Heavyweight authored skills (6)" → implement.

## Pre-requisites

- A work-item to drive. Either passed by id (positional argument) or
  derived from `next` if none given.
- The work-items JSONL store path is reachable.
- Tests pass on the current branch (Red is fine; mid-cycle is not).
- `just check` exists in the consumer project (or equivalent toolchain
  command).

## Flow

### Step 1 — Pick the work-item

If `<work-item-id>` was supplied, load it from the JSONL store:

```python
from livespec_orchestrator_git_jsonl.store import materialize_work_items, read_work_items
from pathlib import Path

ix = materialize_work_items(read_work_items(path=Path("work-items.jsonl")))
target = ix[work_item_id]
```

If no id was supplied, invoke `/livespec-orchestrator-git-jsonl:next --json`,
parse the `work_item_ref`, and confirm with the user before
proceeding.

Refuse to proceed if `target.status != "open"`. Surface a clear error
and exit.

### Step 2 — Disposition decision

Ask the user up-front:

> Resolution path for this work-item:
> 1. Completed (Red→Green; this is the default)
> 2. wontfix / duplicate / spec-revised / no-longer-applicable /
>    resolved-out-of-band

For path 1, proceed to Step 3. For path 2, jump to Step 6 (admin
closure).

### Step 3 — Red

Author a failing test that exercises the work-item's intent:

- Identify the test file location (mirrors source tree).
- Write the test; ensure it fails for the reason described in the
  work-item.
- Commit the failing test with the `RED:` trailer convention (or the
  consumer project's red-green-replay convention).

### Step 4 — Green

Implement until the test passes:

- Make the smallest change that turns the failing test green.
- Run `just check` (or the consumer's check command) to confirm the
  full enforcement suite passes.
- Commit the impl.

### Step 5 — Closure verification

#### Step 5a — Gap-tied closure verification

When `target.origin == "gap-tied"`, the closure REQUIRES re-running
`capture-impl-gaps` in dry-run mode and confirming the `gap_id` is no
longer detected. v001 starter: surface to the user "please re-run
capture-impl-gaps and confirm the gap is gone" and ask `confirmed?`.
Future revisions will automate the dry-run invocation.

If the gap is still detected, the work-item is NOT closed — the user
either revises the impl further (back to Step 4) or marks the
work-item with one of the admin resolutions (Step 6).

#### Step 5b — Freeform closure

When `target.origin == "freeform"`, no re-detection runs. Proceed
directly to closure.

### Step 6 — Append closure record

Append a new JSONL record with `status: closed`. The exact shape
branches on the resolution choice.

**Merge evidence is REQUIRED for merge-implying resolutions.** Per
`SPECIFICATION/contracts.md` §"Work-items JSONL record schema" →
audit, every closure with `resolution` in `{completed, spec-revised,
resolved-out-of-band}` MUST carry a non-null `audit` whose
`merge_sha` is the SHA on `origin/<canonical_branch>` that introduced
the work. Populate it at closure time:

- Close AFTER the merge lands. Resolve the merge SHA from the PR
  (`gh pr view <pr> --json mergeCommit --jq .mergeCommit.oid`) or
  from `git log origin/<canonical_branch>`; for rebase-merges it is
  the last rebased commit of the series.
- VERIFY it locally before appending: `git cat-file -e <merge_sha>`
  and `git merge-base --is-ancestor <merge_sha>
  origin/<canonical_branch>` must both exit 0 — the same rules the
  `work_item_merge_evidence` static check
  (`just check-work-item-merge-evidence`) enforces afterwards.
- Record `pr_number` (integer) when the merge came from a PR; `null`
  otherwise.
- Administrative resolutions (`wontfix`, `duplicate`,
  `no-longer-applicable`) MUST keep `audit: None` — an
  administratively closed record must not carry merge-evidence.

```python
from livespec_orchestrator_git_jsonl.store import append_work_item, work_item_record_identity
from livespec_orchestrator_git_jsonl.types import AuditRecord, WorkItem
from datetime import datetime, timezone
from pathlib import Path

audit = (
    AuditRecord(
        verification_timestamp=datetime.now(tz=timezone.utc).isoformat(),
        commits=tuple(verified_commit_shas),
        files_changed=tuple(verified_files),
        merge_sha=verified_merge_sha,  # reachable from origin/<canonical_branch>
        pr_number=pr_number_or_none,
    )
    if resolution in ("completed", "spec-revised", "resolved-out-of-band")
    else None
)

closing_record = WorkItem(
    id=target.id,
    type=target.type,
    status="closed",
    title=target.title,
    description=target.description,
    origin=target.origin,
    gap_id=target.gap_id,
    priority=target.priority,
    assignee=target.assignee,
    depends_on=target.depends_on,
    captured_at=datetime.now(tz=timezone.utc).isoformat(),
    resolution=resolution,
    reason=user_supplied_reason,
    audit=audit,
    superseded_by=None,
    supersedes=work_item_record_identity(item=target),
)
append_work_item(path=Path("work-items.jsonl"), item=closing_record)
```

Print "closed `<id>` (`<resolution>`)" to the user.

## Important properties

- **Same `id`, new record** — closure does NOT mutate the open record.
  It appends a new record with the same `id` whose `supersedes` key
  names the prior head's `work_item_record_identity`, so the
  materialized view (supersession-chain head) shows the closed state
  with no divergent heads.
- **Audit merge-evidence REQUIRED for merge-implying closures** —
  `verification_timestamp`, `commits`, `files_changed`, `merge_sha`
  (+ optional `pr_number`) whenever `resolution` is `completed`,
  `spec-revised`, or `resolved-out-of-band`, regardless of origin.
  The `work_item_merge_evidence` static check fails closures whose
  `merge_sha` is missing or not reachable from
  `origin/<canonical_branch>`.
- **Admin closures take a `reason` and NO audit** — `wontfix`,
  `duplicate`, `no-longer-applicable` require a user-supplied
  `reason` and MUST keep `audit: None`.

## What this skill does NOT do

- Does NOT modify the spec tree.
- Does NOT auto-supersede related items. The user MAY supersede
  manually via a fresh `capture-work-item` referencing the closed id
  in `description`.
- Does NOT skip the test step. Red→Green is the rule; emergency
  closure paths are `wontfix` / `resolved-out-of-band` resolutions,
  not test-skipping.

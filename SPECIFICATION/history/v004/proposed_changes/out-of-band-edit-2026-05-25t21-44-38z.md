# Proposal: out-of-band MAY uppercase fix to contracts.md

## Motivation

The active spec at `SPECIFICATION/contracts.md` was edited
directly on `master` (commit `e2f9f89`, PR #24) to uppercase
the BCP 14 keyword on line 281 — `May be empty.` →
`MAY be empty.`. The edit landed without going through the
canonical `propose-change` → `revise` flow, so
`history/v003/contracts.md` no longer matches the HEAD-active
file. Doctor's `out-of-band-edits` static check correctly
flags the drift.

This proposal is a synthetic record manufactured by livespec
doctor so the out-of-band edit can be acknowledged and
reconciled into a new `history/v004/` snapshot.

## Proposal

Snapshot the current HEAD-active spec tree as
`SPECIFICATION/history/v004/`. The only file that differs
from the v003 snapshot is `contracts.md`; the other four
canonical spec files (`README.md`, `constraints.md`,
`scenarios.md`, `spec.md`) are byte-identical to v003 and
are copied through as the conventional full point-in-time
snapshot.

## Out-of-scope

- No new spec content. The contracts.md change is the
  already-merged uppercase fix; no further editorial changes
  are bundled here.
- No revisions to v001-v003. The out-of-band drift is
  reconciled forward via v004, not by mutating prior
  snapshots.

## Acceptance

- `SPECIFICATION/history/v004/` exists with the five
  canonical spec files.
- `SPECIFICATION/history/v004/proposed_changes/` contains
  this proposal file and its paired `-revision.md`.
- The revision file lists only `contracts.md` under
  `## Resulting Changes` (the only file whose v004 snapshot
  is non-byte-identical to its v003 snapshot).
- Doctor's `out-of-band-edits` and
  `accept-decision-snapshot-consistency` checks both pass
  after this is merged.

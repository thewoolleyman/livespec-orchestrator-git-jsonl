---
proposal: out-of-band-edit-2026-05-25t21-44-38z.md
decision: accept
revised_at: 2026-05-25T21:44:38Z
author_human: livespec-doctor
author_llm: livespec-doctor
---

## Decision and Rationale

Doctor detected out-of-band drift between HEAD-active spec
content and the HEAD-history-v003 snapshot. The drift is
the uppercase MAY fix on `contracts.md:281` that landed via
PR #24 outside the propose-change → revise flow. This
auto-backfill records the HEAD-active spec as the new
canonical v004.

Only `contracts.md` is listed under `## Resulting Changes`
because it is the only file whose v004 snapshot is
non-byte-identical to its v003 snapshot.

## Resulting Changes

- contracts.md

---
proposal: spec-commitment-hint-surfaces.md
decision: accept
revised_at: 2026-05-27T06:18:18Z
author_human: thewoolleyman <chad@thewoolleyman.com>
author_llm: claude-opus-4-7
---

## Decision and Rationale

Impl→spec ratification of the spec_commitment_hint field that already landed on master via PR #39 (li-4szyct). Load-bearing for livespec's unresolved-spec-commitment doctor invariant, which queries list-work-items --json to verify each declared spec→impl commitment maps to a filed work-item. Adds field to JSONL schema (required-on-write, optional-on-read), enumerates --with-spec-commitment-hint on list-work-items, and enumerates --spec-commitment-hint on capture-work-item.

## Resulting Changes

- contracts.md

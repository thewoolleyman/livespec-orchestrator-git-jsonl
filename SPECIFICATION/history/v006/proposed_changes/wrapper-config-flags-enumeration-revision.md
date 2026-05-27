---
proposal: wrapper-config-flags-enumeration.md
decision: accept
revised_at: 2026-05-27T06:18:18Z
author_human: thewoolleyman <chad@thewoolleyman.com>
author_llm: claude-opus-4-7
---

## Decision and Rationale

Impl→spec ratification of the --project-root and --work-items-path flags accepted by list-work-items and next wrappers. These flags are load-bearing for doctor's cross-boundary handoffs (entries 4 and 5 of §"Cross-boundary handoffs"), which invoke wrappers from outside the consumer project root. Explicitly does NOT touch the next.py --limit/--offset gap (called out in the PC's Open question section) — that remains a separate spec→impl gap for capture-impl-gaps to surface.

## Resulting Changes

- contracts.md

---
proposal: retire-memo-surface.md
decision: accept
revised_at: 2026-06-20T16:58:43Z
author_human: thewoolleyman <chad@thewoolleyman.com>
author_llm: livespec-impl-git-jsonl-w7
---

## Decision and Rationale

W7 step-3 memo retirement, symmetric with impl-beads. The memo entity, its three skills (capture-memo, process-memos, list-memos), the memos.jsonl store, and the Memos JSONL record schema are removed; the work-items store, the Persistent Agent Knowledge (.ai/) store, and every non-memo surface are preserved. archive/memos.jsonl stays as a frozen historical artifact.

## Resulting Changes

- spec.md
- contracts.md
- constraints.md
- scenarios.md
- ../tests/heading-coverage.json

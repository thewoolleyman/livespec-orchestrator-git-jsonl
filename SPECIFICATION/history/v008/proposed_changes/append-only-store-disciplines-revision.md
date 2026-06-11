---
proposal: append-only-store-disciplines.md
decision: accept
revised_at: 2026-06-11T00:19:36Z
author_human: thewoolleyman <chad@thewoolleyman.com>
author_llm: claude-fable-5
---

## Decision and Rationale

Pre-authorized W5 migration (livespec-p7az): the disciplines relocate from livespec's rejected append-only-store-legibility-and-merge-safe-reduction PC (livespec commit 01c8324) into the repo that owns the orchestrator-private stores; no contradiction with the existing schema sections surfaced (superseded_by remains the entity-level amendment marker; supersedes is the per-record supersession pointer the reduction consumes).

## Resulting Changes

- contracts.md
- ../tests/heading-coverage.json

---
proposal: rename-orchestrator-git-jsonl-refs.md
decision: accept
revised_at: 2026-06-22T01:14:07Z
author_human: E2E Test <e2e-test@example.com>
author_llm: orchestrator-rename-4moata.4.14
---

## Decision and Rationale

Pure citation/identifier rename aligning the dogfooded spec prose with the orchestrator-rename wave: livespec-impl-git-jsonl -> livespec-orchestrator-git-jsonl across the current spec files. No semantic change; the tenant == repo == livespec-orchestrator-git-jsonl (31 chars, within Dolt's 32-char limit) so the replacement is unambiguous. History snapshots are immutable and untouched; the H2 heading set is unchanged, so tests/heading-coverage.json needs no co-edit.

## Resulting Changes

- spec.md
- contracts.md
- constraints.md
- scenarios.md
- README.md

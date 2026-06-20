---
topic: retire-memo-surface
author: livespec-impl-git-jsonl-w7
created_at: 2026-06-20T16:55:02Z
---

## Proposal: Retire the memo surface

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/contracts.md
- SPECIFICATION/constraints.md
- SPECIFICATION/scenarios.md

### Summary

Remove the memo entity and its entire skill/store/schema surface from this plugin's specification. Memo is retired as a first-class surface across the livespec family (W7); the work-item ledger absorbs its actionable function, /livespec:propose-change absorbs its spec-bound function (via capture-spec-drift), and the Persistent Agent Knowledge (.ai/<topic>.md) store remains for persistent-knowledge content. The three memo skills (capture-memo, process-memos, list-memos), the memos.jsonl store, the Memos JSONL record schema, and every memo clause are deleted; the work-items store and Persistent Agent Knowledge realization are preserved.

### Motivation

Symmetric with the impl-beads memo retirement in the same W7 step. The memo lifecycle (capture -> triage -> disposition) duplicated routing that the work-item ledger and the spec-side propose-change flow already provide. Keeping a second transient store and three skills to feed it is dead surface now that the auto-memory redirect (livespec core v123) and the Driver's block-auto-memory.sh hook (livespec-driver-claude PR #23) both point at capture-work-item rather than capture-memo. The Persistent Agent Knowledge store is NOT a memo concept and is retained; only the memo machinery that routed INTO it is removed.

### Proposed Changes

spec.md: drop "Memos" from the inherited-terminology parenthetical; delete the "JSONL record (memo)" term; drop the "memo" arm from the "Latest-record-wins reduction" term; remove `memos.jsonl` from the default-paths bullet under Substrate properties. contracts.md: rename "## The ten-skill surface" to "## The seven-skill surface" and re-count to "Heavyweight authored skills (4)" + "Thin-transport skills (3)"; delete the `#### capture-memo`, `#### process-memos`, and `#### list-memos` sub-sections; delete the entire "## Memos JSONL record schema" H2 section; drop the `memos.jsonl` mentions and the `list-memos` reference from "## Append-only store disciplines"; drop `process-memos` from the Spec Reader consumer list; drop the memo-writing sentence from "## Persistent Agent Knowledge realization" (the .ai/ store stays; persistent-knowledge content now arrives via the work-item/knowledge flow, not process-memos); remove `memos_path` from the `## compat block` example and its description; remove the two memo-related cross-boundary handoffs (process-memos -> propose-change, doctor -> list-memos) from "## Cross-boundary handoffs" and renumber the rest; fix the `next` candidates note that referenced `list-memos --filter=untriaged`. constraints.md: drop memos from the append-only / schema-conformance / materialized-view bullets under "## JSONL substrate constraints"; drop capture-memo + process-memos from the heavyweight list and list-memos from the thin-transport list under "## Skill orchestration constraints"; drop the process-memos persistent-knowledge clause under "## Persistent Agent Knowledge constraints" (the .ai/ orphan-reference rule stays); delete the "No memo deletion" forbidden-pattern bullet. scenarios.md: delete "## Scenario 2 - Memo -> spec-bound disposition" and "## Scenario 3 - Memo -> persistent-knowledge graduation"; renumber the remaining scenarios so the set is Scenario 1..4 with no gaps; strip the memo-probe references from the Doctor cross-boundary read scenario and the Layer 3 loop driver scenario. archive/memos.jsonl is a FROZEN historical artifact and is NOT touched.

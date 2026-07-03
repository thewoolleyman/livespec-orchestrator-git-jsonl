---
proposal: full-autonomous-mode.md
decision: accept
revised_at: 2026-07-03T00:29:55Z
author_human: thewoolleyman <chad@thewoolleyman.com>
author_llm: claude-opus-4-8
---

## Decision and Rationale

Accept the full-autonomous-mode proposal as authored. It lands the git-jsonl plugin's dangerous, default-off --autonomous mode scoped to the consent gates this plugin owns (its four heavyweight skills) plus closure narration: a spec.md Autonomous mode section + terminology, the contracts.md --autonomous binding on the heavyweight skills and the new decided_by human|autonomous JSONL key (twenty-key schema, required-on-write/optional-on-read), the Autonomous mode constraints in constraints.md, and Scenario 5. The deep admission/acceptance autonomy is correctly left to livespec-orchestrator-beads-fabro and noted rather than over-reached here. Placement respects the behavior->clause+scenario, functional-placement, and cross-repo splits.

## Resulting Changes

- spec.md
- contracts.md
- constraints.md
- scenarios.md

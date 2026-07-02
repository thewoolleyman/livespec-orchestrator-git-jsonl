---
proposal: carry-acceptance-criteria-and-notes-in-record-schema.md
decision: accept
revised_at: 2026-07-02T09:15:24Z
author_human: thewoolleyman <chad@thewoolleyman.com>
author_llm: livespec-fleet-followups
---

## Decision and Rationale

Widen the canonical work-items JSONL record schema from seventeen to nineteen keys, adding acceptance_criteria and notes as optional-on-read fields, to match the vendored livespec_runtime v0.8.0 WorkItem (serialized on every record via asdict) and unblock the v0.8.0 vendor bump. Consistent with the existing spec_commitment_hint/supersedes optional-on-read treatment; legacy records read the new fields back as null without firing a schema violation.

## Resulting Changes

- contracts.md

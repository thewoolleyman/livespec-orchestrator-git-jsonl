---
proposal: factory-routing-retire-legacy.md
decision: accept
revised_at: 2026-10-24T06:43:48Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: claude-opus-5-5
---

## Decision and Rationale

Fleet capacity coordinator ruling (2026-10-24): hp-xubuntu's legacy Fabro instance is being retired, so the committed factory table stops declaring `legacy`. The requirement existed to keep legacy-pinned open items resolvable; the petri-factory-on-gmktec seat triaged every such item fleet-wide and none needs a run read from hp, and a pin naming an undeclared factory falls back to `default_factory`. The same change removes the entry from .livespec.jsonc and updates the conformance tests. Independent read-only ratification review (fable) of the exact final bytes: NO BLOCKERS on digest d76f8982.

## Resulting Changes

- constraints.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: fable
reviewer_identity: fable
separate_reviewer: True
read_only: True
reviewed_at: 2026-10-24T06:40:00Z
verdict: NO BLOCKERS
proposal_stem: factory-routing-retire-legacy
content_digest: d76f89825056033672cce07bcdf537b814326a1e5a9d4b615f0fcf99ef70c670

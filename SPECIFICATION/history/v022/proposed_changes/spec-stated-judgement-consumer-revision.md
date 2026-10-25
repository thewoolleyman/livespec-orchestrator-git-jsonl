---
proposal: spec-stated-judgement-consumer.md
decision: modify
revised_at: 2026-10-25T01:26:59Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: claude-opus-5-5
---

## Decision and Rationale

ACCEPTED IN SUBSTANCE, MODIFIED IN TEXT. This is plan spec-implementation-lockstep's P5 (epic bd-ib-ax3rds). It makes git-jsonl's two implementation assertions (bd-ib-jik5ko) spec-governed: the ledger-intent scan, the impl-drift front-end and the filing take their verdicts from livespec_runtime.spec_stated, and a feature judged partial or unstated is filed with the shared spec-change tier and its linked proposal topic. It amends the existing clauses (capture-spec-drift, capture-work-item, the record schema, Scope boundary, Scenario 5) and adds only one new heading, Scenario 6, because the filing path has no existing scenario to generalize. No dispatch hold is added, because this plugin runs no Dispatcher. Implementation needs the vendored livespec-runtime bumped from v0.20.0 to at least v0.28.0, which is owned by the implementing work. Decided under revise_decision_mode delegated (non-drift proposal) by the plan session, per the maintainer's autonomy ruling recorded on epic bd-ib-ax3rds on 2026-10-25.

## Modifications

Modified after three rounds of independent read-only review (claude-fable-5-1 through headless claude -p, a separate process from the authoring session). Rounds 1 and 2 returned BLOCKERS; round 3 returned NO BLOCKERS on these exact bytes. Deltas from the filed proposal:
1. capture-spec-drift keeps "heuristically (LLM-driven)": an LLM pass extracts candidate behaviour statements and each candidate is then judged. The prohibition is scoped to "a stated/unstated prompt, verdict schema or verdict parser of its own", so the paragraphs referring to "the impl → spec heuristic" keep a referent.
2. The skill states how run_model is supplied: by the invoking agent session, through a two-phase capture-then-answer use of judge, so the prompt is never rendered outside the module.
3. capture-work-item records the resulting tier, not the class; the class is not persisted. The judge statement is the item's title and description.
4. A declined or failed linked-proposal handoff still records tier spec-change with the verdict and linked_proposal_topic null. A bug/chore/non_functional item records tier none and verdict null. A feature judged stated records tier none with its stated verdict.
5. Cross-boundary handoffs gains entry 4: capture-work-item → /livespec:propose-change.
6. The spec_change_tier schema bullet no longer enumerates the runtime's fields. It defines the JSONL serialization of the vendored SpecChangeTier (one key per dataclass field, tuple as JSON array, None as null), says what judged_at records, lists gap-tied capture-impl-gaps records among the null cases, and requires a closing or amending record to carry forward the chain head's value.
7. Scope boundary says this spec names the verdict values only by reference, and states only where verdicts are obtained and how the tier is serialized.
8. Scenario 5 step 2 also counts partial. Scenario 6 adds the decline branch (step 5) and the bug branch (step 6).
9. Committed in the same PR, outside the CLI's spec-target resulting_files: the tests/heading-coverage.json row for Scenario 6 (test TODO, owned by bd-gj-bez, a covering-test item filed in this repo's tenant, with an owed-test reason), and the regenerated tests/heading-coverage-debt.json row.
Non-blocking round-3 advisories left for follow-up: re-judging on a later append, the drift path when a judgement cannot run, linked_proposal_topic null named in the bug-path prose, and the ledger-intent statement composition.

## Resulting Changes

- contracts.md
- scenarios.md
- spec.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: fable
reviewer_identity: fable
separate_reviewer: True
read_only: True
reviewed_at: 2026-10-25T01:25:45Z
verdict: NO BLOCKERS
proposal_stem: spec-stated-judgement-consumer
content_digest: 0993dd156716fda97dba8ddf8e92939c917254bcddbb32a2afa1e620d5c893f6

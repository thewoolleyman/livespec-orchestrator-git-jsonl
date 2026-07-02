---
topic: carry-acceptance-criteria-and-notes-in-record-schema
author: livespec-fleet-followups
created_at: 2026-07-02T09:14:38Z
---

## Proposal: carry-acceptance-criteria-and-notes-in-record-schema

### Target specification files

- SPECIFICATION/contracts.md

### Summary

Widen the work-items JSONL record schema from seventeen to nineteen canonical keys by adding the optional-on-read acceptance_criteria and notes fields, matching the vendored livespec_runtime v0.8.0 WorkItem.

### Motivation

livespec_runtime v0.8.0 adds first-class optional acceptance_criteria and notes fields to the WorkItem model and serializes them on every record. The git-jsonl store adapter serializes WorkItem via asdict, so every appended record now carries these two keys. The current spec caps the canonical schema at seventeen keys and forbids extras, so the store no-extra-keys invariant would reject every v0.8.0 record. Widening the schema to nineteen keys, with both new fields optional-on-read (legacy records read back as null, no violation) consistent with how spec_commitment_hint and supersedes are treated, reconciles the contract with the runtime model and unblocks the v0.8.0 vendor bump.

### Proposed Changes

In the section 'Work-items JSONL record schema': (1) change 'seventeen keys ... canonical schema' to 'nineteen keys'; (2) extend the optional-on-read sentence so spec_commitment_hint, supersedes, acceptance_criteria, and notes are all required-on-write but optional-on-read (legacy records read back as null without a violation); (3) change 'Additional keys beyond this seventeen are forbidden' to 'nineteen'; (4) add two field bullets: acceptance_criteria (string or null; the vendored WorkItem.acceptance_criteria definition-of-done) and notes (string or null; the vendored WorkItem.notes free-form notes), each optional-on-read and always written on append. No H2/H3 headings change, so heading-coverage is untouched.

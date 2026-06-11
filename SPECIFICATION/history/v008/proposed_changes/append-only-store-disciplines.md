---
topic: append-only-store-disciplines
author: claude-fable-5
created_at: 2026-06-11T00:19:22Z
---

## Proposal: append-only-store-disciplines

### Target specification files

- SPECIFICATION/contracts.md

### Summary

Migrate the append-only-store disciplines from livespec's formally REJECTED proposed change append-only-store-legibility-and-merge-safe-reduction (rejected at the livespec v103/v104 revise, 2026-06-09, per decision-record item 6 of contract-and-reference-implementations-phase-1; source: livespec commit 01c8324) into this repo's SPECIFICATION, adapted to its role as the git-jsonl reference orchestrator whose work-items/memos stores are the orchestrator-private Ledger.

### Motivation

The rejection rationale was relocation, not refusal: under the re-steered contract core never reads the stores, so order-independent reduction, record self-identification, read-path-via-query-surface, a single canonical reducer, and the no-divergent-heads / no-raw-store-read integrity checks belong in the repo that owns the store. The 2026-05-30 openbrain incident (two physical records for one id misread as duplicates; order-based reduction unsafe under git merge) motivates each discipline.

### Proposed Changes

In SPECIFICATION/contracts.md: (1) extend the Work-items JSONL record schema from fifteen to sixteen keys with a `supersedes` supersession pointer (required-on-write, optional-on-read; null marks an original record); (2) replace the §"Materialized view" file-order rule with an order-independent supersession-chain-head reduction (deterministic tie-break: captured_at, then stable per-record identity; divergent heads representable and detectable; the file-order rule is DEPRECATED interim behavior until realization lands); (3) add the same `supersedes` key to the Memos JSONL record schema; (4) add a new H2 §"Append-only store disciplines" carrying the scope definition (git-committed append-structured store), record self-identification, read-path-only-via-query-surface, one-canonical-reducer, the two orchestrator-private store-integrity checks wired into just check (no-divergent-heads, no-raw-store-read), and the merge=union .gitattributes obligation; (5) record the provenance citation. Realization is tracked as follow-up work-items in this repo's work-item store.

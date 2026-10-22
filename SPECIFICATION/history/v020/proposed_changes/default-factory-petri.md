---
topic: default-factory-petri
author: claude-opus-5-5
created_at: 2026-10-22T22:18:09Z
---

## Proposal: Default factory petri

### Target specification files

- constraints.md

### Summary

Change the `## Factory routing` default-factory sentence so `dispatcher.default_factory` MUST name `petri` instead of `legacy`, with `legacy` remaining a declared registry-backed entry. Nothing else in the section changes.

### Motivation

Maintainer direction relayed by coordinator session gitops-fleet-capacity-monitoring as ruling R668 moves this repository's dispatch default from the `legacy` Fabro factory to `petri`, the current Fabro server; ruling R672 approves this spec revise as a delegated decision (work-item bd-ib-iud52v). The committed `.livespec.jsonc` now declares a registry-backed `petri` entry beside the existing registry-backed `legacy` entry and sets `dispatcher.default_factory` to `petri`; the ratified sentence still pins `legacy`, so it must move with the config. Only the default-factory sentence changes; the registry-backed and no-machine requirements are unchanged.

### Proposed Changes

In constraints.md §"Factory routing", replace the final sentence

`dispatcher.default_factory` MUST name `legacy`.

with

`dispatcher.default_factory` MUST name `petri`; `legacy` remains a declared
registry-backed entry.

No heading is added, renamed or removed; every other sentence of the section stays verbatim.

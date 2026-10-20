---
topic: factory-routing
author: claude-opus-5-5
created_at: 2026-10-20T15:29:19Z
---

## Proposal: Factory routing

### Target specification files

- constraints.md

### Summary

Add a `## Factory routing` section requiring every committed dispatcher.factories entry in .livespec.jsonc to be registry-backed ("registry": true, no server, no docker_host) so no committed factory entry names a machine, and requiring dispatcher.default_factory to name legacy.

### Motivation

Coordinator rulings R318 and R320 (2026-10-20, plan petri-factory-on-gmktec, epic bd-ib-fyozyd) require every fleet repository's committed factory table to be registry-backed and name no machine; a factory is bound to a machine only in the fleet gitops inventory's factory registry. This heading is the governing clause the registry-switch work-item references. This repository's CI doctor job checks out only livespec core, so the livespec-dev-tooling registry section is cited in prose rather than through an external_references allowlist entry.

### Proposed Changes

Add this H2 and body verbatim to constraints.md, immediately before `## Forbidden patterns`:

## Factory routing

Every entry this repository commits in `.livespec.jsonc` under
`dispatcher.factories` MUST be registry-backed: it declares `"registry": true`
and carries no `server` and no `docker_host` value, so no committed factory
entry names a machine. Which Fabro server answers to a factory name is bound
only in the fleet gitops inventory's factory registry (the Fabro factory
registry section of `livespec-dev-tooling/SPECIFICATION/non-functional-requirements.md`),
which each dispatching host renders as `/etc/livespec/fabro-factories.json`; a
dispatch resolves a registry-backed entry from that file by name.
`dispatcher.default_factory` MUST name `legacy`.

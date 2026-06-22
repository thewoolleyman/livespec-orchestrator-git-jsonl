---
topic: rename-orchestrator-git-jsonl-refs
author: orchestrator-rename-4moata.4.14
created_at: 2026-06-22T01:10:47Z
---

## Proposal: Rename impl-git-jsonl plugin and repo references to orchestrator-git-jsonl

### Target specification files

- spec.md
- contracts.md
- constraints.md
- scenarios.md
- README.md

### Summary

Align the dogfooded specification prose with the orchestrator-rename wave: replace every reference to the retired plugin/repository/package name `livespec-impl-git-jsonl` with the current name `livespec-orchestrator-git-jsonl` across the current spec files.

### Motivation

The reference orchestrator was renamed family-wide (the `impl-` prefix dropped to `orchestrator-`): GitHub repository, local clone, Python package, plugin identity and the `/livespec-orchestrator-git-jsonl:*` skill namespace, configs, CI, and the Beads tenant (`livespec-orchestrator-git-jsonl`, 31 chars, == repo). The dogfooded SPECIFICATION prose still cites the retired `livespec-impl-git-jsonl` name, so the spec describes a repo/plugin that no longer exists under that name. This is the spec-prose half of the rename wave (work-item 4moata.4.14).

### Proposed Changes

Replace every occurrence of the literal string `livespec-impl-git-jsonl` with `livespec-orchestrator-git-jsonl` in the CURRENT spec files only: `spec.md`, `contracts.md`, `constraints.md`, `scenarios.md`, and `README.md`. This is a pure citation/identifier rename with no semantic change. For this repo the Beads tenant == repo == `livespec-orchestrator-git-jsonl` (31 chars, within Dolt's 32-char username limit), so the replacement is unambiguous in every context: the H1 title lines, the `/livespec-orchestrator-git-jsonl:` namespace prose, and the `.livespec.jsonc` connection JSONC example. Do NOT modify `SPECIFICATION/history/` — those vNNN snapshots are immutable frozen records and intentionally retain the historical name. The H2 (`## `) heading set is unchanged by this rename, so `tests/heading-coverage.json` needs no co-edit.

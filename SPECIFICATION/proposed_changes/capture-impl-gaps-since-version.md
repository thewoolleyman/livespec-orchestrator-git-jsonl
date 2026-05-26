---
topic: capture-impl-gaps-since-version
author: claude-opus-4-7
created_at: 2026-05-26T07:30:00Z
---

## Cross-cutting parent

This PC is part of the coordinating epic `livespec#coordinating-epic-stale-revise-enforcement` (filed at `livespec/SPECIFICATION/proposed_changes/coordinating-epic-stale-revise-enforcement.md`, merged on master via livespec PR #247). It extends the original 4-layer enforcement story with a Layer 5 contribution: ensuring spec changes accepted by `/livespec:revise` don't sit and never reach impl tracking because no one remembered to invoke gap detection.

This PC does NOT yet carry a `parent_proposed_change` front-matter field. That field is itself proposed in the parent PC (which has to widen `livespec`'s `proposed_change_front_matter.schema.json`). After acceptance, this PC SHOULD be retroactively edited to add `parent_proposed_change: livespec#coordinating-epic-stale-revise-enforcement`.

The Layer 5 companion PC lives at `livespec/SPECIFICATION/proposed_changes/revise-post-step-capture-impl-gaps.md` (Layer 5 in the parent epic's framing).


## Problem statement

`/livespec-impl-plaintext:capture-impl-gaps` (and its underlying `detect-impl-gaps` thin-transport sibling) scans the entire `<spec-root>/` tree on every invocation. The skill has no notion of "what changed in the most recent revise vs the prior version" — it walks every MUST / SHOULD clause in every spec file as if every clause is equally fresh.

This produces two problems for the use case the coordinating epic's Layer 5 needs:

1. **Noisy post-step**. If `/livespec:revise`'s post-step invokes `capture-impl-gaps` unconditionally, every revise re-prompts the user for every long-standing gap in the spec. The user trains themselves to skip the prompt; the signal value collapses.

2. **No targeted attention on new spec content**. After a revise that accepts (say) a single proposed change, the impl side most needs to attend to gaps introduced by THAT change. The current skill mixes new gaps with stale ones with no way to distinguish.

The underlying Spec Reader already has the cross-version diff machinery — `SpecSnapshot`, `SpecDiff`, and `FileDiff` dataclasses in `livespec_impl_plaintext/types.py` carry exactly the deltas we want. The detect-impl-gaps surface just doesn't consume them.


## Proposal: add --since-version flag to detect-impl-gaps

### Target specification files

- SPECIFICATION/contracts.md

### Summary

Extend the `detect-impl-gaps` thin-transport skill (and the underlying `detect_impl_gaps.py` script) with an optional `--since-version <vN>` flag. When passed, the skill restricts its MUST / SHOULD clause scan to spec files whose content differs between version `<vN>` and the live spec. When omitted, the skill scans every file (current whole-spec behavior, unchanged).

### Motivation

This is the surface extension that makes per-revise post-step focus possible. Without it, `capture-impl-gaps` (which calls this primitive) cannot scope to recent changes.

The Spec Reader already computes `SpecDiff(version_a=vN, version_b=<live>)` for any historical version — the machinery is shipped and tested. This proposal connects that machinery to the gap-detection surface that didn't previously consume it.

### Proposed Changes

Update `SPECIFICATION/contracts.md` §"`detect-impl-gaps` thin-transport surface" (or the section that codifies this skill — confirmed at revise time) to add the new flag:

> **`--since-version <vN>`** (optional, default `null`). When set to a historical version integer that exists under `<spec-root>/history/v<NNN>/`, the skill restricts its scan to files whose content differs between `<vN>` and the live spec (i.e., the file appears in `SpecDiff(version_a=<vN>, version_b=<live>).per_file`). For each such file, only MUST / SHOULD clauses present in the live version are considered (clauses removed by the diff are not gaps — they were spec content that no longer exists).
>
> Validation:
> - The value MUST be a positive integer. Non-integer / negative input exits `2` with a usage error.
> - The version directory `<spec-root>/history/v<padded-N>/` MUST exist. Missing version exits `3` with `PreconditionError` naming the expected path.
>
> When omitted, the behavior is unchanged from the pre-flag version — scan every file in the live spec.

Update the script `.claude-plugin/scripts/bin/detect_impl_gaps.py` to accept the flag (impl follow-up, not part of this PC; tracked as a work-item after acceptance).


## Proposal: add --since-version pass-through to capture-impl-gaps

### Target specification files

- SPECIFICATION/contracts.md

### Summary

Update the `capture-impl-gaps` heavyweight skill's invocation contract to accept the same `--since-version <vN>` flag and pass it through to `detect-impl-gaps` (called twice — once with `--json` for the authoritative gap-id set, once without for rich human-readable display per the existing Step 1 protocol).

Per-rule classification (Step 2), per-gap consent (Step 3), and summary (Step 4) are unchanged.

### Motivation

`capture-impl-gaps` is the user-facing wrapper. The pass-through is the user-facing surface for "scope this gap-detection pass to recent changes."

### Proposed Changes

Update `SPECIFICATION/contracts.md` §"`capture-impl-gaps` heavyweight skill" (or the section codifying this skill) to document the new flag:

> **`--since-version <vN>`** (optional). When set, passed through verbatim to both `detect-impl-gaps` invocations (the `--json` authoritative-set call and the rich-display call). Validation is delegated to the underlying skill — if the value is invalid, `detect-impl-gaps` exits `2` or `3` and `capture-impl-gaps` surfaces the error and aborts.
>
> The flag is the surface that callers (notably `/livespec:revise`'s post-step per the parent coordinating epic) use to scope per-revise gap detection. Direct user invocations MAY use it as well for any "show me gaps for changes since this version" workflow.

Update `skills/capture-impl-gaps/SKILL.md` Step 1 prose to mention the flag pass-through (impl follow-up).


## Acceptance criteria

This PC is complete when:

1. The `--since-version <vN>` flag is specified for both `detect-impl-gaps` and `capture-impl-gaps` in `contracts.md`.
2. The validation rules (integer, version-exists) are documented.
3. The pass-through behavior in `capture-impl-gaps` is documented.
4. Implementation follow-ups are tracked in `work-items.jsonl` after acceptance:
   - Update `detect_impl_gaps.py` to accept the flag and use `SpecDiff` to scope its scan.
   - Update `capture-impl-gaps`'s SKILL.md Step 1 to pass through the flag.
   - Paired tests in the standard mirror locations per red-green-replay TDD discipline.

The companion change at livespec (`revise-post-step-capture-impl-gaps`) — wiring revise's post-step to invoke `capture-impl-gaps --since-version <prior-vN>` — depends on this PC's acceptance but does NOT depend on the implementation follow-ups landing first; the livespec SKILL.md change can reference the flag prospectively.

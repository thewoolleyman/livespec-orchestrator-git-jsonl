---
topic: next-layer-3-discoverability-nudge
author: claude-opus-4-7
created_at: 2026-05-26T05:40:09Z
---

## Proposal: concretize-next-layer-3-discoverability-nudge-for-jsonl-substrate

### Target specification files

- SPECIFICATION/contracts.md

### Summary

Concretize the upstream contract clause (per the parallel propose-change `next-layer-3-discoverability-nudge` against `livespec/SPECIFICATION/contracts.md` §"`/livespec:next` spec-side thin-transport skill" → §"Layer 3 discoverability nudge" AND §"Implementation-plugin contract — the 10-skill surface" → `next` bullet) for this plugin's JSONL-substrate realization. Add a Layer-3-discoverability-nudge clause to `SPECIFICATION/contracts.md` §"next" requiring the `/livespec-impl-plaintext:next` SKILL.md prose to surface a one-time nudge before invoking the wrapper on direct user invocation, naming the project-local `.claude/skills/loop/SKILL.md` Layer 3 driver as the cohesive cross-side composition surface and asking the user to confirm direct invocation. The wrapper at `.claude-plugin/scripts/bin/next.py` remains a pure thin-transport pass-through.

### Motivation

This propose-change is the impl-side concretization of the upstream `next-layer-3-discoverability-nudge` contract clause; both are filed in parallel and coordinated by a tracking epic in `livespec`'s `work-items.jsonl`. The upstream clause pins the requirement at the cross-plugin contract layer (§"Implementation-plugin contract — the 10-skill surface" → `next` bullet); this local propose-change concretizes it for `livespec-impl-plaintext`'s JSONL substrate, naming the specific SKILL.md file and the specific wrapper path that participates.

The discoverability hole the upstream clause names applies symmetrically here: a user (or agent) who invokes `/livespec-impl-plaintext:next` directly gets only the impl-side ranking and no signal that the project-local Layer 3 driver at `.claude/skills/loop/SKILL.md` is the cohesive surface combining `/livespec:next` with this skill. The upstream architectural rule ("Cross-side composition belongs at Layer 3"; "Livespec-core MUST NOT bake a particular weighting in; impl plugins MUST NOT either" — per `livespec/SPECIFICATION/spec.md` §"Three-layer orchestration architecture") is load-bearing and correct, but without the nudge, the rule's beneficiaries cannot discover it.

The fix is a one-time SKILL.md-prose nudge that the agent surfaces before invoking the wrapper. The wrapper itself stays pure (no flag, no confirmation dialogue, no exit-code change). This matches the thin-transport doctrine codified in `livespec/SPECIFICATION/contracts.md` §"Thin-transport skill doctrine" — SKILL.md is the LLM-driven shaping layer the agent reads, and the wrapper is the pure-function layer below. Adding the nudge in SKILL.md prose is the only architecturally clean seam.

### Proposed Changes

**Edit 1.** Append to `SPECIFICATION/contracts.md` §"next" (the impl-plugin's `next` thin-transport skill subsection under §"Thin-transport skills (4)") a new subsection at the end of the section:

> #### Layer 3 discoverability nudge
>
> Per the upstream cross-plugin contract clause (`livespec/SPECIFICATION/contracts.md` §"Implementation-plugin contract — the 10-skill surface" → `next` bullet → "Layer 3 discoverability nudge"), the `/livespec-impl-plaintext:next` SKILL.md prose at `.claude-plugin/skills/next/SKILL.md` MUST surface a one-time discoverability nudge before invoking the wrapper on direct user invocation. The nudge MUST:
>
> 1. Inform the user that `.claude/skills/loop/SKILL.md` (the project-local Layer 3 loop driver per `livespec/SPECIFICATION/spec.md` §"Three-layer orchestration architecture" → "Layer 3 — Project-local composition") is the cohesive cross-side composition surface, combining `/livespec:next` (spec-side ranking over `<spec-root>/proposed_changes/` and `<spec-root>/history/`) with `/livespec-impl-plaintext:next` (impl-side ranking over the JSONL work-items store).
> 2. Ask the user to confirm they want to run `/livespec-impl-plaintext:next` directly rather than via the project's Layer 3 driver.
> 3. Skip the nudge when `/livespec-impl-plaintext:next` is invoked by another skill (e.g., the Layer 3 driver itself, the `doctor` cross-boundary surface) rather than by a direct user request. The detection mechanism is per-harness and out of scope here.
>
> The nudge lives entirely in SKILL.md prose. The wrapper at `.claude-plugin/scripts/bin/next.py` MUST NOT accrete a confirmation dialogue, an opt-in flag, or any other interactive layer — the wrapper remains a pure thin-transport pass-through per the upstream §"Thin-transport skill doctrine" and this plugin's §"Thin-transport skills (4)" preamble. The nudge is informational: it points the user at the Layer 3 surface but never selects the cross-side weighting itself, preserving the upstream §"Cross-side composition exclusion" invariant for this skill.
>
> The nudge wording MAY name the JSONL substrate (e.g., "the impl-side ranking is a pure function of the work-items JSONL store at `<work_items_path>`") to help the user understand what `/livespec-impl-plaintext:next` returns in isolation, but the load-bearing semantic (point at Layer 3; ask to confirm direct invocation) MUST be preserved verbatim per the upstream cross-plugin contract.

**Edit 2 (companion downstream change).** This contract clause requires `.claude-plugin/skills/next/SKILL.md` to be regenerated at the next `/livespec:revise` pass. The regenerated SKILL.md MUST add the nudge prose described above before the existing wrapper invocation instructions. Existing wrapper invocations from non-user contexts (e.g., the Layer 3 `loop` driver invoking `/livespec-impl-plaintext:next --json`, doctor's cross-boundary handoffs) MUST continue to work without surfacing the nudge — the SKILL.md prose distinguishes the contexts via the standard invocation-context conventions documented in the Claude Code skill harness.

This propose-change is filed in parallel with the upstream `livespec` repo's `SPECIFICATION/proposed_changes/next-layer-3-discoverability-nudge.md` (PR #245). The two PRs are coordinated by a tracking epic in `livespec`'s `work-items.jsonl` whose `depends_on` array references both PRs via the cross-repo `pull_request` `DependsOnEntry` kind (per `livespec/SPECIFICATION/contracts.md` §"Cross-repo dependency awareness" → §"DependsOnEntry typed union"). The epic stays open until both PRs merge.

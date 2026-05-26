---
name: next
description: Rank the most-ripe impl-side action from the JSONL work-items store. Required thin-transport surface per livespec/SPECIFICATION/contracts.md §"Thin-transport skills (3) — required machine query surface". Pure function of file state; no LLM in the ranking path. Invoke as `/livespec-impl-plaintext:next [--json]`.
allowed-tools: Bash
---

# next

Thin-transport pass-through. All behavior lives in
`.claude-plugin/scripts/livespec_impl_plaintext/commands/next.py`.

## Invocation

```bash
uv run python3 .claude-plugin/scripts/bin/next.py "$@"
```

Supported flags:

- `--json` — emit the recommendation as JSON
  `{action, work_item_ref, urgency, reason}`
- `--work-items-path <path>` — override the default location

## Output schema

Per livespec/SPECIFICATION/contracts.md §"Implementation-plugin
contract — the 9-skill surface" → next:

```json
{
  "action": "implement" | "none",
  "work_item_ref": "<id>" | null,
  "urgency": "high" | "medium" | "low",
  "reason": "<one-line narration>"
}
```

## Layer 3 discoverability nudge

On direct user invocation (the user typed
`/livespec-impl-plaintext:next` or asked for the next impl-side
move in plain language), before invoking the wrapper, surface a
one-time nudge per livespec/SPECIFICATION/contracts.md
§"Implementation-plugin contract — the 10-skill surface" → `next`
bullet, parallel-and-symmetric to the upstream `/livespec:next`
nudge documented at livespec's `.claude-plugin/skills/next/SKILL.md`
§"Layer 3 discoverability nudge". The nudge MUST:

- Inform the user that `.claude/skills/loop/SKILL.md` (the
  project-local Layer 3 loop driver per livespec/SPECIFICATION/spec.md
  §"Three-layer orchestration architecture" → "Layer 3 — Project-local
  composition") is the cohesive cross-side composition surface that
  combines `/livespec:next` (spec-side ranking over
  `<spec-root>/proposed_changes/` and `<spec-root>/history/`) with
  `/livespec-impl-plaintext:next` (impl-side ranking over the JSONL
  work-items store at `<work-items-path>`).
- Ask the user to confirm they want to run
  `/livespec-impl-plaintext:next` directly rather than via the
  project's Layer 3 driver.

SKIP the nudge when `/livespec-impl-plaintext:next` is invoked by
another skill (e.g., the Layer 3 driver itself, the `doctor`
cross-boundary surface consuming `--json` output, the `implement`
skill chaining its own ranking pass) rather than by a direct user
request. The detection mechanism is per-harness; this skill simply
gates the nudge on whether the entry path is a direct user
invocation.

When `.claude/skills/loop/SKILL.md` is absent in the current
project (the file is OPTIONAL per livespec/SPECIFICATION/spec.md
§"Layer 3 — Project-local composition"), the nudge MAY soften to a
documentation pointer (e.g., "consider authoring a Layer 3 loop
driver per livespec/SPECIFICATION/spec.md §...") rather than being
suppressed. The discoverability discipline applies whenever direct
user invocation is the entry path, regardless of whether the driver
exists.

The nudge is informational only — it points the user at the Layer 3
surface but never selects the cross-side weighting itself,
preserving the §"Cross-side composition exclusion" invariant. The
wrapper at `.claude-plugin/scripts/bin/next.py` MUST NOT accrete any
confirmation dialogue or opt-in flag; the nudge is SKILL.md-prose
discipline only.

## When to use

- User asks "what should I work on next?"
- The project-local Layer 3 loop driver composes
  `/livespec:next` + `/livespec-impl-plaintext:next` outputs into
  per-iteration recommendations.

## What this skill does NOT do

- It does NOT mutate any state. Read-only by contract.
- It does NOT invoke an LLM. The ranking is deterministic per the
  algorithm documented in
  livespec-impl-plaintext/SPECIFICATION/contracts.md §"next".

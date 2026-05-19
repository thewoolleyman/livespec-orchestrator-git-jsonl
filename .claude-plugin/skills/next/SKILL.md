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

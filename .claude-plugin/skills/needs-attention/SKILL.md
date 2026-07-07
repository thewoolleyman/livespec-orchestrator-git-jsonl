---
name: needs-attention
description: Compose spec, implementation, human-valve, and hygiene gather primitives into a Markdown attention list. Invoke as `/livespec-orchestrator-git-jsonl:needs-attention [--project-root <path>]`.
allowed-tools: Bash
---

# needs-attention

Thin-transport pass-through. All behavior lives in
`.claude-plugin/scripts/livespec_orchestrator_git_jsonl/commands/needs_attention.py`.

## Invocation

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/bin/needs_attention.py" "$@"
```

Supported flags:

- `--json` — emit `{ "attention": [...] }` JSON for machine callers.
- `--project-root <path>` — override the project root used for store and manifest resolution.
- `--work-items-path <path>` — override the default work-items JSONL location.
- `--repo-name <name>` — override the repository label in attention items.
- `--skip-hygiene` — omit git hygiene findings from the point-in-time read.

## Output

Default output is Markdown for human review. `--json` emits the same flat
`attention[]` records as JSON.

The binding composes only the primitives this plugin ships: spec-side
`next`, impl-side `next`, `list-work-items` human-valve lanes, and hygiene
scan. This plugin has no plan skill, so it does not gather plan threads.

# livespec-impl-git-jsonl

The **JSONL-backed reference realization** of
[livespec](https://github.com/thewoolleyman/livespec)'s
implementation-plugin contract, and livespec's **designated dogfood
target**. As a Claude Code plugin it exposes the
`/livespec-impl-git-jsonl:*` impl-side skill surface — capturing
work-items, gaps, and drift, and driving implementation —
over a substrate of plain JSONL files committed alongside the
consumer project's own source. No embedded database, no external
service: every record is readable with `cat` and greppable with
`git grep`. That property is the principal reason livespec picked it
as the dogfood target (per `SPECIFICATION/spec.md` §"Purpose").

## Status

Active and maintained. This is ONE realization of the abstract
implementation-plugin contract livespec publishes in
[`livespec/SPECIFICATION/contracts.md`](https://github.com/thewoolleyman/livespec/blob/master/SPECIFICATION/contracts.md)
§"Implementation-plugin contract — the 10-skill surface". Other
realizations exist — notably
[livespec-impl-beads](https://github.com/thewoolleyman/livespec-impl-beads),
the family's current work-items backend. git-jsonl is not retired and
is not the active family backend; it is the reference realization and
the spec-side dogfood target, kept in lockstep with the livespec
template via copier re-syncs (`copier update --vcs-ref=master`; the
pinned reference is recorded in `.copier-answers.yml` and the
`.livespec.jsonc` `compat` block).

## Install

This is a Claude Code plugin. It is consumed by a livespec-governed
project, not run standalone:

```
/plugin marketplace add thewoolleyman/livespec-impl-git-jsonl
/plugin install livespec-impl-git-jsonl@livespec-impl-git-jsonl
```

After install, restart Claude Code (or run `/reload-plugins`). The
skills below become available with the `livespec-impl-git-jsonl:`
namespace prefix. A consumer project selects this plugin by naming it
in its `.livespec.jsonc` `implementation.plugin` block.

## The JSONL substrate — why it's the dogfood target

The substrate is the only thing unique to this plugin; everything
else (the skill names, the cross-boundary handoffs, the Spec Reader's
required-capability surface, the `compat` block format) is FIXED by
livespec's published contract, which this plugin concretizes rather
than re-states (per `SPECIFICATION/spec.md` §"Scope boundary").

- **Plain files, no service.** Work-items live in a
  git-tracked JSONL file (default `work-items.jsonl` at the
  consumer's project root; overridable via the
  `.livespec.jsonc` configuration block). Nothing the user can't read
  with `cat` or grep with `git grep`.
- **Append-only.** Skills only append new lines — never edit,
  truncate, or rewrite in place — so concurrent invocations can't
  corrupt each other's writes; conflicting concurrent appends are
  git's job to resolve, not the plugin's.
- **Latest-record-wins.** A record's current state is the LAST line
  keyed by `id`; earlier records stay in the file as audit trail.
  Deletion is NEVER performed by skill code.
- **The commit is the audit trail.** Every write produces a commit
  (inline or via the consumer's PR cycle).

Because the entire store is plain text under version control, the
spec ⇆ impl boundary is fully inspectable — which is exactly the
transparency livespec wants from its dogfood target.

## Skill surface

Seven skills per `SPECIFICATION/contracts.md` §"The seven-skill
surface" — four heavyweight authored skills and three thin-transport
machine query surfaces:

- `capture-impl-gaps` — detect spec→impl gaps and file gap-tied
  work-items with per-gap consent
- `capture-spec-drift` — detect impl→spec drift and hand each finding
  to `/livespec:propose-change`
- `capture-work-item` — freeform direct filing of an impl-side
  work-item
- `implement` — drive Red→Green for a single work-item
- `detect-impl-gaps` — emit the current gap-id set as JSON
  (thin-transport, read-only)
- `list-work-items` — list work-items from the JSONL store
  (thin-transport)
- `next` — rank the most-ripe impl-side action (thin-transport;
  pure function of file state, no LLM in the ranking path)

## Repo layout

This plugin dogfoods livespec: the `SPECIFICATION/` tree at the repo
root is its own live spec, governed through the standard `/livespec:*`
lifecycle.

| Path | Purpose |
|---|---|
| `.claude-plugin/` | Plugin manifest, marketplace, `skills/<name>/SKILL.md` bindings, and `scripts/` (the wrapper layer for thin-transport skills) |
| `SPECIFICATION/` | The plugin's own live livespec spec (`spec.md`, `contracts.md`, …), dogfooded |
| `dev-tooling/` | Standalone enforcement scripts + the commit-refuse / git-hook wrappers |
| `tests/` | pytest suite mirroring the scripts tree, plus `e2e-cli/` end-to-end checks |
| `archive/` | Frozen historical artifacts |
| `pyproject.toml`, `justfile`, `lefthook.yml`, `.mise.toml`, `.livespec.jsonc`, `.copier-answers.yml` | Toolchain + livespec/copier configuration |

## Development

```
just bootstrap   # one-time: primary-checkout guard hooks + lefthook + plugins
just check       # full enforcement aggregate (lint, types, tests, coverage, AST checks)
```

`just check` is the load-bearing safety net — it runs locally, in
pre-push, and in CI. The repo follows the livespec-family conventions:
`.mise.toml` pins the non-Python binaries (uv, just, lefthook), the
justfile is the single entry point for every check, lefthook delegates
to `just`, and the primary checkout refuses direct commits (work
happens in `git worktree add` secondaries). Product `.py` changes are
committed via the Red→Green commit-gate ritual described in
[AGENTS.md](AGENTS.md).

## Observability

The livespec family dogfoods its own telemetry. CI runs, Red→Green commit-gate cycles, the beads+fabro dispatcher, sandbox runs, and harness sub-agents are published to a shared Honeycomb environment:

- **[livespec family — all activity](https://ui.honeycomb.io/thewoolleyweb/environments/livespec/board/krThv8DvcwS)** — the cross-repo activity board (Honeycomb, `livespec` environment).

## More

- See [livespec](https://github.com/thewoolleyman/livespec) for livespec core (the contract, prose, CLIs, templates).
- See [`livespec/SPECIFICATION/contracts.md`](https://github.com/thewoolleyman/livespec/blob/master/SPECIFICATION/contracts.md) for the implementation-plugin contract this repo realizes.
- See [AGENTS.md](AGENTS.md) for the commit protocol and agent instructions.
- See [SPECIFICATION/](SPECIFICATION/) for this plugin's own dogfooded spec.

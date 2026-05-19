# Proposal: align with the upstream rename retirement

## Motivation

The upstream `livespec` project landed the `retire-livespec-core-rename`
propose-change at history/v068 (see
`livespec/SPECIFICATION/history/v068/proposed_changes/
retire-livespec-core-rename.md` for the full rationale). The upstream
project keeps the name `livespec`; the Phase E rename to
`livespec-core` is canceled.

`livespec-impl-plaintext`'s own SPECIFICATION/ was authored at v001
under the assumption that the rename would land. Every reference here
to `livespec-core`, `/livespec-core:<skill>`, and the
`livespec_core` compat semver-range key needs to follow the upstream
decision.

## Proposal

Revert every `livespec-core` reference in this plugin's spec tree,
SKILL.md prose, configuration manifests, and `.copier-answers.yml`
back to `livespec`. The companion changes:

- **SPECIFICATION/{spec,contracts,constraints,scenarios,README}.md** —
  every `livespec-core` becomes `livespec`; every
  `/livespec-core:<skill>` becomes `/livespec:<skill>`; every
  `livespec_core` compat key becomes `livespec`.
- **`.claude-plugin/skills/*/SKILL.md`** — same renames in the
  cross-boundary handoff narration (notably `capture-spec-drift`,
  `process-memos`, `implement`, `capture-impl-gaps`, and the
  thin-transport skills' "Authority" pointers).
- **`.claude-plugin/{plugin.json, marketplace.json}`** — description
  text updated; the plugin's own name (`livespec-impl-plaintext`) is
  unchanged.
- **`.livespec.jsonc`** — the compat block's `livespec_core` key
  renames to `livespec`.
- **`.copier-answers.yml`** — `_src_path` reverts from
  `gh:thewoolleyman/livespec-core/templates/impl-plugin` to
  `gh:thewoolleyman/livespec/templates/impl-plugin`. The variable
  `livespec_core_release_tag` renames to `livespec_release_tag`.

## Out-of-scope

- The skill behaviors, JSONL record schemas, Spec Reader API shape,
  and 9-skill surface enumeration are unchanged in form; only the
  name used to refer to the upstream changes.
- The plugin's own name `livespec-impl-plaintext` is unchanged.

## Acceptance

- No `livespec-core` references remain in any live spec file, SKILL.md,
  manifest, or config in this repo (history/v001/ snapshot retains
  its original text).
- `just check` is green.
- A v002 history snapshot captures the revise state; the
  proposed-change file moves into `history/v002/proposed_changes/`.

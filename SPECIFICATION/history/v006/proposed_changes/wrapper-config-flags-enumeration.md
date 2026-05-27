---
topic: wrapper-config-flags-enumeration
author: claude-opus-4-7
created_at: 2026-05-27T03:00:00Z
---

## Problem statement

Several thin-transport wrappers in `.claude-plugin/scripts/livespec_impl_plaintext/commands/` accept `--project-root <path>` and `--work-items-path <path>` flags that the v005 spec's CLI surface enumerations do NOT mention. Specifically:

- `commands/list_work_items.py` accepts `--project-root` (line 67) and `--work-items-path` (line 66). The v005 spec §"list-work-items" enumerates only `[--filter <name>] [--with-gap-id=<id>] [--json]`.
- `commands/next.py` accepts `--project-root` (line 56) and `--work-items-path` (line 55). The v005 spec §"next" enumerates `[--limit <count>] [--offset <count>] [--json]`.
- `commands/detect_impl_gaps.py` accepts `--project-root` (line 79). The v005 spec §"detect-impl-gaps" DOES enumerate `[--project-root <path>]` — so this one is reconciled.
- `commands/list_memos.py` likely accepts `--work-items-path` / `--memos-path` analogues — out of scope for this PC pending verification.

The `--project-root` and `--work-items-path` flags are load-bearing: doctor's cross-boundary handoffs (per §"Cross-boundary handoffs" entries 3, 4, 5) invoke wrappers from a working directory that may not be the consumer project root, and pass these flags to scope the invocation. A spec that doesn't enumerate them creates ambiguity about whether the flags are a stable contract or an undocumented impl detail subject to removal.


## Proposal: enumerate `--project-root` and `--work-items-path` on list-work-items

In `SPECIFICATION/contracts.md` §"list-work-items", update the CLI surface line to:

> CLI surface: `list-work-items [--filter <name>] [--with-gap-id=<id>] [--with-spec-commitment-hint=<id_hint>] [--json] [--work-items-path <path>] [--project-root <path>]`.

(The `--with-spec-commitment-hint` insertion is filed under the sibling PC `spec-commitment-hint-surfaces.md`; if both PCs land together, the union surface is the merged result. If only this PC lands, omit the `--with-spec-commitment-hint` token.)

And add a bullet:

> `--project-root <path>` — override the cross-repo manifest and store-path resolution base. Default: `Path.cwd()`. Used by doctor's cross-boundary handoffs to invoke this skill from outside the consumer project root.
>
> `--work-items-path <path>` — override the default `work-items.jsonl` location (the value resolved from the consumer's `.livespec.jsonc` `work_items_path` config). Used by tests and by doctor invocations that want to scope to a non-default store path.


## Proposal: enumerate `--work-items-path` and `--project-root` on next

In `SPECIFICATION/contracts.md` §"next", update the CLI surface line to:

> CLI surface: `next [--limit <count>] [--offset <count>] [--json] [--work-items-path <path>] [--project-root <path>]`.

And add bullets after the existing `--limit` / `--offset` bullets (mirroring the list-work-items prose above).


## Open question

The spec section for `next` (§"next") currently prescribes a paginated `{candidates: [...], pagination: {...}}` output schema with `--limit` and `--offset` flags. The impl at `commands/next.py` still emits the legacy single-object `{action, work_item_ref, urgency, reason}` shape and does NOT accept `--limit` or `--offset`. This is spec→impl drift (a gap, not a drift in the impl→spec direction), and the right surface for it is `/livespec-impl-plaintext:capture-impl-gaps`. This PC scopes itself to enumerating the existing `--project-root` / `--work-items-path` flags only.


## Why now

The flags are stable contract used by doctor cross-boundary handoffs. Documenting them in the spec ratifies the existing surface so future refactors don't silently drop them.


## Affected files

- `SPECIFICATION/contracts.md` — two CLI-surface edits as enumerated above.

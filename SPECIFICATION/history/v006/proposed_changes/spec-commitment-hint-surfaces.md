---
topic: spec-commitment-hint-surfaces
author: claude-opus-4-7
created_at: 2026-05-27T03:00:00Z
---

## Problem statement

The `spec_commitment_hint` pairing field landed in `livespec-impl-plaintext` via li-4szyct (PR #39, merged 2026-05-26) — it's the surface livespec's `unresolved-spec-commitment` doctor invariant queries to verify each spec-side `spec_commitments.impl_followups[].id_hint` declaration maps to a filed impl-side work-item. The impl carries the field on `WorkItem` (typed `str | None`, see `.claude-plugin/scripts/livespec_impl_plaintext/types.py:78`), validates it on the read path (`.claude-plugin/scripts/livespec_impl_plaintext/store.py:235-242`), wires it through `capture-work-item` via `--spec-commitment-hint <id_hint>` (SKILL.md Step 1), and exposes a filter on `list-work-items` via `--with-spec-commitment-hint <id_hint>` (`commands/list_work_items.py:61-62`).

The v005 spec at `SPECIFICATION/contracts.md` does NOT reflect any of this:

1. §"Work-items JSONL record schema" says "EXACTLY these keys (additional keys are forbidden — schema violations fire as doctor `fail` findings)" and enumerates 14 keys ending at `superseded_by`. `spec_commitment_hint` is absent. A strict reading of the current spec would have doctor reject every work-item the impl now writes.

2. §"list-work-items" enumerates the CLI surface `list-work-items [--filter <name>] [--with-gap-id=<id>] [--json]`. The `--with-spec-commitment-hint=<id_hint>` flag the impl supports (and that the upstream doctor invariant queries) is not enumerated.

3. §"capture-work-item" describes the freeform path as "the user supplies title, description, type, and priority" with no enumeration of optional input fields. The `--spec-commitment-hint` flag and its semantics (verbatim id_hint pass-through; null for freeform) are not documented.

This is impl→spec drift in the classic sense: the implementation has evolved beyond the ratified contract, in a load-bearing way (doctor depends on the surface).


## Proposal: add `spec_commitment_hint` to the work-items JSONL record schema

In `SPECIFICATION/contracts.md` §"Work-items JSONL record schema", append a new key entry after `superseded_by`:

> - `spec_commitment_hint` — string or `null`. OPTIONAL on the read path (records authored before this field's introduction read back as `null`); always written explicitly on append. When non-null, carries the verbatim `id_hint` from a spec-side `spec_commitments.impl_followups[]` declaration (per `livespec/SPECIFICATION/contracts.md` §"Implementation-plugin contract — the 10-skill surface" → "Work-item `spec_commitment_hint` field"). When the work-item was filed via the freeform path with no spec-side commitment to pair against, the field is `null`. The field is the surface livespec's `unresolved-spec-commitment` doctor invariant queries via `list-work-items --json` to verify every declared spec→impl commitment maps to a filed work-item.

Also relax the "EXACTLY these keys" preamble to clarify the read-path optionality: the existing 14 required keys remain required-on-write; `spec_commitment_hint` is required-on-write but optional-on-read (legacy records lacking the field read back as `null` without firing a schema violation).


## Proposal: enumerate `--with-spec-commitment-hint` on list-work-items

In `SPECIFICATION/contracts.md` §"list-work-items", update the CLI surface line to:

> CLI surface: `list-work-items [--filter <name>] [--with-gap-id=<id>] [--with-spec-commitment-hint=<id_hint>] [--json]`.

And add a new bullet alongside the existing `--with-gap-id=<id>` bullet:

> `--with-spec-commitment-hint=<id_hint>` — exact-match on the `spec_commitment_hint` field. Combinable with `--filter` and with `--with-gap-id`.


## Proposal: enumerate `--spec-commitment-hint` on capture-work-item

In `SPECIFICATION/contracts.md` §"capture-work-item", append a paragraph after the existing prose:

> The skill accepts an optional `--spec-commitment-hint <id_hint>` flag. When supplied, the resulting work-item's `spec_commitment_hint` field MUST equal the verbatim `id_hint`; when omitted, the field defaults to `null` (the freeform case). This is the surface livespec's `unresolved-spec-commitment` doctor invariant queries via `list-work-items --json` to verify each declared spec→impl commitment maps to a filed work-item (per `livespec/SPECIFICATION/contracts.md` §"Implementation-plugin contract — the 10-skill surface" → "Work-item `spec_commitment_hint` field").


## Why now

The field landed on master and the doctor invariant on the upstream livespec side already queries this surface. The spec's continued silence creates two failure modes:

- Doctor's `work-items-jsonl-schema-strict` static check (if/when re-derived from the v005 spec) would FAIL on every work-item the impl now writes (the unknown key `spec_commitment_hint`).
- A future contributor reading only the spec and not the impl source would author a new tool / migration / sibling plugin that drops the field, silently breaking the cross-plugin commitment-pairing surface.

Accepting this PC reconciles the contract with the landed behavior. No impl work is needed — this is a pure spec-side ratification of behavior that already exists.


## Affected files

- `SPECIFICATION/contracts.md` — three edits as enumerated above.

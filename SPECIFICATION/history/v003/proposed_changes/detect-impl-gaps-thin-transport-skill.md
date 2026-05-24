---
topic: detect-impl-gaps-thin-transport-skill
author: claude-opus-4-7
created_at: 2026-05-24T08:30:00Z
---

## Proposal: declare-detect-impl-gaps-thin-transport-surface

### Target specification files

- SPECIFICATION/contracts.md

### Summary

Concretize the new `detect-impl-gaps` thin-transport skill in `livespec-impl-plaintext`'s sub-spec to mirror the upstream contract addition (paired propose-change in `livespec/SPECIFICATION/proposed_changes/detect-impl-gaps-thin-transport-skill.md`). Update the skill enumeration to a 10-skill surface (4 thin-transport), rewrite `capture-impl-gaps` to consume the new sibling for its detection step, rewrite `implement`'s gap-tied closure verification to invoke `detect-impl-gaps` directly, and update the Spec Reader consumer listing + the cross-boundary handoffs listing.

### Motivation

This sub-spec MUST track the upstream contract per the rule in this file's preamble: "Every contract here concretizes a slot in `livespec/SPECIFICATION/contracts.md`; nothing here overrides upstream." The upstream propose-change adds `detect-impl-gaps` as the canonical machine surface for spec → impl gap detection; this plugin's sub-spec must declare its own realization of that surface (the `bin/<skill>.py` shape, the `--json` output schema, the consumers within the heavyweight `capture-impl-gaps` and `implement` skills). The detection logic itself stays in one Python module that both `detect-impl-gaps` (via the thin-transport wrapper) and `capture-impl-gaps` (via subprocess to the thin-transport skill) consume; doctor consumes it identically. This eliminates the "non-mutating dry-run mode" framing that previously muddled `capture-impl-gaps`'s contract.

### Proposed Changes

#### `SPECIFICATION/contracts.md` §"The nine-skill surface" section header + intro

Rename and update the intro:

```diff
-## The nine-skill surface
-
-Every entry below is REQUIRED. The descriptions concretize each
-skill's behavior on the JSONL substrate; cross-boundary semantics
-(handoffs, JSON output schemas, user-consent rules) are defined by
-`livespec/SPECIFICATION/contracts.md` §"Implementation-plugin
-contract — the 9-skill surface" and apply uniformly.
+## The ten-skill surface
+
+Every entry below is REQUIRED. The descriptions concretize each
+skill's behavior on the JSONL substrate; cross-boundary semantics
+(handoffs, JSON output schemas, user-consent rules) are defined by
+`livespec/SPECIFICATION/contracts.md` §"Implementation-plugin
+contract — the 10-skill surface" and apply uniformly.
```

#### `SPECIFICATION/contracts.md` §"capture-impl-gaps" sub-section

Rewrite the heavyweight skill description to consume the new thin-transport sibling for detection:

```diff
-#### `capture-impl-gaps`
-
-Detect spec → impl gaps mechanically via the Spec Reader. The gap
-ruleset is enumerated by reading every rule from the live
-Specification (per the Spec Reader's "read current spec"
-capability); the detection logic is deterministic — no LLM in the
-detection path. Detected gaps are presented to the user one at a
-time; on consent, a new work-item JSONL record is appended with
-`origin: gap-tied` and `gap_id: <stable-id>`. Detection state is
-in-memory and discarded at skill exit — no persistent intermediate
-artifact. Re-running the skill is idempotent: an already-tracked
-gap-id is detected as "already filed" and not re-prompted unless
-the user explicitly asks for a refresh.
+#### `capture-impl-gaps`
+
+Detect spec → impl gaps by invoking the sibling `detect-impl-gaps
+--json` thin-transport skill (no in-skill duplication of the
+detection logic; both this skill and doctor consume the same
+canonical surface). The returned gap-ids are presented to the
+user one at a time; on consent, a new work-item JSONL record is
+appended with `origin: gap-tied` and `gap_id: <stable-id>`.
+Detection state is in-memory and discarded at skill exit — no
+persistent intermediate artifact. Re-running the skill is
+idempotent: an already-tracked gap-id is detected as "already
+filed" and not re-prompted unless the user explicitly asks for
+a refresh.
```

#### `SPECIFICATION/contracts.md` §"implement" sub-section — closure-verification step

Update the gap-tied closure verification to invoke `detect-impl-gaps` directly:

```diff
-Closure branches on `origin × disposition`:
-
-- **gap-tied fix** — re-run `capture-impl-gaps` in dry-run mode
-  (no JSONL writes); confirm the `gap_id` is NO LONGER detected;
-  append a closing record with `status: closed`, `resolution: fix`,
-  and audit fields (`verification_timestamp`, `commits`,
-  `files_changed`).
+Closure branches on `origin × disposition`:
+
+- **gap-tied fix** — invoke `detect-impl-gaps --json`; confirm
+  the `gap_id` is NO LONGER in the returned gap-id set; append
+  a closing record with `status: closed`, `resolution: fix`,
+  and audit fields (`verification_timestamp`, `commits`,
+  `files_changed`).
```

#### `SPECIFICATION/contracts.md` §"Thin-transport skills (3)" section header

Rename and append a new sub-section for `detect-impl-gaps` after the `next` sub-section (i.e., as the fourth thin-transport skill):

```diff
-### Thin-transport skills (3)
+### Thin-transport skills (4)
```

#### `SPECIFICATION/contracts.md` — new `detect-impl-gaps` sub-section

Add the following sub-section immediately after the `next` sub-section (and before §"Work-items JSONL record schema"):

```markdown
#### `detect-impl-gaps`

CLI surface: `detect-impl-gaps [--spec-target <path>]
[--project-root <path>] [--json]`. No `--filter` flag — the
skill emits the complete current gap-id set.

The skill reads the live Specification via the Spec Reader,
enumerates every MUST/SHOULD rule per the gap-rule enumeration
contract (per upstream §"Spec Reader required-capability
surface" capability 1), and computes a stable `gap_id` per
detected rule. Gap-id derivation is a pure function of rule
text + canonical heading path; the same rule text always yields
the same gap-id across runs.

`--json` output: a top-level JSON object with one key, `gap_ids`,
whose value is an array of strings:

```json
{
  "gap_ids": ["gap-<stable-id-1>", "gap-<stable-id-2>", "..."]
}
```

Default human output: one line per gap-id, prefixed with the
spec-file path + heading the rule was sourced from.

The skill is the canonical gap-detection surface for the plugin.
Consumers:

- `livespec` doctor's `gap-tracking-one-to-one` and
  `no-stale-gap-tied` invariants subprocess this skill via the
  `<impl-plugin>:detect-impl-gaps --json` cross-boundary handoff
  (per upstream §"Cross-boundary handoffs" entry 5).
- The heavyweight sibling `capture-impl-gaps` invokes this
  skill as its detection step before walking the user through
  per-gap consent.
- The heavyweight `implement` skill invokes this skill at gap-
  tied work-item closure to confirm the `gap_id` is no longer
  detected before appending the closing record.

The skill MUST NOT mutate any impl-side store; it MUST NOT
write to the work-items JSONL; it MUST NOT prompt the user. It
is a pure read-and-emit pass-through over the Spec Reader's
output and the gap-rule enumeration.
```

#### `SPECIFICATION/contracts.md` §"Spec Reader internal API" — consumer listing

Replace `capture-impl-gaps` with `detect-impl-gaps` in the consumer list (the heavyweight skill no longer reads the Spec Reader directly; the thin-transport sibling does):

```diff
-The Spec Reader is consumed by `capture-impl-gaps`,
-`capture-spec-drift`, `implement`, and `process-memos`. It is
-NOT a slash command and NOT exposed through the
-`/livespec-impl-plaintext:` namespace.
+The Spec Reader is consumed by `detect-impl-gaps`,
+`capture-spec-drift`, `implement`, and `process-memos`. It is
+NOT a slash command and NOT exposed through the
+`/livespec-impl-plaintext:` namespace.
```

#### `SPECIFICATION/contracts.md` §"Cross-boundary handoffs"

Insert a new entry for the gap-detection handoff (slot 4 in upstream's listing) and re-number the existing work-items handoff to slot 5 to mirror upstream:

```diff
 1. `/livespec-impl-plaintext:capture-spec-drift` →
    `/livespec:propose-change` (drift findings).
 2. `/livespec-impl-plaintext:process-memos` →
    `/livespec:propose-change` (spec-bound memo disposition).
 3. `/livespec:doctor` →
    `/livespec-impl-plaintext:list-memos --filter=untriaged --json`
    (memo-hygiene invariant).
-4. `/livespec:doctor` →
-   `/livespec-impl-plaintext:list-work-items --json` (work-item
-   structural invariants).
+4. `/livespec:doctor` →
+   `/livespec-impl-plaintext:list-work-items --json` (work-item
+   structural invariants).
+5. `/livespec:doctor` →
+   `/livespec-impl-plaintext:detect-impl-gaps --json` (gap-
+   detection invariants `gap-tracking-one-to-one` and
+   `no-stale-gap-tied`).
```

# contracts.md — livespec-impl-plaintext

Wire-level surfaces this plugin exposes (slash commands and internal
APIs), plus the on-disk JSONL schemas the skills read and write.
Every contract here concretizes a slot in
`livespec/SPECIFICATION/contracts.md`; nothing here overrides
upstream.

## Plugin namespace

The plugin's slash commands live under `/livespec-impl-plaintext:`.
That namespace is fixed by `.claude-plugin/plugin.json` and may not
be changed without a coordinated rename across consumers (because
doctor's cross-boundary invariants in `livespec` invoke skills
through this namespace prefix per
`livespec/SPECIFICATION/contracts.md` §"Cross-plugin
invocation"). Renaming is a major-version-bump operation.

## The ten-skill surface

Every entry below is REQUIRED. The descriptions concretize each
skill's behavior on the JSONL substrate; cross-boundary semantics
(handoffs, JSON output schemas, user-consent rules) are defined by
`livespec/SPECIFICATION/contracts.md` §"Implementation-plugin
contract — the 10-skill surface" and apply uniformly.

### Heavyweight authored skills (6)

#### `capture-impl-gaps`

Detect spec → impl gaps by invoking the sibling
`/livespec-impl-plaintext:detect-impl-gaps --json` thin-transport
skill (no in-skill duplication of the detection logic; both this
skill and doctor consume the same canonical surface). The returned
gap-ids are presented to the user one at a time; on consent, a new
work-item JSONL record is appended with `origin: gap-tied` and
`gap_id: <stable-id>`. Detection state is in-memory and discarded
at skill exit — no persistent intermediate artifact. Re-running the
skill is idempotent: an already-tracked gap-id is detected as
"already filed" and not re-prompted unless the user explicitly
asks for a refresh.

#### `capture-spec-drift`

Detect impl → spec drift heuristically (LLM-driven). For each
finding, present it to the user with a recommended action; on
consent, hand off to `/livespec:propose-change` via the
cross-boundary handoff (per
`livespec/SPECIFICATION/contracts.md` §"Cross-boundary
handoffs" entry 1). The handoff produces a proposed-change file
under the consumer's spec-side `<spec-root>/proposed_changes/`;
this plugin never writes to spec-side state directly.

#### `capture-work-item`

Freeform direct filing of a work-item. The user supplies title,
description, type, and priority; the skill appends a new JSONL
record with `origin: freeform`, `gap_id: null`, and the supplied
fields. No gap detection runs; no closure-verification rules
attach. Closure is via the freeform path in `implement`.

#### `implement`

Drive Red → Green for a single work-item. The user picks the
work-item (or the skill defers to `next`'s recommendation). The
skill walks the user through:

1. Authoring a failing test (Red).
2. Implementing the change until the test passes (Green).
3. Closing the work-item.

Closure branches on `origin × disposition`:

- **gap-tied fix** — invoke `detect-impl-gaps --json`; confirm
  the `gap_id` is NO LONGER in the returned gap-id set; append
  a closing record with `status: closed`, `resolution: fix`,
  and audit fields (`verification_timestamp`, `commits`,
  `files_changed`).
- **freeform fix** — append a closing record with
  `status: closed`, `resolution: fix`, and a user-supplied
  `--reason`.
- **non-fix administrative closure** — append a closing record with
  `status: closed` and `resolution: <wontfix | duplicate |
  spec-revised | no-longer-applicable | resolved-out-of-band>`,
  carrying a user-supplied `--reason`.

#### `capture-memo`

Low-friction free-text deposit of an observation the user is not
yet ready to classify. The user supplies a one-paragraph text;
the skill appends a new memo JSONL record with `state: untriaged`
and `captured_at: <ISO-8601 UTC>`. No dialogue branches; no
classification.

#### `process-memos`

Per-memo handholding dialogue. Iterates over `state: untriaged`
memos (or a `--filter`ed subset) and for each:

1. Shows the memo content and timestamp.
2. Asks the user to pick a disposition (`spec-bound`,
   `impl-bound`, `persistent-knowledge`, `discard`).
3. Performs the disposition action:
   - `spec-bound` — hand off to `/livespec:propose-change`
     (cross-boundary handoff entry 2) with the memo content as
     the proposed-change source material; append a closing memo
     record with `state: dispositioned`,
     `disposition: spec-bound`.
   - `impl-bound` — invoke `capture-work-item` internally to file
     a freeform work-item carrying the memo content; append a
     closing memo record with `state: dispositioned`,
     `disposition: impl-bound`, plus the resulting `work_item_id`
     for cross-reference.
   - `persistent-knowledge` — write the memo content into a
     newly-authored or existing `.ai/<topic>.md` file (the user
     picks the topic name in dialogue); add a reference to that
     file from `CLAUDE.md` and/or `AGENTS.md` if not already
     present; append a closing memo record with
     `state: dispositioned`, `disposition: persistent-knowledge`,
     plus the resulting `knowledge_file` path for cross-reference.
   - `discard` — append a closing memo record with
     `state: dispositioned`, `disposition: discard`. The memo
     content is preserved on disk (audit-trail discipline); only
     the state marker changes.

### Thin-transport skills (4)

Each thin-transport skill is a short SKILL.md pass-through over a
Python `bin/` implementation (the wrapper-shape contract codified
in `livespec/SPECIFICATION/contracts.md` §"Wrapper CLI
surface"). SKILL.md MUST NOT accrete logic — every behavior lives
under `.claude-plugin/scripts/bin/<skill>.py`.

#### `list-memos`

CLI surface: `list-memos [--filter <name>] [--json]`.

`--filter` flags supported:

- `--filter=untriaged` — show only memos whose latest state
  marker is `untriaged`.
- `--filter=dispositioned` — show only memos whose latest state
  marker is `dispositioned`.
- `--filter=all` — show every memo (default if no filter).
- Additional filters MAY be added in future revisions.

`--json` output: an array of memo materialized views (latest
record per `id`); each view is the full JSONL record contents.
Default human output: one-line summary per memo.

#### `list-work-items`

CLI surface: `list-work-items [--filter <name>]
[--with-gap-id=<id>] [--json]`.

`--filter` flags:

- `--filter=gap-tied` — `origin: gap-tied` only.
- `--filter=freeform` — `origin: freeform` only.
- `--filter=blocked` — `status: blocked` only.
- `--filter=ready` — `status: open` AND no unresolved
  `depends_on` records.
- `--filter=closed` — `status: closed` only.
- `--filter=all` — default.

`--with-gap-id=<id>` — exact-match on the `gap_id` field.

`--json` output: an array of work-item materialized views.

#### `next`

CLI surface: `next [--json]`. No `--filter` flag — the skill's
job is to RANK rather than to filter.

Ranking is a pure function of work-items JSONL state (no LLM).
The algorithm:

1. Identify ready items: `status: open`, `depends_on` either
   empty or all-closed.
2. Score by priority (lower number = more urgent) then by
   `gap-tied` ahead of `freeform` (gap-tied items have explicit
   spec backing) then by oldest `captured_at`.
3. The top-ranked item is the recommendation; ties are broken
   deterministically by `id` lexicographic order.

Output schema (per
`livespec/SPECIFICATION/contracts.md` §"Implementation-plugin
contract — the 9-skill surface" → next):

```json
{
  "action": "implement",
  "work_item_ref": "<id-of-top-ranked-item>",
  "urgency": "high" | "medium" | "low",
  "reason": "<one-line human narration>"
}
```

When no items are ready, output is:

```json
{
  "action": "none",
  "work_item_ref": null,
  "urgency": "low",
  "reason": "no work-items are ready (queue empty or all blocked)"
}
```

`urgency` derivation: P0 → high; P1, P2 → medium; P3, P4 → low.

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

`--json` output: a top-level JSON object with one key,
`gap_ids`, whose value is an array of strings:

```json
{
  "gap_ids": ["gap-<stable-id-1>", "gap-<stable-id-2>", "..."]
}
```

Default human output: one line per gap-id, prefixed with the
spec-file path + heading the rule was sourced from.

The skill is the canonical gap-detection surface for the
plugin. Consumers:

- `livespec` doctor's `gap-tracking-one-to-one` and
  `no-stale-gap-tied` invariants subprocess this skill via the
  `<impl-plugin>:detect-impl-gaps --json` cross-boundary
  handoff (per upstream §"Cross-boundary handoffs" entry 5).
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

## Work-items JSONL record schema

Each line in the work-items file is a single JSON object with
EXACTLY these keys (additional keys are forbidden — schema
violations fire as doctor `fail` findings):

- `id` — string, stable lifetime identifier. Format:
  `li-<6-char-base32-suffix>` mirroring the upstream `bd`
  convention so cross-references stay legible across the
  beads-era and plaintext-era histories.
- `type` — string, one of: `bug`, `feature`, `task`, `chore`,
  `epic`. Matches upstream Conventional Commits scopes.
- `status` — string, one of: `open`, `in_progress`, `blocked`,
  `closed`, `deferred`.
- `title` — string, one-line summary.
- `description` — string, multi-line free-form. Markdown
  permitted but optional.
- `origin` — string, one of: `gap-tied`, `freeform`.
- `gap_id` — string or `null`. REQUIRED non-null when
  `origin == gap-tied`; MUST be `null` when
  `origin == freeform`.
- `priority` — integer 0–4 (0 = critical, 4 = backlog), matching
  upstream `bd` priority semantics.
- `assignee` — string or `null`. Optional ownership marker.
- `depends_on` — array of `id` strings. May be empty.
- `captured_at` — ISO-8601 UTC timestamp of the record's
  authorship.
- `resolution` — string or `null`. REQUIRED non-null when
  `status == closed`; one of: `fix`, `wontfix`, `duplicate`,
  `spec-revised`, `no-longer-applicable`, `resolved-out-of-band`.
- `reason` — string or `null`. Closure narration; REQUIRED
  non-null for closure records.
- `audit` — object or `null`. REQUIRED non-null when
  `status == closed AND resolution == fix`; carries
  `verification_timestamp`, `commits` (array of SHAs),
  `files_changed` (array of relative paths).
- `superseded_by` — `id` or `null`. Used for record amendments;
  not for `resolution: duplicate` (use `reason` for that).

### Materialized view

The latest record per `id` (by file order) is the materialized
view. A record with `status: closed` is terminal — appending
further records carrying the same `id` is ALLOWED but DISCOURAGED
(the right pattern is to file a new work-item with a fresh `id`
that references the closed one). Doctor's `no-orphan-blocker`
invariant in `livespec` reads materialized views; readers
of this plugin MUST do the same.

## Memos JSONL record schema

- `id` — string, same format as work-items but prefixed differently:
  `mm-<6-char-base32-suffix>`.
- `text` — string, the memo body. Markdown permitted.
- `state` — string, one of: `untriaged`, `dispositioned`.
- `disposition` — string or `null`. REQUIRED non-null when
  `state == dispositioned`; one of: `spec-bound`, `impl-bound`,
  `persistent-knowledge`, `discard`.
- `captured_at` — ISO-8601 UTC timestamp.
- `work_item_id` — string or `null`. Set when
  `disposition == impl-bound` to record the resulting work-item
  cross-reference.
- `knowledge_file` — string or `null`. Set when
  `disposition == persistent-knowledge` to record the
  `.ai/<topic>.md` path.
- `propose_change_topic` — string or `null`. Set when
  `disposition == spec-bound` to record the resulting
  proposed-change topic.

## Spec Reader internal API

Per `livespec/SPECIFICATION/contracts.md` §"Spec Reader
required-capability surface", every `livespec-impl-*` plugin MUST
expose four capabilities through an internal adapter. The shape
is implementation-dependent; this plugin's shape is a Python
module with these public functions:

```python
def read_current_specification(spec_root: Path) -> SpecSnapshot: ...
def read_specification_history(spec_root: Path, version: int) -> SpecSnapshot: ...
def current_specification_version(spec_root: Path) -> int: ...
def diff_specification_versions(
    spec_root: Path, version_a: int, version_b: int,
) -> SpecDiff: ...
```

`SpecSnapshot` and `SpecDiff` are dataclasses defined under
`.claude-plugin/scripts/<adapter>/spec_reader.py`. The initial
implementation is a thin file pass-through (no caching, no
indexing); cached or section-indexed implementations remain
valid future refinements without contract change.

The Spec Reader MUST:

- Consult the active template manifest's `spec_files` list rather
  than hardcoding the well-known file set (per upstream §"Spec
  Reader required-capability surface" capability 1).
- Surface the `version-directories-complete` pruned-marker
  exemption when reading history (capability 2).
- Return `int` for the current version (capability 3).
- Compute diffs as a structured change list (capability 4); the
  initial implementation returns a `SpecDiff` carrying per-file
  added/removed-line counts plus a unified-diff body.

The Spec Reader MUST exclude content from
`<spec-root>/proposed_changes/`. Only ratified canonical content
is exposed; pending proposals are not yet intent.

The Spec Reader is consumed by `detect-impl-gaps`,
`capture-spec-drift`, `implement`, and `process-memos`. It is
NOT a slash command and NOT exposed through the
`/livespec-impl-plaintext:` namespace.

## Persistent Agent Knowledge realization

Per `livespec/SPECIFICATION/contracts.md` §"Persistent Agent
Knowledge realization", the per-plugin form is
implementation-dependent. `livespec-impl-plaintext` realizes the
store as:

- A directory `.ai/` at the consumer project's root containing
  one markdown file per topic (`.ai/<topic-slug>.md`).
- Each topic file is referenced from the consumer project's
  `CLAUDE.md` and/or `AGENTS.md` via a one-line bullet pointing
  at the file path. Reference inclusion is REQUIRED — orphaned
  topic files MUST NOT exist.
- `process-memos`'s `persistent-knowledge` disposition writes the
  memo content to the chosen topic file (creating it if absent)
  and updates `CLAUDE.md` / `AGENTS.md` references if needed.
- Topic files MAY grow over time; pruning is the user's call
  (`process-memos` does NOT auto-trim). Doctor's memo-hygiene
  invariant in `livespec` does NOT apply to
  dispositioned-into-store content (per upstream §"Persistent
  Agent Knowledge realization" bullet 3).

The harness loads `CLAUDE.md` / `AGENTS.md` automatically into
agent context per Claude Code / Codex / other harness
conventions; the linked `.ai/<topic>.md` files are loaded
on-demand by the agent following bullet references when relevant.
This realization mirrors `livespec`'s own v058-era
`.ai/<topic>.md` convention (now graduated to a first-class
upstream contract slot).

## `compat` block

Per `livespec/SPECIFICATION/contracts.md` §"Cross-repo
coordination — pin-and-bump", every consuming project's
`.livespec.jsonc` declares a `compat` block for each active
impl-plugin. For `livespec-impl-plaintext`:

```jsonc
{
  "implementation": { "plugin": "livespec-impl-plaintext" },
  "livespec-impl-plaintext": {
    "format": "jsonl",
    "compat": {
      "livespec": ">=2.0.0,<3.0.0",
      "pinned": "v2.3.0"
    },
    "work_items_path": "work-items.jsonl",
    "memos_path": "memos.jsonl"
  }
}
```

`format: jsonl` is fixed for this plugin (the substrate marker).
`livespec` is a semver range matching every `livespec`
release this plugin's pinned version is known to be compatible
with. `pinned` is the SPECIFIC `livespec` release tag the
consumer currently runs against. Both are REQUIRED per upstream.

`work_items_path` and `memos_path` are plugin-specific
configuration keys; they default to the values shown above and
MAY be overridden per consumer.

The configuration block is read by every skill at invocation
time. A missing or malformed block MUST fire a `fail` finding
from doctor's `contract-version-compatibility` invariant
(upstream §"Cross-boundary doctor invariants").

## Cross-boundary handoffs

Per `livespec/SPECIFICATION/contracts.md` §"Cross-boundary
handoffs", this plugin participates in these red-edge handoffs:

1. `/livespec-impl-plaintext:capture-spec-drift` →
   `/livespec:propose-change` (drift findings).
2. `/livespec-impl-plaintext:process-memos` →
   `/livespec:propose-change` (spec-bound memo disposition).
3. `/livespec:doctor` →
   `/livespec-impl-plaintext:list-memos --filter=untriaged --json`
   (memo-hygiene invariant).
4. `/livespec:doctor` →
   `/livespec-impl-plaintext:list-work-items --json` (work-item
   structural invariants).
5. `/livespec:doctor` →
   `/livespec-impl-plaintext:detect-impl-gaps --json` (gap-
   detection invariants `gap-tracking-one-to-one` and
   `no-stale-gap-tied`).

The handoff mechanism is namespace invocation (per
`livespec/SPECIFICATION/contracts.md` §"Cross-plugin
invocation") — never direct CLI shelling-out to wrapper paths.

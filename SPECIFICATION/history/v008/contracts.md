# contracts.md — livespec-impl-git-jsonl

Wire-level surfaces this plugin exposes (slash commands and internal
APIs), plus the on-disk JSONL schemas the skills read and write.
Every contract here concretizes a slot in
`livespec/SPECIFICATION/contracts.md`; nothing here overrides
upstream.

## Plugin namespace

The plugin's slash commands live under `/livespec-impl-git-jsonl:`.
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
`/livespec-impl-git-jsonl:detect-impl-gaps --json` thin-transport
skill (no in-skill duplication of the detection logic; both this
skill and doctor consume the same canonical surface). The returned
gap-ids are presented to the user one at a time; on consent, a new
work-item JSONL record is appended with `origin: gap-tied` and
`gap_id: <stable-id>`. Detection state is in-memory and discarded
at skill exit — no persistent intermediate artifact. Re-running the
skill is idempotent: an already-tracked gap-id is detected as
"already filed" and not re-prompted unless the user explicitly
asks for a refresh.

**`--since-version <vN>`** (optional). When set, passed through
verbatim to both `detect-impl-gaps` invocations (the `--json`
authoritative-set call and the rich-display call). Validation is
delegated to the underlying skill — if the value is invalid,
`detect-impl-gaps` exits `2` or `3` and `capture-impl-gaps`
surfaces the error and aborts.

The flag is the surface that callers (notably `/livespec:revise`'s
post-step per the coordinating epic
`livespec#coordinating-epic-stale-revise-enforcement`) use to scope
per-revise gap detection. Direct user invocations MAY use it as
well for any "show me gaps for changes since this version"
workflow.

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

The skill accepts an optional `--spec-commitment-hint <id_hint>`
flag. When supplied, the resulting work-item's
`spec_commitment_hint` field MUST equal the verbatim `id_hint`;
when omitted, the field defaults to `null` (the freeform case).
This is the surface livespec's `unresolved-spec-commitment` doctor
invariant queries via `list-work-items --json` to verify each
declared spec→impl commitment maps to a filed work-item (per
`livespec/SPECIFICATION/contracts.md` §"Implementation-plugin
contract — the 10-skill surface" → "Work-item
`spec_commitment_hint` field").

#### `implement`

Drive Red → Green for a single work-item. The user picks the
work-item (or the skill defers to `next`'s recommendation). The
skill walks the user through:

1. Authoring a failing test (Red).
2. Implementing the change until the test passes (Green).
3. Closing the work-item.

Closure branches on `origin × disposition`:

- **gap-tied completion** — invoke `detect-impl-gaps --json`; confirm
  the `gap_id` is NO LONGER in the returned gap-id set; append
  a closing record with `status: closed`, `resolution: completed`,
  and audit fields (`verification_timestamp`, `commits`,
  `files_changed`, `merge_sha`, optional `pr_number`).
- **freeform completion** — append a closing record with
  `status: closed`, `resolution: completed`, and a user-supplied
  `--reason`.
- **non-completion administrative closure** — append a closing record with
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

CLI surface: `list-work-items [--filter <name>] [--with-gap-id=<id>] [--with-spec-commitment-hint=<id_hint>] [--json] [--work-items-path <path>] [--project-root <path>]`.

`--filter` flags:

- `--filter=gap-tied` — `origin: gap-tied` only.
- `--filter=freeform` — `origin: freeform` only.
- `--filter=blocked` — `status: blocked` only.
- `--filter=ready` — `status: open` AND no unresolved
  `depends_on` records.
- `--filter=closed` — `status: closed` only.
- `--filter=all` — default.

`--with-gap-id=<id>` — exact-match on the `gap_id` field.

`--with-spec-commitment-hint=<id_hint>` — exact-match on the
`spec_commitment_hint` field. Combinable with `--filter` and
with `--with-gap-id`.

`--project-root <path>` — override the cross-repo manifest and
store-path resolution base. Default: `Path.cwd()`. Used by
doctor's cross-boundary handoffs to invoke this skill from
outside the consumer project root.

`--work-items-path <path>` — override the default
`work-items.jsonl` location (the value resolved from the
consumer's `.livespec.jsonc` `work_items_path` config). Used by
tests and by doctor invocations that want to scope to a
non-default store path.

`--json` output: an array of work-item materialized views.

#### `next`

Cross-reference: cross-side composition of impl-side `next` with
spec-side `/livespec:next` is a Layer 3 (project-local
orchestration) concern per `livespec/SPECIFICATION/spec.md`
§"Three-layer orchestration architecture" → "Cross-side
composition belongs at Layer 3". This Layer 2 surface ranks
impl-side state only; it MUST NOT bake a cross-side weighting in.

CLI surface: `next [--limit <count>] [--offset <count>] [--json] [--work-items-path <path>] [--project-root <path>]`.
No `--filter` flag — the skill's job is to RANK rather than to
filter.

`--limit <count>` — positive integer, default `5`. Maximum number
of candidates returned in the `candidates` array. Non-positive
values MUST cause the wrapper to exit `2` with a `UsageError`.

`--offset <count>` — non-negative integer, default `0`. Number of
ranked candidates to skip from the front of the ranked list
before returning. Negative values MUST cause the wrapper to exit
`2` with a `UsageError`.

`--project-root <path>` — override the cross-repo manifest and
store-path resolution base. Default: `Path.cwd()`. Used by
doctor's cross-boundary handoffs to invoke this skill from
outside the consumer project root.

`--work-items-path <path>` — override the default
`work-items.jsonl` location (the value resolved from the
consumer's `.livespec.jsonc` `work_items_path` config). Used by
tests and by doctor invocations that want to scope to a
non-default store path.

Ranking is a pure function of work-items JSONL state (no LLM).
The algorithm:

1. Identify ready items: `status: open`, `depends_on` either
   empty or all-closed.
2. Score by priority (lower number = more urgent) then by
   `gap-tied` ahead of `freeform` (gap-tied items have explicit
   spec backing) then by oldest `captured_at`.
3. Ties are broken deterministically by `id` lexicographic
   order.
4. Apply `--offset` and `--limit` to produce the returned slice.

Output schema (per `livespec/SPECIFICATION/contracts.md`
§"Implementation-plugin contract — the 10-skill surface" →
`next` and the upstream
§"`/livespec:next` spec-side thin-transport skill" → §"Output
schema"): the output is a JSON object with two top-level keys,
`candidates[]` and `pagination`:

```jsonc
{
  "candidates": [
    {
      "action": "implement",
      "reason": "<one-line human narration>",
      "urgency": "high",
      "work_item_ref": "<id-of-ranked-item>"
    }
  ],
  "pagination": {
    "offset": 0,
    "limit": 5,
    "total": 12,
    "has_more": true
  }
}
```

Field semantics:

- `candidates[]` — array of candidate objects. `action` MUST be
  one of `"implement"` | `"none"`. The work-items-only scoping
  is principled: memos are a different store, and the canonical
  actionable-memo probe is `list-memos --filter=untriaged`;
  gap-detection and drift-detection are driver-side concerns
  the Layer 3 driver invokes outside of `next`'s ranking. Each
  candidate MUST carry `action`, `reason` (non-empty
  human-readable narration), `urgency` (one of `high`,
  `medium`, `low`), and `work_item_ref` (the `id` of the ranked
  work-item, or `null` for `action: "none"`). Each candidate
  MAY include additional impl-git-jsonl-specific fields the
  wrapper emits (e.g., `priority`, `origin`); the cross-plugin
  contract MUST NOT prescribe `additionalProperties` discipline
  per upstream.
- `pagination.offset` — echoed from `--offset`.
- `pagination.limit` — echoed from `--limit`.
- `pagination.total` — total count of ripe candidates BEFORE
  `offset` and `limit` are applied.
- `pagination.has_more` — `true` iff
  `offset + len(candidates) < total`.

`urgency` derivation per candidate: P0 → high; P1, P2 → medium;
P3, P4 → low.

When no items are ready, the wrapper MUST emit `candidates: []`
with a `pagination` echoing the inputs and `has_more: false`.
An empty `candidates` array IS the no-work signal; it does NOT
degrade to any legacy single-object shape. The Layer 2 surface
MUST NOT bake a hygiene fallback into the emission: emission of
the empty array is purely advisory, and any "what to do when
both `/livespec:next` and `/livespec-impl-git-jsonl:next` are
quiet" handoff is a Layer 3 (project-local orchestration)
concern (per `scenarios.md` Scenario 6's empty-queue handoff
sub-step).

When `offset >= total`, the wrapper MUST emit `candidates: []`
and `has_more: false`. The wrapper MUST always emit a valid
(possibly empty) `candidates` array.

##### Layer 3 discoverability nudge — not applicable under v089 recast

Under the v089 upstream recast
(`livespec/SPECIFICATION/spec.md` §"Three-layer
orchestration architecture" → "Layer 3 — Cross-repo
orchestration (livespec-resident)"), the Layer 3
discoverability nudge applies only to `/livespec:next`;
impl-plugin `next` skills do NOT carry the parallel-and-
symmetric nudge contract because impl-plugin repos do NOT
carry their own Layer 3 driver. The wrapper at
`.claude-plugin/scripts/bin/next.py` MUST remain a pure
thin-transport pass-through per the upstream §"Thin-transport
skill doctrine" and this plugin's §"Thin-transport skills (4)"
preamble.

#### `detect-impl-gaps`

CLI surface: `detect-impl-gaps [--spec-target <path>]
[--project-root <path>] [--since-version <vN>] [--json]`. No
`--filter` flag — the skill emits the complete current gap-id
set.

The skill reads the live Specification via the Spec Reader,
enumerates every MUST/SHOULD rule per the gap-rule enumeration
contract (per upstream §"Spec Reader required-capability
surface" capability 1), and computes a stable `gap_id` per
detected rule. Gap-id derivation is a pure function of rule
text + canonical heading path; the same rule text always yields
the same gap-id across runs.

**`--since-version <vN>`** (optional, default `null`). When set
to a historical version integer that exists under
`<spec-root>/history/v<NNN>/`, the skill restricts its scan to
files whose content differs between `<vN>` and the live spec
(i.e., the file appears in `SpecDiff(version_a=<vN>,
version_b=<live>).per_file`). For each such file, only MUST /
SHOULD clauses present in the live version are considered
(clauses removed by the diff are not gaps — they were spec
content that no longer exists).

Validation:

- The value MUST be a positive integer. Non-integer / negative
  input exits `2` with a usage error.
- The version directory `<spec-root>/history/v<padded-N>/` MUST
  exist. Missing version exits `3` with `PreconditionError`
  naming the expected path.

When omitted, the behavior is unchanged — scan every file in
the live spec.

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

Each line in the work-items file is a single JSON object. The
sixteen keys enumerated below are the canonical schema. The first
fourteen (`id` through `superseded_by`) are required-on-write AND
required-on-read; the fifteenth (`spec_commitment_hint`) and the
sixteenth (`supersedes`) are required-on-write but optional-on-read
(legacy records authored before each field's introduction read back
as `null` without firing a schema violation). Additional keys beyond
this sixteen are forbidden — schema violations fire as doctor `fail`
findings.

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
- `depends_on` — array of `id` strings. MAY be empty.
- `captured_at` — ISO-8601 UTC timestamp of the record's
  authorship.
- `resolution` — string or `null`. REQUIRED non-null when
  `status == closed`; one of: `completed`, `wontfix`, `duplicate`,
  `spec-revised`, `no-longer-applicable`, `resolved-out-of-band`.
- `reason` — string or `null`. Closure narration; REQUIRED
  non-null for closure records.
- `audit` — object or `null`. Present when `resolution` is one
  of `{completed, spec-revised, resolved-out-of-band}` (the
  resolutions that imply git activity landed on the canonical
  branch); null otherwise. Schema:
  - `verification_timestamp` (string, required). UTC ISO-8601
    seconds of audit-record creation.
  - `commits` (array of strings, required, MAY be empty). SHAs
    of commits comprising the work. After squash-merge these
    SHAs may no longer exist locally; tooling MUST tolerate
    that case.
  - `files_changed` (array of strings, required, MAY be empty).
    Repo-root-relative paths touched by the work.
  - **`merge_sha`** (string, required, non-empty). SHA of the
    merge commit on the canonical branch that introduced this
    work. Tooling MUST verify it is reachable from
    `origin/<canonical_branch>` via
    `git merge-base --is-ancestor`.
  - **`pr_number`** (integer or null, optional). GitHub PR
    number for traceability; null when the merge did not
    originate from a PR.

  The previous version of this spec stated audit is captured
  "at fix-resolution closure time." The widened rule is: audit
  MUST be present when `resolution` is one of `{completed,
  spec-revised, resolved-out-of-band}` — all three carry an
  implied canonical-branch merge that the audit attests.
  Resolutions in `{wontfix, duplicate, no-longer-applicable}`
  MUST have `audit: null`.
- `superseded_by` — `id` or `null`. Used for record amendments;
  not for `resolution: duplicate` (use `reason` for that).
- `spec_commitment_hint` — string or `null`. OPTIONAL on the read
  path (records authored before this field's introduction read back
  as `null`); always written explicitly on append. When non-null,
  carries the verbatim `id_hint` from a spec-side
  `spec_commitments.impl_followups[]` declaration (per
  `livespec/SPECIFICATION/contracts.md` §"Implementation-plugin
  contract — the 10-skill surface" → "Work-item
  `spec_commitment_hint` field"). When the work-item was filed via
  the freeform path with no spec-side commitment to pair against,
  the field is `null`. The field is the surface livespec's
  `unresolved-spec-commitment` doctor invariant queries via
  `list-work-items --json` to verify every declared spec→impl
  commitment maps to a filed work-item.
- `supersedes` — string or `null`. The append-only supersession
  pointer (per §"Append-only store disciplines"). `null` marks an
  original record — one that supersedes nothing; non-null carries
  the stable per-record identity of the single prior record this
  record amends. The identity encoding MUST be derivable from
  record content alone (no file positions, no external state);
  the concrete encoding is fixed at realization time and tracked
  as a follow-up work-item.

### Materialized view

The materialized view of an entity MUST be derivable by a
reduction that is INDEPENDENT of the physical order of records in
the store file: the current head per `id` is the
supersession-chain head computed from the in-record `supersedes`
pointers (per §"Append-only store disciplines"), with a
deterministic tie-break (`captured_at`, then the stable per-record
identity). Physical file/line position MUST NOT be the reduction
key — git is free to reorder lines during a merge, so the legacy
"latest record per `id` by file order" rule is DEPRECATED and
remains only as the implemented interim behavior until the
realization work-items land. Concurrent divergence (two records
for one entity, neither superseding the other) MUST be
representable and detectable by the reduction, NOT silently
resolved by picking one winner.

A record with `status: closed` is terminal — appending further
records carrying the same `id` is ALLOWED but DISCOURAGED (the
right pattern is to file a new work-item with a fresh `id` that
references the closed one). Readers of this plugin MUST consume
materialized views, never raw record sequences.

### Backfill for existing closed work-items

Existing closed work-items in `work-items.jsonl` (created before
the `merge_sha` schema addition) have `audit` records without
`merge_sha`. They cannot be validated against
`work_item_merge_evidence` (below) until backfilled. Two
strategies are admissible:

- **(a) Disciplined backfill** (default). Scan `git log` for the
  SHAs in each closed work-item's `audit.commits`. For each,
  find the merge commit on `origin/<canonical_branch>` that
  introduced it via
  `git rev-list --merges --ancestry-path <commit>..origin/<canonical_branch> | tail -1`.
  Populate `merge_sha` with that value. If the SHA is not on
  the canonical branch (orphaned), surface a finding asking
  the user to dispose (re-open, change resolution to
  `wontfix`, etc.). This produces real, verifiable data, and
  surfacing orphans IS the point — they are exactly what the
  merge-evidence epic exists to find.
- **(b) Grandfather sentinel** (fallback). Populate
  `merge_sha: "<pre-schema-bootstrap>"` on every existing
  closed work-item. Exempt this sentinel from the static
  check's reachability test. Fast but leaves a known-incomplete
  sentinel in the data.

The migration script ships Strategy (a) as the default, with
Strategy (b) as a `--grandfather` fallback flag for
hostile-environment cases where the git history is genuinely
unreachable. The actual migration script is impl work, tracked
as a follow-up work-item filed after the PC was accepted.

### `work_item_merge_evidence` static check

The check walks every record in the configured `work_items_path`
and applies the following rules.

For each work-item with `status == "closed"`:

- If `resolution` is in `{completed, spec-revised, resolved-out-of-band}`:
  - REQUIRE `audit` is non-null.
  - REQUIRE `audit.merge_sha` is non-empty.
  - REQUIRE `git cat-file -e <merge_sha>` exits 0 (the SHA
    exists in the local repo).
  - REQUIRE
    `git merge-base --is-ancestor <merge_sha> origin/<canonical_branch>`
    exits 0.
- If `resolution` is in `{wontfix, duplicate, no-longer-applicable}`:
  - REQUIRE `audit` is null OR `audit.merge_sha` is the empty
    string and `audit.commits` is empty (the negative-evidence
    case — a record that says "this was closed administratively"
    must not carry merge-evidence).
- If `resolution` is null AND `status == "closed"`:
  - FAIL with message "closed work-item without resolution is
    malformed."

Work-items with `type == "epic"` are EXEMPT from the
merge-evidence requirement. Epics close when their `depends_on`
work-items are all closed; the check INSTEAD requires that
every entry in `depends_on` resolves to a closed work-item.

All operations are local `git` invocations (`cat-file`,
`merge-base`); the check is network-free per the existing
no-network-I/O constraint.

The check is invoked by the impl plugin's
`process-work-items` lifecycle (or as a doctor-static-eligible
check that runs against every spec tree's project root). Exact
wiring is determined at implementation time.

The check is plugin-private to `livespec-impl-git-jsonl` (it
depends on the JSONL schema this plugin defines). A future
sibling impl plugin using a different storage format would ship
its own equivalent.

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
- `supersedes` — string or `null`. Same semantics as the
  work-items schema's `supersedes` key (per §"Append-only store
  disciplines"); required-on-write, optional-on-read.

## Append-only store disciplines

A *git-committed append-structured store* is any Work Items /
Memos store that (a) is committed to git as its audit trail and
(b) records state transitions by appending new records rather
than rewriting existing ones. Both of this plugin's stores
(`work-items.jsonl`, `memos.jsonl`) make this design choice, so
the disciplines below bind them; a future backend without the
property (e.g. a transactional database) would be exempt.

These disciplines migrate verbatim-in-spirit from livespec's
formally REJECTED proposed change
`append-only-store-legibility-and-merge-safe-reduction` (rejected
at the livespec v103/v104 revise, 2026-06-09, decision-record
item 6 of `contract-and-reference-implementations-phase-1`;
source: livespec commit `01c8324`,
`SPECIFICATION/history/v103/proposed_changes/`). Under the
re-steered contract the work-items and memos stores are the
orchestrator's PRIVATE Ledger — core's contract never reads
them — so the disciplines have no home in livespec's
SPECIFICATION and land here, where the store they govern lives.

- **Record self-identification.** Every record MUST
  self-identify, from record content alone, as either an
  original record (`supersedes: null`) or an amendment that
  supersedes a specific prior record. A reader encountering more
  than one record for a single entity `id` MUST be able to
  determine, from record content alone, which record is the
  current head and which are superseded history — WITHOUT
  consulting file order and without running skill-private logic.
  Superseded records remain in the store as audit trail.
- **Order-independent reduction.** The materialized view is the
  supersession-chain head per §"Materialized view" above; the
  reduction MUST NOT depend on any property git may change
  during a merge.
- **Read path only via the query surface.** Any consumer of
  store state — this plugin's own skills, the orchestrator
  layer, operator/agent tooling — MUST obtain it through the
  published query CLIs/skills (`list-work-items`, `list-memos`,
  `next`) or through the single canonical reducer they delegate
  to. Direct parsing of a backing store file by shipped code is
  NON-CONFORMING. This constrains the READ PATH only; the
  backing append store remains the committed source of truth and
  audit trail. The rule cannot police an ad-hoc interactive
  shell command; the self-identification and order-independent
  reduction obligations are the defense for that residual
  surface (a raw read becomes self-explanatory rather than
  misleading).
- **One canonical reducer.** Exactly one reduction
  implementation exists; every query wrapper and check consumes
  it rather than re-deriving "latest wins" per skill. The
  reducer resolves supersession chains and surfaces any entity
  with divergent un-superseded heads as an explicit, detectable
  result. (It MAY later move into the shared `livespec_runtime`
  library; that relocation is a realization decision, not a
  contract requirement.)
- **Store-integrity checks (orchestrator-private).** Two checks
  wire into this repo's `just check` aggregate (NOT into
  livespec's doctor — the store is orchestrator-private):
  `no-divergent-heads` fires `fail` when any entity id resolves
  to more than one un-superseded head, naming the offending
  entity and the conflicting record identities;
  `no-raw-store-read` fires `fail` when shipped code opens a
  declared backing store path directly, bypassing the
  reducer/query surface.
- **Merge-safe append (`merge=union`).** Once reduction is
  order-independent, a `.gitattributes` `*.jsonl merge=union`
  entry MUST be added so concurrent appends from parallel
  worktrees merge without manual textual-conflict resolution —
  safe precisely because reduction no longer depends on physical
  line order.

Realization (the `supersedes` field in the store code, the
canonical reducer, the two checks, and the `.gitattributes`
entry) is tracked as follow-up work-items in this repo's
work-item store; until they land, the DEPRECATED file-order
reduction remains the implemented interim behavior.

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
`/livespec-impl-git-jsonl:` namespace.

## Persistent Agent Knowledge realization

Per `livespec/SPECIFICATION/contracts.md` §"Persistent Agent
Knowledge realization", the per-plugin form is
implementation-dependent. `livespec-impl-git-jsonl` realizes the
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
impl-plugin. For `livespec-impl-git-jsonl`:

```jsonc
{
  "implementation": { "plugin": "livespec-impl-git-jsonl" },
  "livespec-impl-git-jsonl": {
    "format": "jsonl",
    "compat": {
      "livespec": ">=2.0.0,<3.0.0",
      "pinned": "v2.3.0"
    },
    "work_items_path": "work-items.jsonl",
    "memos_path": "memos.jsonl",
    "canonical_branch": "master"
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

**`canonical_branch`** (optional string). The canonical branch
name against which merge-evidence checks (see
§"`work_item_merge_evidence` static check") verify
reachability. Default: the value of
`git symbolic-ref --short refs/remotes/origin/HEAD` (typically
`master` or `main`). Hard-coded fallback when symbolic-ref
resolution fails: `"master"`. The key is project-level (one
value per repo), not per-work-item — static checks resolve it
once per invocation and apply it uniformly.

The configuration block is read by every skill at invocation
time. A missing or malformed block MUST fire a `fail` finding
from doctor's `contract-version-compatibility` invariant
(upstream §"Cross-boundary doctor invariants").

## Cross-boundary handoffs

Per `livespec/SPECIFICATION/contracts.md` §"Cross-boundary
handoffs", this plugin participates in these red-edge handoffs:

1. `/livespec-impl-git-jsonl:capture-spec-drift` →
   `/livespec:propose-change` (drift findings).
2. `/livespec-impl-git-jsonl:process-memos` →
   `/livespec:propose-change` (spec-bound memo disposition).
3. `/livespec:doctor` →
   `/livespec-impl-git-jsonl:list-memos --filter=untriaged --json`
   (memo-hygiene invariant).
4. `/livespec:doctor` →
   `/livespec-impl-git-jsonl:list-work-items --json` (work-item
   structural invariants).
5. `/livespec:doctor` →
   `/livespec-impl-git-jsonl:detect-impl-gaps --json` (gap-
   detection invariants `gap-tracking-one-to-one` and
   `no-stale-gap-tied`).

The handoff mechanism is namespace invocation (per
`livespec/SPECIFICATION/contracts.md` §"Cross-plugin
invocation") — never direct CLI shelling-out to wrapper paths.

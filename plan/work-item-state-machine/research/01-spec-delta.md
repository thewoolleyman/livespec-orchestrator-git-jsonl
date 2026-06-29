# L1b spec delta — `SPECIFICATION/contracts.md` (the propose-change payload)

This is the **drafted propose-change payload**, human-readable — the
exact `contracts.md` edits the `revise` gate ratifies. Authority for
every value: the cross-repo design of record (`02-design.md` §2/§5/§6
"Backend mapping" git-jsonl column + consequence (d); `03-decision-log.md`
decisions 24/32/36/39/44).

**Scope note.** The slice plan pins the spec delta as "`## Work-items
JSONL record schema` 16→17 keys (`+rank`, `−priority`); status-enum prose
→ the 7 states." Re-vendoring v0.5.0 flips the vendored `WorkItemStatus`
Literal to the 7 states, and the git-jsonl store validates `status`
against that Literal (consequence (d)) — so the old values
`open`/`in_progress`/`closed`/`deferred` become invalid. That **forces**
the downstream prose that referenced them to be reconciled in the SAME
propose-change for internal consistency: the closure-status term
(`closed` → `done`), the dispatchable predicate (`open` → `ready`), the
`next` ranking (priority → rank), and the `priority` references in the
skill surfaces. All edits land under EXISTING `## ` headings; **no `## `
(H2) heading is added/changed/removed**, so `tests/heading-coverage.json`
needs no co-edit (the shared check tracks H2 only).

---

## Delta 1 — rewrite `## Work-items JSONL record schema` (the intro + key list)

**Current** intro says "The sixteen keys… The first fourteen (`id`
through `superseded_by`)…" — a latent undercount (the section actually
enumerates **17** key bullets; `id`…`superseded_by` is 15 bullets).
After `−priority`/`+rank` the count stays **17**, and the strictly
required-on-read set becomes exactly **14**. Replace the intro with:

> Each line is a single JSON object. The **seventeen** keys enumerated
> below are the canonical schema. **Fourteen** (`id`, `type`, `status`,
> `title`, `description`, `origin`, `gap_id`, `assignee`, `depends_on`,
> `captured_at`, `resolution`, `reason`, `audit`, `superseded_by`) are
> required-on-write AND required-on-read. **`rank`** is required-on-write
> (always serialized) but optional-on-read: a legacy record authored
> before `rank` reads back as the store-adapter **bottom-sentinel** (NOT
> a violation, NOT `null`). `spec_commitment_hint` and `supersedes` are
> required-on-write but optional-on-read (legacy records read back as
> `null`). Additional keys beyond these seventeen are forbidden — schema
> violations fire as doctor `fail` findings.

Per-key edits:

- **`status`** — was `one of: open, in_progress, blocked, closed,
  deferred`. **Replace with:** `one of the seven livespec lifecycle
  states: backlog, pending-approval, ready, active, acceptance, blocked,
  done`. Validated against the vendored
  `livespec_runtime.work_items.types.WorkItemStatus` Literal (so the enum
  auto-tracks the runtime schema bump). `blocked` is a name-matched reuse;
  `done` is the terminal state (was `closed`). A closure record now
  carries `status: done` (not `status: closed`).
- **`+ rank`** — NEW bullet, inserted after `gap_id` (the runtime field
  order). Text: *"string, the fractional/lexicographic ordering key — the
  **sole ordering authority** (decisions 11/12/39; `priority` is
  removed). Required non-null on write. A legacy record lacking `rank`
  reads back as the shared bottom-sentinel
  `livespec_runtime.work_items.rank.BOTTOM_SENTINEL` (a char outside the
  base-62 alphabet, e.g. `~`, sorting strictly after every real key),
  supplied by the **store adapter** — NOT nullability in the domain type.
  Every live (head, non-superseded) record MUST carry a real,
  non-sentinel rank (a doctor-checkable invariant; a stray sentinel-rank
  head sorts last and is named, never crashes the listing)."*
- **`− priority`** — REMOVE the bullet. Add a one-line note under the key
  list: *"`priority` (the former `integer 0–4`) is **removed** — `rank`
  is the sole ordering authority (decision 39). Legacy physical lines
  keep `priority` harmlessly in append-only history; new/backfilled
  records omit it. No data scrub."*
- **`resolution` / `reason` / `audit`** — the clauses keyed on
  `status == closed` are re-pointed to `status == done` (the terminal
  state rename). Resolution enum values are unchanged.

---

## Delta 2 — `### Materialized view` closure-term update

The clause *"A record with `status: closed` is terminal — appending
further records carrying the same `id` is ALLOWED but DISCOURAGED…"* →
`status: done`. (Same paragraph; only the state name changes.)

---

## Delta 3 — `### \`work_item_merge_evidence\` static check` closure-term update

Every `status == "closed"` in the check's rules → `status == "done"`
(the terminal-state rename). The resolution-driven audit requirements are
otherwise unchanged. (`type == "epic"` exemption + the
all-depends_on-resolve-to-done requirement unchanged, with `closed` →
`done`.)

---

## Delta 4 — `#### next` ranking algorithm prose

- The ranking algorithm (currently "1. ready items: `status: open`…;
  2. Score by priority then gap-tied then captured_at; 3. id tie-break")
  → **"1. ready items: `status: ready` AND `depends_on` empty or
  all-`done`; 2. Order by `rank` (the sole ordering key); 3. `id`
  lexicographic tie-break."** The `priority → gap-tied → captured_at`
  heuristic is retired (decision 39).
- **`urgency` derivation** (currently "P0 → high; P1, P2 → medium; P3, P4
  → low"). Priority is removed, and `rank` is a pure ordering key, not a
  severity — so the priority-tier derivation is retired. **Replace with:**
  *"`urgency` is a uniform advisory `medium` for every ready candidate;
  the ranked ORDER (by `rank`) is the dispatch signal. (`urgency` is a
  git-jsonl-specific advisory field; the cross-plugin contract does not
  prescribe its derivation.)"* — a reversible, advisory, decide-and-inform
  choice (no design rule governs git-jsonl urgency once priority is gone).
- The candidate's impl-specific extra fields: `priority` → `rank` ("each
  candidate MAY include `rank` and `origin`").

---

## Delta 5 — `#### list-work-items` filter prose

- `--filter=ready` — was `status: open AND no unresolved depends_on` →
  **`status: ready` AND `depends_on` empty or all-`done`** (the
  dispatchable set; same `is_item_ready` predicate `next` uses).
- `--filter=closed` — was `status: closed only` → **`status: done`
  only**. The filter NAME stays `closed` (a stable CLI token; renaming it
  is a separate compat decision), but its predicate matches the terminal
  `done` state. *(Decide-and-inform: keep the `closed` filter token,
  re-point its predicate to `done`.)*
- `--filter=blocked` — unchanged (`status: blocked` survives the rename
  name-matched).

---

## Delta 6 — `#### capture-work-item` priority drop

The freeform-filing description *"The user supplies title, description,
type, and priority"* → drop `priority`. Per the design, create POSITION
(`rank`) replaces priority as the ordering input (decision 13); for the
git-jsonl realization the minimal consistent edit is to drop the
`priority` input and note that order is set by `rank` (the create
position is `bottom` by default for the freeform path; a full
`{top|bottom|before|after}` position parameter is a later enhancement not
forced by this slice). Records still file with `origin: freeform`,
`gap_id: null`.

---

## heading-coverage co-edit — none required

The `livespec_dev_tooling.checks.heading_coverage` check tracks **only
`## ` (H2) headings**. Every edit above lands under an existing H2
(`## Work-items JSONL record schema`, `## Append-only store disciplines`,
`## The seven-skill surface`); the H2 set is unchanged. So **no
`tests/heading-coverage.json` co-edit** — the existing rows already cover
these sections at the check's granularity. (The kickoff's "co-edit for
any `## `-heading change" is satisfied vacuously.)

---

## Code blast radius (for `groom`/`implement`, NOT this propose-change)

The spec delta above forces these code edits (the `groom` cut + the
red-green-replay implement; tracked separately):

- **re-vendor** `livespec_runtime` v0.4.0 → v0.5.0 (new
  `work_items/{lifecycle,rank,_fractional_indexing}.py`; 7-state
  `WorkItemStatus`; `+rank −priority` `WorkItem`; `BOTTOM_SENTINEL`).
- `store.py` — `_WORK_ITEM_REQUIRED_KEYS` drop `priority`; `rank` joins
  the optional-on-read presence set but `_parse_work_item` substitutes
  `BOTTOM_SENTINEL` when absent (not `None`); a `rank` str validator;
  `_parse_work_item` drops `priority=`, adds `rank=`.
- `commands/next.py` — `_sort_key` → `(item.rank, item.id)`; drop
  `_urgency_for(priority=…)` (constant `medium`); `_candidate_for` emits
  `rank` not `priority`; docstring + `reason` narration.
- `commands/_cross_repo.py` — `is_item_ready` `status == "open"` →
  `status == "ready"`; the dep `RefStatus.CLOSED` mapping `status ==
  "closed"` → `status == "done"`.
- `commands/list_work_items.py` — filter predicates `closed`→`done`;
  human-output `P{priority}` segment dropped (use `rank`).
- `checks/work_item_merge_evidence.py` + `migration/
  merge_evidence_backfill.py` — `status != "closed"` → `status != "done"`.
- `migration/beads_to_jsonl.py` — status default + closed-handling →
  the new states (migration tool; align its mapping).
- tests + the golden-master + e2e-cli fixtures — re-author every fixture
  record to the new schema (`+rank`, `−priority`, 7-state status,
  `done` closures).

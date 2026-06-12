# livespec_impl_git_jsonl/migration/

One-shot migration utilities that translate a legacy beads export
into the plugin's JSONL substrate. Behind the `migrate_beads.py`
shebang wrapper.

- `beads_to_jsonl.py` — reads a `.beads/issues.jsonl` export view
  (the schema `bd list --format=json` produces), maps each beads
  issue onto the `WorkItem` schema in `SPECIFICATION/contracts.md`
  §"Work-items JSONL record schema", and appends one final-state
  record per issue via `store.append_work_item`. Exports
  `main(argv=None) -> int` and `translate_record`.
- `depends_on_typed_form.py` — one-shot per-repo migration that
  merges `blocked_by` into `depends_on`, converts bare-string
  `depends_on` entries to the typed `{"kind": "local",
  "work_item_id": "<id>"}` form, and drops the absorbed `blocked_by`
  field. Records already in the typed shape pass through unchanged.
- `merge_evidence_backfill.py` — one-shot per-repo merge-evidence
  backfill per SPECIFICATION/contracts.md §"Backfill for existing
  closed work-items". Strategy (a), the disciplined default,
  populates `audit.merge_sha` from local git evidence (the
  `audit.commits` SHAs, falling back to a `git log --grep=<id>`
  walk; the introducing merge commit via `git rev-list --merges
  --ancestry-path`, or the commit itself when the work landed
  without a merge commit). Strategy (b), the `--grandfather` flag,
  populates the `<pre-schema-bootstrap>` sentinel instead. Legacy
  audit objects lacking `merge_sha` are unreadable by the canonical
  query surface (that is WHY this migration exists), so phase 1
  repairs those record lines in place (raw read, the sanctioned
  exception below); phase 2 then consumes the canonical surface to
  append a superseding merge-evidence transition record per
  audit-null closed head. Orphans (no evidence reachable from
  `origin/<canonical_branch>`) are surfaced as findings and BLOCK
  all writes (all-or-nothing). Exports `main(*, argv=None) -> int`,
  `backfill_file`, and `BackfillReport`.

Migration-specific constraints:

- The migration is ONE-SHOT and intentionally NOT idempotent —
  re-running on the same input appends duplicate records. It is run
  exactly once during cutover; all subsequent state changes go
  through the regular heavyweight skills, never through this module.
- It produces the materialized final-state record per issue (not a
  Red→Green pair). Future state transitions are new appended records
  per the append-only discipline.
- Still subject to the full package rule set: keyword-only args,
  `__all__` declared, EXPECTED errors via
  `livespec_impl_git_jsonl.errors`, `sys.stdout`/`sys.stderr` writes
  only in `main()`, no `print()`.
- Writes go ONLY through `store.append_work_item` (append-only); do
  NOT open the JSONL for rewrite/truncate. EXCEPTION: a schema
  migration whose INPUT is unreadable by the canonical surface
  (e.g. `merge_evidence_backfill.py` phase 1 — legacy audit objects
  without `merge_sha` fail the read path's schema validation) may
  read raw lines and rewrite ONLY the offending lines in place;
  untouched lines keep their original bytes so record identities
  are preserved.

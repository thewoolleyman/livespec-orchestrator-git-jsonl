# tests/livespec_impl_git_jsonl/migration/

Tests for the one-shot migration utilities under
`.claude-plugin/scripts/livespec_impl_git_jsonl/migration/`.

- `test_beads_to_jsonl.py` — covers `main()` and `translate_record`:
  asserts a beads issue record maps onto the `WorkItem` schema
  correctly (id, type, status, priority, gap-id / resolution label
  extraction, audit record), and that output is appended via the
  store's append-only path. Builds beads-shaped fixture dicts and a
  `tmp_path` output file.
- `test_depends_on_typed_form.py` — covers the `blocked_by` →
  typed-`depends_on` migration: `blocked_by` merged and
  deduplicated, bare-string entries converted to `{"kind": "local",
  "work_item_id": ...}`, `blocked_by` dropped, already-typed records
  passed through unchanged, and records with no legacy data NOT
  re-emitted.
- `test_merge_evidence_backfill.py` — covers the merge-evidence
  backfill black-box through `main()` against real `tmp_path` git
  repos (host-config-isolated): phase-1 in-place repair of legacy
  audit objects lacking (or carrying an empty) `merge_sha` via
  `audit.commits` evidence (introducing merge commit, or the commit
  itself when no merge commit exists, with unusable candidates
  skipped) and via the `git log --grep=<id>` fallback; phase-2
  superseding transition appends for audit-null closed heads
  (asserting `supersedes` identity parity with
  `store.work_item_record_identity` and a single reduced head);
  orphan findings blocking ALL writes (both phases); the
  `--grandfather` sentinel path composing with the
  `work_item_merge_evidence` check; `--dry-run`; the
  nothing-to-backfill pass-through; the unreadable-input error
  paths; and the `--canonical-branch` flag.

Conventions:

- These tests verify the one-shot transformation only; they do NOT
  assert idempotency (the migration is intentionally non-idempotent
  — re-running appends duplicates).
- Write all output to `tmp_path` fixtures; never touch the repo's
  real work-items JSONL.
- 100% line + branch coverage, including every field-mapping and
  label-parsing branch.

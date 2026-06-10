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

Conventions:

- These tests verify the one-shot transformation only; they do NOT
  assert idempotency (the migration is intentionally non-idempotent
  — re-running appends duplicates).
- Write all output to `tmp_path` fixtures; never touch the repo's
  real work-items JSONL.
- 100% line + branch coverage, including every field-mapping and
  label-parsing branch.

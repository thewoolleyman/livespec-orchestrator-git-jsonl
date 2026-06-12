# tests/livespec_impl_git_jsonl/io/

Tests for the `livespec_impl_git_jsonl.io` sub-package under
`.claude-plugin/scripts/livespec_impl_git_jsonl/io/`.

The `io/` package is the architectural boundary for all file I/O and
expected-error handling (try/except), per the `no_except_outside_io`
check.

- `test_store.py` — raw JSONL I/O helpers: `iter_records`,
  `append_record`, `parse_jsonl_line`. Covers missing-file, empty-line,
  bad-JSON, non-dict-JSON error paths; happy-path yields; append creates
  files and parent directories.
- `test_jsonc.py` — JSONC parsing: `loads` (with comment stripping and
  parse-error signaling) and `loads_optional` (None on error).
- `test_cross_repo.py` — cross-repo manifest helpers:
  `parse_cross_repo_manifest_optional` and
  `parse_depends_on_entry_optional` (both return None on schema error).

Conventions:

- 100% line + branch coverage on every io/ module.
- Use `tmp_path` for filesystem fixtures; never touch repo-level stores.
- No Hypothesis needed here (these are file-I/O functions, not pure
  transformations).

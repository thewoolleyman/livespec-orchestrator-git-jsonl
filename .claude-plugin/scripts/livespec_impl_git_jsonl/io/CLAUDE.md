# livespec_impl_git_jsonl/io/

Architectural I/O boundary layer. All file I/O and all try/except
for EXPECTED errors live here, and only here. The `no_except_outside_io`
check enforces this boundary across the rest of the package.

- `store.py` — raw JSONL primitives: `iter_records` (stream
  `(line_number, dict)` pairs; raises `StoreFileMissingError` on absent
  file, `MalformedRecordLineError` on bad JSON or non-dict line),
  `append_record` (append a JSON line, creating the file and parent
  dirs), `parse_jsonl_line` (parse one raw line; the error-raising
  core shared by `iter_records` and migration raw-read paths).
- `_jsonc.py` — JSONC comment-stripping parser: `loads` (raises
  `JsoncParseError`), `loads_optional` (returns None on parse error).
  Re-exported by `commands/_jsonc.py` for backwards compatibility.
- `_cross_repo.py` — cross-repo manifest and entry parsing: wraps
  `livespec_runtime.cross_repo.types.parse_cross_repo_manifest` and
  `parse_depends_on_entry` with optional-return semantics so callers
  outside io/ need no try/except.

Rules an agent editing this tree must follow:

- Every module declares `__all__: list[str]`.
- Files in this package are WHOLLY EXEMPT from `no_except_outside_io`
  (try/except is expected here). They are NOT exempt from any other
  check (`keyword_only_args`, `all_declared`, etc.).
- The io/ modules are pure I/O adapters; no domain logic, no
  cross-module orchestration. Domain-level decisions belong above.

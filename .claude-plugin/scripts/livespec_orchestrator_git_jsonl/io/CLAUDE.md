# livespec_orchestrator_git_jsonl/io/

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
  `JsoncParseError` carried on the failure track). A caller wanting the
  absent-shaped answer writes `.value_or(None)` at its own call site.
  Re-exported by `commands/_jsonc.py` for backwards compatibility.
- `_cross_repo.py` — cross-repo manifest and entry parsing on the
  `Result` railway, so callers outside io/ need no try/except:
  `parse_cross_repo_manifest_result` converts the
  `CrossRepoSchemaError` that
  `livespec_runtime.cross_repo.types.parse_cross_repo_manifest` raises,
  while `parse_depends_on_entry_result` passes its upstream parser's
  own `Result` straight through (since livespec-runtime v0.28.0
  `parse_depends_on_entry` answers on the failure track itself).

Rules an agent editing this tree must follow:

- Every module declares `__all__: list[str]`.
- Files in this package are WHOLLY EXEMPT from `no_except_outside_io`
  (try/except is expected here). They are NOT exempt from any other
  check (`keyword_only_args`, `all_declared`, etc.).
- The io/ modules are pure I/O adapters; no domain logic, no
  cross-module orchestration. Domain-level decisions belong above.

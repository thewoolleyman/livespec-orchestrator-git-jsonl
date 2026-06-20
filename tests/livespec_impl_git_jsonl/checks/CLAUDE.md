# tests/livespec_impl_git_jsonl/checks/

Tests for the orchestrator-private store-integrity checks under
`.claude-plugin/scripts/livespec_impl_git_jsonl/checks/`.

- `test_no_divergent_heads.py` — exercises pass modes (absent store,
  empty store, clean store, resolved supersession chain), the fail
  mode (divergent work-item heads — asserting the offending entity id
  AND each conflicting record identity appear in the output), and the
  unreadable-store failure modes (malformed line, schema violation),
  all black-box through `main()`.
- `test_no_raw_store_read.py` — builds fixture source trees in
  `tmp_path` planting conforming and offending open-calls, asserts the
  canonical store-module exemption and the `_vendor/` exclusion, and
  runs the check against this repo's real shipped tree as the
  conformance pin.
- `test_work_item_merge_evidence.py` — builds real `tmp_path` git
  repos (host-config-isolated) with `refs/remotes/origin/<branch>`
  refs and store fixtures via the append API; exercises the pass
  modes (absent/empty store, reachable `merge_sha`, grandfather
  sentinel, administrative closure without audit, epic with closed
  children), the fail modes (missing audit, unknown and unreachable
  `merge_sha`, administrative closure carrying audit, closed item
  without resolution, epic with a non-closed local child), and the
  `resolve_canonical_branch` precedence chain (`.livespec.jsonc` key
  → `origin/HEAD` symbolic-ref → `master` fallback, including every
  unusable-config shape).

Coverage rules:

- 100% line + branch on every check module, exercised black-box
  through `main()` (exit code + stdout), not by poking helpers.
- Build store fixtures in `tmp_path` via the store append API (or raw
  writes only when the scenario IS a malformed store); never read or
  write the repo's real work-items file.
- Tests that rely on the cwd-default store resolution MUST
  `monkeypatch.chdir(tmp_path)` so a failing run cannot touch repo
  state.

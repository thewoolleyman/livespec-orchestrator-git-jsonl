# livespec_impl_git_jsonl/checks/

Orchestrator-private store-integrity checks, wired into this repo's
`just check` aggregate (NOT livespec's doctor — the stores are
orchestrator-private) per SPECIFICATION/contracts.md §"Append-only
store disciplines" → "Store-integrity checks (orchestrator-private)".

- `no_divergent_heads.py` — materializes both declared backing stores
  via the canonical reducer (`store.reduce_work_item_heads` /
  `store.reduce_memo_heads`) and fails when any entity id resolves to
  more than one un-superseded head, naming the offending entity id and
  the conflicting record identities so the operator can append a
  reconciling record.
- `no_raw_store_read.py` — AST-scans shipped code (committed `.py`
  under `.claude-plugin/scripts/` and `dev-tooling/`, with `_vendor/`
  and `__pycache__/` excluded) and fails when anything other than the
  canonical store module opens a declared backing store path directly,
  bypassing the reducer/query surface.
- `work_item_merge_evidence.py` — per SPECIFICATION/contracts.md
  §"Work-items JSONL record schema" → "`work_item_merge_evidence`
  static check": walks the materialized work-items view and fails any
  closed work-item with a merge-implying resolution (`completed`,
  `spec-revised`, `resolved-out-of-band`) whose audit `merge_sha` is
  missing or not reachable from `origin/<canonical_branch>` (local
  `git cat-file -e` + `git merge-base --is-ancestor`; network-free),
  any administratively closed work-item carrying merge-evidence, and
  any closed work-item without a resolution. Epics are exempt but
  every local `depends_on` child must be closed. The backfill
  grandfather sentinel (`GRANDFATHER_MERGE_SHA_SENTINEL`) is exempt
  from the reachability test. Also exports
  `resolve_canonical_branch` (`.livespec.jsonc` plugin-block key →
  `origin/HEAD` symbolic-ref → `master`), shared with the
  merge-evidence backfill migration.

Rules an agent editing this tree must follow:

- Checks MUST consume the canonical reducer (or the published query
  surface) — never re-derive "latest wins" locally. That is the
  one-canonical-reducer obligation these checks exist to defend.
- Each public module exports `main(argv=None) -> int`; exit 0 = pass,
  exit 1 = fail. `main()` is the only place `sys.stdout.write` is
  permitted; helpers return data, never write.
- Catch the EXPECTED `livespec_impl_git_jsonl.errors` exceptions at
  the read boundary; a malformed or schema-violating store is a check
  FAILURE (reported, exit 1), not an uncaught traceback.
- Keyword-only arguments (`*` separator) on every helper; the
  `main(argv)` positional is the argparse-convention exemption.
- Wrappers live at `.claude-plugin/scripts/bin/check_<slug>.py`; the
  justfile recipes `check-no-divergent-heads` /
  `check-no-raw-store-read` invoke them and are wired as private
  extras (after the canonical block) in the `check:` aggregate.

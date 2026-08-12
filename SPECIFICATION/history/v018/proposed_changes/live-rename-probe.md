# Frozen plaintext tracking store

As of epic **li-ws2iv4** ("Phase 5 — Flip each repo's `.livespec.jsonc`
to `livespec-impl-beads`; archive/freeze plaintext store"), this repo's
OWN impl tracking moved from the plaintext JSONL store at the repo root
onto its per-repo **livespec-impl-beads** Dolt tenant.

- Tenant identity: `livespec-impl-plaintext`
  (`database == server_user == prefix == tenant`).
- Live store: the beads tenant, reached via `.beads/config.yaml` +
  the `BEADS_DOLT_PASSWORD` env var (never committed). Connection
  details live in `.livespec.jsonc` under `livespec-impl-beads`.

The files in this directory are the **frozen** pre-cutover plaintext
store, retained for audit/history only:

- `work-items.jsonl` — frozen work-item records (migrated into the tenant).
- `memos.jsonl` — frozen memos.

These files are no longer read by any tooling and MUST NOT be edited.
The cutover is reversible: restoring `.livespec.jsonc`'s
`livespec-impl-plaintext` impl block (pointing `work_items_path` /
`memos_path` back at these files, moved to the repo root) re-activates
the plaintext store.

> NOTE: the generic `work-items.jsonl` / `memos.jsonl` references that
> remain throughout the plugin's own source (`.claude-plugin/scripts/`,
> skills, and `tests/e2e-cli/fixtures/**`) are the plugin's GENERIC store
> handling and TEST DATA — they are unrelated to this repo's own frozen
> tracking store and were intentionally left untouched.

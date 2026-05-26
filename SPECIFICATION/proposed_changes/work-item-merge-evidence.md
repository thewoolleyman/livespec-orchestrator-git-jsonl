---
topic: work-item-merge-evidence
author: claude-opus-4-7
created_at: 2026-05-26T07:00:00Z
---

## Cross-cutting parent

This PC is a child of the coordinating epic `livespec#coordinating-epic-stale-revise-enforcement` (filed at `livespec/SPECIFICATION/proposed_changes/coordinating-epic-stale-revise-enforcement.md`). The parent PC owns the cross-cutting design decisions (the 4-layer enforcement story, the parent_proposed_change front-matter convention); this PC owns Layer 4 — the work-item merge-evidence schema and its static check.

This PC does NOT yet carry a `parent_proposed_change` front-matter field. That field is itself proposed for the first time by the parent PC (which has to widen `livespec`'s `proposed_change_front_matter.schema.json` to admit it). After the parent's schema widening is accepted, this PC SHOULD be retroactively edited via an admin commit to add `parent_proposed_change: livespec#coordinating-epic-stale-revise-enforcement` to its front-matter.


## Problem statement

The work-item JSONL schema records `status: closed` with `resolution: fix` accompanied by an `audit` block carrying `commits` (tuple of SHAs) and `files_changed` (tuple of paths). The schema currently has NO field that proves any of those commits actually reached the canonical branch (`master` / `main`). An agent can close a work-item with `commits: ["abc123"]` where `abc123` is on a never-merged feature branch — the JSONL says fixed, reality says orphaned.

This was the second-order root cause of the 2026-05-25/26 orphaned-`spec/dev-tooling-revise-v003` incident: the work-item ledger lacked semantics for "open until externally-observable merge condition holds." Per the parent PC's RCA, the schema needs an explicit `merge_sha` field that points to a master-reachable merge commit, plus a static check that verifies reachability.


## Proposal: add merge_sha and pr_number to AuditRecord

### Target specification files

- SPECIFICATION/contracts.md

### Summary

Add two new fields to the `AuditRecord` dataclass (codified in `SPECIFICATION/contracts.md` §"Work-items JSONL record schema"):

- **`merge_sha`** (string, required when audit is present): the SHA of the merge commit on the canonical branch that introduced the work-item's fix.
- **`pr_number`** (integer or null, optional): the GitHub PR number that contained the work, for traceability. Optional because not all merges originate from PRs (direct-to-canonical commits, manual merges from external branches, etc.).

Widen the existing rule "audit is only present at fix-resolution closure" to "audit MUST be present for resolutions in `{fix, spec-revised, resolved-out-of-band}`."

### Motivation

The existing `commits: tuple[str, ...]` field lists commit SHAs but proves nothing about reachability from `master`. `merge_sha` is the externally-verifiable pointer that:

- Can be checked locally via `git merge-base --is-ancestor <merge_sha> origin/<canonical_branch>`.
- Survives squash-merges (the SHA on master IS the squash commit; the original branch SHAs may no longer exist locally).
- Survives rebase-merges (the SHA on master IS the rebased commit).
- Provides a stable audit-trail entry that does not rot when feature branches are deleted.

`pr_number` adds optional human-readable traceability without coupling the audit record to GitHub-specific infrastructure (any system referring to the audit can resolve the PR via its own conventions).

### Proposed Changes

1. Update the dataclass in `livespec_impl_plaintext/types.py`:

   ```python
   @dataclass(frozen=True, kw_only=True)
   class AuditRecord:
       """Audit-trail fields captured at canonical-merge-closure time."""

       verification_timestamp: str
       commits: tuple[str, ...]
       files_changed: tuple[str, ...]
       merge_sha: str           # NEW: required
       pr_number: int | None    # NEW: optional traceability
   ```

2. Update `SPECIFICATION/contracts.md` §"Work-items JSONL record schema" to document the new fields and the widened applicability rule:

   > **`audit`** (object or null). Present when `resolution` is one of `{fix, spec-revised, resolved-out-of-band}` (the resolutions that imply git activity landed on the canonical branch); null otherwise. Schema:
   >
   > - `verification_timestamp` (string, required). UTC ISO-8601 seconds of audit-record creation.
   > - `commits` (array of strings, required, MAY be empty). SHAs of commits comprising the work. After squash-merge these SHAs may no longer exist locally; tooling MUST tolerate that case.
   > - `files_changed` (array of strings, required, MAY be empty). Repo-root-relative paths touched by the work.
   > - **`merge_sha`** (string, required, non-empty). SHA of the merge commit on the canonical branch that introduced this work. Tooling MUST verify it is reachable from `origin/<canonical_branch>` via `git merge-base --is-ancestor`.
   > - **`pr_number`** (integer or null, optional). GitHub PR number for traceability; null when the merge did not originate from a PR.

3. Update §"Work-items JSONL record schema" to widen the applicability rule:

   > The previous version of this spec stated audit is captured "at fix-resolution closure time." The widened rule is: audit MUST be present when `resolution` is one of `{fix, spec-revised, resolved-out-of-band}` — all three carry an implied canonical-branch merge that the audit attests. Resolutions in `{wontfix, duplicate, no-longer-applicable}` MUST have `audit: null`.


## Proposal: add canonical_branch to the .livespec.jsonc livespec-impl-plaintext config block

### Target specification files

- SPECIFICATION/contracts.md

### Summary

Add a new optional config key `canonical_branch` to the `livespec-impl-plaintext` top-level block in `.livespec.jsonc`. Default: the value of `git symbolic-ref --short refs/remotes/origin/HEAD` (typically `master` or `main`), with a hard-coded fallback of `master` when the symbolic-ref resolution fails.

The key is project-level (one value per repo), not per-work-item. Static checks resolve it once per invocation and apply it uniformly across all work-items being checked.

### Motivation

`canonical_branch` is a project-level invariant — it doesn't vary by work-item. Storing it as a per-`AuditRecord` field would be redundant denormalization; storing it once in `.livespec.jsonc` lets future renames (master → main) be a one-line config edit rather than a JSONL rewrite.

### Proposed Changes

Update `SPECIFICATION/contracts.md` §"`compat` block" (or the section codifying the `livespec-impl-plaintext` config block; exact section name confirmed at revise time) to add:

> **`canonical_branch`** (optional string). The canonical branch name against which merge-evidence checks verify reachability. Default: the value of `git symbolic-ref --short refs/remotes/origin/HEAD`. Hard-coded fallback when symbolic-ref resolution fails: `"master"`.

Example `.livespec.jsonc` block after the change:

```jsonc
"livespec-impl-plaintext": {
  "format": "jsonl",
  "compat": { "livespec": ">=0.1.0,<1.0.0", "pinned": "master" },
  "work_items_path": "work-items.jsonl",
  "memos_path": "memos.jsonl",
  "canonical_branch": "master"
}
```


## Proposal: add work_item_merge_evidence static check

### Target specification files

- SPECIFICATION/contracts.md

### Summary

Add a new doctor-static check `work_item_merge_evidence` that runs against the consumer repo's work-items JSONL and verifies every closed work-item with a merge-evidence-bearing resolution carries a valid, reachable `merge_sha`.

The check is plugin-private to livespec-impl-plaintext (it depends on the JSONL schema this plugin defines). A future sibling impl plugin using a different storage format would ship its own equivalent.

### Motivation

The schema change above is necessary but not sufficient. Without a check that mechanically verifies the field is populated correctly, agents can still:

- Close work-items with `merge_sha: ""` or `merge_sha: "TODO"`.
- Close work-items with a `merge_sha` that is on a feature branch but not on the canonical branch.
- Close work-items with a `merge_sha` that doesn't exist in the local git repo at all (typo, stale paste).

The static check catches all three.

### Proposed Changes

Add a new §"`work_item_merge_evidence` static check" subsection to `SPECIFICATION/contracts.md`:

> ### `work_item_merge_evidence` static check
>
> The check walks every record in the configured `work_items_path` and applies the following rules:
>
> For each work-item with `status == "closed"`:
>
> - If `resolution` is in `{fix, spec-revised, resolved-out-of-band}`:
>   - REQUIRE `audit` is non-null.
>   - REQUIRE `audit.merge_sha` is non-empty.
>   - REQUIRE `git cat-file -e <merge_sha>` exits 0 (the SHA exists in the local repo).
>   - REQUIRE `git merge-base --is-ancestor <merge_sha> origin/<canonical_branch>` exits 0.
> - If `resolution` is in `{wontfix, duplicate, no-longer-applicable}`:
>   - REQUIRE `audit` is null OR `audit.merge_sha` is the empty string and `audit.commits` is empty (the negative-evidence case — a record that says "this was closed administratively" must not carry merge-evidence).
> - If `resolution` is null AND `status == "closed"`:
>   - FAIL with message "closed work-item without resolution is malformed."
>
> Work-items with `type == "epic"` are EXEMPT from the merge-evidence requirement. Epics close when their `depends_on` work-items are all closed; the check INSTEAD requires that every entry in `depends_on` resolves to a closed work-item.
>
> All operations are local `git` invocations (`cat-file`, `merge-base`); the check is network-free per the existing no-network-I/O constraint.
>
> The check is invoked by the impl plugin's `process-work-items` lifecycle (or as a doctor-static-eligible check that runs against every spec tree's project root). Exact wiring is determined at revise time.


## Proposal: migrate existing closed work-items

### Target specification files

- SPECIFICATION/contracts.md

### Summary

Existing closed work-items in `work-items.jsonl` (created before this schema change) have `audit` records without `merge_sha`. They cannot be validated against the new check until backfilled. Two strategies are admissible:

- **(a) Disciplined backfill**: scan `git log` for the SHAs in each closed work-item's `audit.commits`. For each, find the merge commit on `origin/<canonical_branch>` that introduced it via `git rev-list --merges --ancestry-path <commit>..origin/<canonical_branch> | tail -1`. Populate `merge_sha` with that value. If the SHA is not on master (orphaned), surface a finding asking the user to dispose (re-open, change resolution to `wontfix`, etc.).
- **(b) Grandfather sentinel**: populate `merge_sha: "<pre-schema-bootstrap>"` on every existing closed work-item. Exempt this sentinel from the static check's reachability test.

### Motivation

Strategy (a) is the disciplined version — it produces real, verifiable data. Strategy (b) is fast but leaves a known-incomplete sentinel in the data.

The risk with (a) is that it surfaces orphans that were closed against unmerged work. THIS IS A FEATURE, NOT A BUG — orphans are exactly what this whole epic exists to find. The migration script's `--report-orphans` mode produces the list; the user disposes each.

### Proposed Changes

Document the migration in a new §"Backfill for existing closed work-items" subsection. The actual migration script is impl work, tracked as a follow-up work-item filed AFTER this PC is accepted.

Recommendation: ship Strategy (a) as the default, with Strategy (b) as a `--grandfather` fallback flag for hostile-environment cases where the git history is genuinely unreachable.


## Acceptance criteria

This PC is complete when:

1. `AuditRecord` carries `merge_sha` (required when present) and `pr_number` (optional).
2. The widened "when is audit present" rule is documented.
3. `.livespec.jsonc`'s `livespec-impl-plaintext` block admits the `canonical_branch` key.
4. The `work_item_merge_evidence` static check is specified.
5. The migration strategy is documented (script implementation deferred to a follow-up work-item).
6. The implementation work — dataclass updates, schema-validation updates, check module, migration script — is tracked in follow-up work-items in `work-items.jsonl` once this PC is accepted.

This PC declares the SPEC; it does NOT itself ship impl. Per the livespec-impl-plaintext discipline, impl follows acceptance via TDD: a Red commit with failing tests, then a Green commit with implementation, then any Refactor commits.

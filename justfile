# justfile — livespec-orchestrator-git-jsonl dev-tooling task runner.
#
# Generated from livespec/templates/impl-plugin/justfile.jinja at
# copier-copy time; re-sync via `copier update --vcs-ref=master` when livespec
# publishes a new release.
#
# Authority: livespec/SPECIFICATION/non-functional-requirements.md
#   §"Enforcement-suite invocation" — `just` is the canonical entry
#   point for every dev-tooling invocation. Lefthook and CI MUST
#   delegate to `just <target>`; direct tool invocations are banned
#   (enforced by livespec_dev_tooling.checks.no_direct_tool_invocation).
#
# Authority: livespec/SPECIFICATION/contracts.md
#   §"Pre-commit step ordering" — the gates wired here mirror the
#   spec-required ordering: 00-lint-autofix-staged, 01-commit-pairs-
#   source-and-test, 02-check-pre-commit at pre-commit;
#   no-commit-on-master + red-green-replay at commit-msg; full
#   aggregate (with zero-py subsetting) at pre-push.
#
# Authority: livespec/SPECIFICATION/contracts.md
#   §"Shared code sync — livespec-dev-tooling" (v094 wiring-
#   completeness invariant) — every canonical slug emitted by
#   `livespec_dev_tooling.canonical_checks` MUST be wired in this
#   `check:` aggregate in alphabetical order; livespec-orchestrator-git-jsonl-
#   private extras MAY follow after the canonical block. The in-repo
#   gate `check-aggregate-completeness` enforces this on every run.

# `skip` — space-separated list of `check:` targets to omit from a single run.
# Default empty (full aggregate). Overridden on the command line by the Red-mode
# pre-commit hook (see check-pre-commit). When empty, the green token is written
# after a full green aggregate pass for the pre-push short-circuit.
skip := ""

# pytest-xdist worker count, lane-aware (plan/fabro-ci-image-factoring cont.5).
# GitHub-hosted CI (LIVESPEC_CI_LANE=hosted, set from CI_RUNNER_LABELS in
# ci.yml) uses all cores (-n auto — GH runners are small + dedicated). The
# self-hosted/local lane throttles to LIVESPEC_TEST_PARALLELISM, defaulting to
# 25% of cores (min 1) so a shared host is never oversubscribed. Tune per host
# by exporting LIVESPEC_TEST_PARALLELISM (a dedicated box can set it to `auto`
# or a high N); local dev may export it to speed a laptop run.
test_nprocs := if env_var_or_default("LIVESPEC_CI_LANE", "local") == "hosted" { "auto" } else { env_var_or_default("LIVESPEC_TEST_PARALLELISM", `c=$(nproc 2>/dev/null || echo 4); n=$(( c / 4 )); [ "$n" -ge 1 ] || n=1; echo "$n"`) }

# Default to listing targets when no recipe is invoked.
default:
    @just --list

# Golden-master acceptance harness. Kept outside `just check` so the
# fast aggregate remains the local/pre-push safety net while CI can
# expose this as a separate merge-gate status.
acceptance:
    uv run pytest acceptance -q

# ---------------------------------------------------------------
# Worktree-discipline recipes (the Worktree Discipline Pack).
#
# The four `just worktree-{create,hydrate,land,reap}` lifecycle recipes are
# SINGLE-SOURCED from the livespec-dev-tooling package's canonical
# `worktree.just` fragment, installed into `dev-tooling/worktree.just` by
# `just install-worktree-pack` (run from `bootstrap` and CI) and IMPORTED
# here — so this repo no longer copies the recipe text into its own justfile.
# The recipes are ecosystem-neutral one-line pass-throughs onto the portable,
# ecosystem-neutral worktree core (dev-tooling/worktree-lib.sh), which they
# call DIRECTLY. The CORE is the single source of truth for the lifecycle
# (create / hydrate / land / reap) and the primary-vs-linked detection; the
# recipes carry NO logic of their own — they only forward arguments. `just`
# and `lefthook` are mandated non-functionally across the fleet + adopters
# (the Conformance Pattern: Installer = a `just` recipe; commit gate wired via
# `lefthook → just check`); they never enter livespec core's public functional
# surface or the /livespec:* skills. Where this repo's ecosystem (python) has a
# native tool, expose it as a STRICT PASS-THROUGH wrapper onto these recipes —
# never an alternative runner: e.g. rust `cargo xtask worktree create` →
# `just worktree-create`; javascript package.json
# `"wt:create": "just worktree-create"`. Keeping the logic in the core — not
# in any wrapper — is what stops ecosystems from drifting; the drift workflow
# + `copier update` exist to catch any divergence.
#
# Hydration is the python-profile specialization in
# dev-tooling/worktree-hydrate.sh, which the core's `create`/`hydrate` verbs
# invoke automatically.
#
# OPTIONAL import (`import?`, NOT plain `import`): `dev-tooling/worktree.just`
# is gitignored + installed (written by `install-worktree-pack`, never
# tracked-committed), so it is ABSENT in a fresh clone until `just bootstrap`
# runs. A plain `import` of a missing file makes `just` fail to parse the
# ENTIRE justfile — which would brick `just bootstrap` on a fresh clone. The
# optional `import?` silently no-ops while the file is absent (the worktree-*
# recipes simply aren't available until `install-worktree-pack` materializes
# the fragment) and resolves once installed.
# ---------------------------------------------------------------

import? 'dev-tooling/worktree.just'

# ---------------------------------------------------------------
# Server-side worktree discipline: GitHub branch protection.
#
# The local commit-refuse hook (the structural canonical body installed at
# .git/hooks from the shared livespec-dev-tooling package) blocks commits on the
# primary checkout, but it is LOCALLY BYPASSABLE (`--no-verify`, or simply never
# installed). Branch protection is
# the server-enforced backstop: the default branch advances only via PR/merge;
# direct + force pushes are rejected by GitHub itself.
#
# The two `protect-default-branch` (INSTALLER) and `check-branch-protection`
# (VERIFIER / "tripwire") recipes are SINGLE-SOURCED from the livespec-dev-tooling
# package's canonical `branch-protection.just` fragment, installed into
# `dev-tooling/branch-protection.just` by `just install-worktree-pack` (run from
# `bootstrap` and CI) and IMPORTED here — so this repo no longer copies the recipe
# text into its own justfile. Both recipes are ecosystem-neutral one-line
# pass-throughs onto the portable, ecosystem-neutral dev-tooling/branch-protection.sh
# (the single source of truth) — `just` is the mandated runner and the recipes
# carry no logic of their own, exactly like the worktree-* recipes above.
#
# `protect-default-branch` (the INSTALLER) establishes baseline protection on a
# fresh repo (requires an admin-scoped gh token); it is idempotent and
# non-weakening — it leaves an existing, possibly richer, protection untouched
# unless FORCE=1. `check-branch-protection` (the VERIFIER / "tripwire") asserts
# protection is present and is fail-closed, but capability-aware: it SKIPs with
# a NAMED notice when it cannot read protection (no gh / no admin token /
# non-GitHub origin) so it never makes `just check` flaky, and honours the
# LIVESPEC_BRANCH_PROTECTION_CHECK severity lever (fail [default] | warn | skip).
# The authoritative bite belongs to the Fleet-time conformance/orchestrator
# tier, where an admin token exists.
#
# OPTIONAL import (`import?`, NOT plain `import`): `dev-tooling/branch-protection.just`
# is gitignored + installed (written by `install-worktree-pack`, never
# tracked-committed), so it is ABSENT in a fresh clone until `just bootstrap`
# runs. A plain `import` of a missing file makes `just` fail to parse the
# ENTIRE justfile — which would brick `just bootstrap` on a fresh clone. The
# optional `import?` silently no-ops while the file is absent (the
# protect-default-branch / check-branch-protection recipes simply aren't
# available until `install-worktree-pack` materializes the fragment) and
# resolves once installed.
# ---------------------------------------------------------------

import? 'dev-tooling/branch-protection.just'

# ---------------------------------------------------------------
# First-time setup.
# ---------------------------------------------------------------

# Install the canonical livespec commit-refuse hook by REUSING the shared
# livespec-dev-tooling installer module (the SINGLE source of the structural
# hook body; pinned in pyproject.toml). NOT a repo-vendored copy — the prior
# `cp dev-tooling/git-hook-wrapper.sh` x3 + chmod block is retired so there is
# exactly ZERO drift-prone hook-body copy in this repo. This is the Installer
# slot of the Worktree-discipline concern (the Conformance Pattern: Installer =
# a `just` recipe; commit gate wired via lefthook → just check) that `bootstrap`
# delegates to. The installed body refuses commits/pushes STRUCTURALLY: it
# exits 1 when `git rev-parse --git-dir` equals `git rev-parse --git-common-dir`
# (a real primary checkout; a secondary worktree's git-dir is
# `.git/worktrees/<name>` and so differs) UNLESS `git config
# livespec.sandboxExempt` is `true`. There is therefore NO arming step and so no
# fail-open window — the hook is armed the moment it is installed. At worktrees
# (and in declared-exempt Fabro sandboxes) the body delegates to mise-managed
# lefthook so the per-hook gates fire. The installer resolves the shared hooks
# dir via git-common-dir so the install lands correctly whether invoked from the
# primary checkout or a secondary worktree. Idempotent; worktree-safe.
install-commit-refuse-hooks:
    uv run python -m livespec_dev_tooling.install_commit_refuse_hooks

# Install the canonical worktree-discipline PACK (worktree-lib.sh +
# branch-protection.sh) by REUSING the shared livespec-dev-tooling installer
# module (the SINGLE source of both bodies; pinned in pyproject.toml). NOT a
# repo-vendored copy — the prior tracked `dev-tooling/worktree-lib.sh` +
# `dev-tooling/branch-protection.sh` copies are retired so there is exactly
# ZERO drift-prone pack copy in this repo. This is the Installer slot for the
# pack facet of the Worktree-discipline concern, mirroring
# `install-commit-refuse-hooks` exactly: `bootstrap` delegates to it, and CI
# runs it before the `check-primary-checkout-commit-refuse-hook-installed`
# verifier so the verifier VALIDATES the installed pack (byte-identical to the
# package source) rather than skipping it. The installer writes both scripts
# into `dev-tooling/` and sets the executable bit; the scripts are gitignored
# (installed, not tracked), exactly as the commit-refuse hooks are installed
# into the untracked `.git/hooks/` dir. Idempotent.
install-worktree-pack:
    uv run python -m livespec_dev_tooling.install_worktree_pack

# First-touch setup — a THIN delegator to the shipped LOCAL first-touch
# reconcile verb (`livespec_dev_tooling.fleet.local_reconcile`), the
# generalized successor to this recipe's former inline steps (livespec-zs22.8
# M5), PLUS the member-specific worktree-pack tail the verb does not cover.
# Reuse-first: NO copied logic — the verb walks the LOCAL obligation partition
# (`contract.LOCAL_OBLIGATION_ROWS`): mise trust/install, uv sync, the
# structural commit-refuse hooks (subsuming `lefthook install`), the advisory
# `refs/notes/*` refspec, the worktree-root mise-trust entry, the beads
# tenant-dir hardening, the beads-runtime detect-and-guide probes, and
# project-scoped Claude/Codex plugin registration via THIS repo's own
# `ensure-plugins` / `ensure-codex-plugins` recipes. The verb resolves the
# target checkout worktree-safely via `git rev-parse --git-common-dir`. The
# TAIL below installs the worktree-discipline pack (worktree-lib.sh +
# branch-protection.sh + the `.just` recipe fragments) and keeps the tracked
# worktree-hydrate.sh executable — neither is a verb obligation row, so both
# MUST survive the rewire. The verb's uv-sync row precedes the tail's `uv run`,
# so the venv is ready.
bootstrap:
    bash dev-tooling/just-bootstrap.sh

# The standard shared derive-from-settings wrapper: it reads the committed
# .claude/settings.json (extraKnownMarketplaces incl. ref, enabledPlugins)
# at runtime and issues the marketplace add / install / update commands for
# exactly what it finds. One source of truth — recipe-content drift is
# structurally impossible.
ensure-plugins:
    mise exec -- uv run --no-sync python -m livespec_dev_tooling.fleet.ensure_plugins

# Idempotent host-wide Codex plugin provisioning. Codex does not support
# project-scoped plugin enablement, so these registrations intentionally land in
# the user's default CODEX_HOME and are visible to every repo on the host. Codex
# is an optional dogfooding runtime; bootstrap skips this target when the CLI is
# absent but fails on real install errors when Codex is present.
ensure-codex-plugins:
    bash dev-tooling/just-ensure-codex-plugins.sh

# ---------------------------------------------------------------
# Aggregate check — canonical full-set stamped at copier-copy time.
#
# The `targets=(...)` array below is Jinja-rendered from the committed
# copier-template DATA file `canonical-slugs.yml`, which is a
# release-time projection of
# `livespec_dev_tooling.canonical_checks.canonical_check_slugs()` (the
# single source of truth) regenerated in livespec via
# `just stamp-canonical-slugs`. The block is Jinja-included from that
# data file and line-parsed below — import-free, so it renders
# correctly on BOTH the smoke-check flow AND the consumer
# `copier update` flow (copier clones the template to an ephemeral
# checkout with no PYTHONPATH injection, where a render-time copier
# jinja-extension importing the dev-tooling module cannot resolve).
# Per livespec/SPECIFICATION/contracts.md
# §"Shared code sync — livespec-dev-tooling" → Template gate, every
# newly-generated `livespec-impl-*` sibling inherits the full canonical
# aggregate from inception; existing siblings see canonical-set growth
# as a real reviewable diff on `copier update` (3-way merge surfaces
# canonical drift).
#
# The data file resolves at the Jinja loader root, which differs
# between the two flows (smoke-check flow: loader root is
# templates/impl-plugin/; consumer flow: loader root is the repo/clone
# root, with _subdirectory routing). A Jinja list-include tries
# "canonical-slugs.yml" then "templates/impl-plugin/canonical-slugs.yml"
# and uses the first that exists, so one physical data file serves both
# flows import-free.
#
# Slugs are stamped in alphabetical order (sorted at the source). DO
# NOT hand-edit this list — extend the canonical set by adding
# `livespec_dev_tooling/checks/<name>.py` in the dev-tooling sibling
# repo, re-run `just stamp-canonical-slugs` in livespec, cut a template
# release, then re-run `copier update --vcs-ref=master` here.
# ---------------------------------------------------------------

check-no-workflow-edits:
    bash dev-tooling/just-check-no-workflow-edits.sh

# Deliberately omit errexit so the aggregate reports every failing target before exiting non-zero.
check:
    #!/usr/bin/env bash
    set -uo pipefail
    : <<'LIVESPEC_AGGREGATE_TARGETS'
    targets=(
        check-agents-ai-references-resolve
        check-aggregate-completeness
        check-all-declared
        check-assert-never-exhaustiveness
        check-branch-protection-alignment
        check-canonical-recipe-fidelity
        check-check-coverage-incremental
        check-check-mutation
        check-check-tools
        check-ci-matrix-completeness
        check-claude-md-coverage
        check-comment-line-anchors
        check-commit-pairs-source-and-test
        check-file-lloc
        check-fleet-marketplace-relative-sources
        check-global-writes
        check-handoff-dispatch-routing
        check-heading-coverage
        check-hook-trees-not-io-exempt
        check-keyword-only-args
        check-local-memory-drift-audit
        check-main-guard
        check-master-ci-green
        check-match-keyword-only
        check-newtype-domain-primitives
        check-no-direct-destructive-cli
        check-no-direct-tool-invocation
        check-no-except-outside-io
        check-no-fmt-directives
        check-no-inheritance
        check-no-lloc-soft-warnings
        check-no-raise-outside-io
        check-no-shadow-ledger-body-identical
        check-no-shadow-ledger-body-typechecks
        check-no-todo-registry
        check-no-write-direct
        check-partition-completeness
        check-pbt-coverage-pure-modules
        check-per-file-coverage
        check-plan-anchor-declared
        check-plan-epic-parity
        check-plan-no-tombstone
        check-plugin-resolution
        check-primary-checkout-commit-refuse-hook-installed
        check-private-calls
        check-public-api-result-typed
        check-red-green-replay
        check-required-role-keys-declared
        check-rop-pipeline-shape
        check-self-hosted-routing
        check-self-hosted-uv-lane
        check-shell-quality
        check-skill-invocation-paths
        check-source-trees-scoped-to-consumer
        check-supervisor-discipline
        check-tests-mirror-pairing
        check-tests-no-subprocess-spawn
        check-tool-backed-check-completeness
        check-vendor-manifest
        check-wrapper-shape
        check-format
        check-lint
        check-types
        check-coverage
        check-no-divergent-heads
        check-no-raw-store-read
        check-spec-governance-default-block
        check-work-item-merge-evidence
        check-doctor-static
    )
    LIVESPEC_AGGREGATE_TARGETS
    bash dev-tooling/just-check.sh

[positional-arguments]
check-skipping *skip_targets:
    bash dev-tooling/just-check.sh "$@"

# ---------------------------------------------------------------
# Tool-backed checks (livespec-orchestrator-git-jsonl-private).
# ---------------------------------------------------------------

check-lint:
    uv run ruff check .

check-format:
    uv run ruff format --check .

check-types:
    uv run pyright

# Aggregate (total) coverage gate at `fail_under = 100` (pyproject.toml
# [tool.coverage.report]). Wired as a LITERAL member of the `check:`
# targets array (private block) AND the CI check-python matrix; the
# check-tool-backed-check-completeness meta-check (dev-tooling v0.8.0)
# enforces that both-surfaces wiring. To avoid a DUPLICATE full pytest
# run when invoked inside `just check`, this recipe gates off the
# EXISTING `.coverage` data file when present — the canonical
# check-per-file-coverage slug runs `pytest --cov` upfront and sorts
# alphabetically BEFORE this private extra, so `.coverage` already
# exists by the time this runs locally. When `.coverage` is ABSENT —
# the CI check-python matrix runs check-coverage as a standalone job in
# its own runner with no prior pytest — the recipe runs the suite
# itself so the aggregate gate still fires there. In Red-mode pre-commit
# this target is omitted by `check-pre-commit` via the `just skip=...`
# argument (coverage is verified at the Green amend), so no ambient
# env-var read is needed here (epic li-cvaudit, cvredmd). Mirrors
# dev-tooling's coverage-reuse recipe.
check-coverage:
    bash dev-tooling/just-check-coverage.sh

# ---------------------------------------------------------------
# Orchestrator-private store-integrity checks (livespec-impl-git-
# jsonl-private; v008 SPECIFICATION/contracts.md "Append-only store
# disciplines"). Both consume the canonical reducer / query surface
# in livespec_orchestrator_git_jsonl.store — never a private re-derivation
# of "latest wins" (the one-canonical-reducer obligation).
# ---------------------------------------------------------------

# Fails when any entity id in the declared backing store (work-items)
# resolves to more than one un-superseded head, naming the offending
# entity id and the conflicting record identities. An absent store
# file is skipped; a malformed/schema-violating store fails.
check-no-divergent-heads:
    uv run python3 .claude-plugin/scripts/bin/check_no_divergent_heads.py

# Fails when shipped code (committed .py under .claude-plugin/scripts/
# and dev-tooling/, _vendor/ excluded) opens a declared backing store
# path directly, bypassing the reducer/query surface. The canonical
# store module is the one exemption. Scope is committed code only —
# ad-hoc interactive shell reads are defended by the record
# self-identification + order-independent-reduction obligations.
check-no-raw-store-read:
    uv run python3 .claude-plugin/scripts/bin/check_no_raw_store_read.py

check-spec-governance-default-block:
    uv run python dev-tooling/check_spec_governance_default_block.py

# Plugin-private merge-evidence static check (li-tenpup;
# SPECIFICATION/contracts.md "Work-items JSONL record schema" ->
# "work_item_merge_evidence static check"). Walks the materialized
# work-items view: closed work-items with merge-implying resolutions
# (completed, spec-revised, resolved-out-of-band) must carry an audit
# merge_sha that exists locally and is reachable from
# origin/<canonical_branch> (local git cat-file/merge-base only —
# network-free); administratively closed items must NOT carry
# merge-evidence; closed epics instead require every local depends_on
# child closed. The backfill grandfather sentinel is exempt from the
# reachability test. An absent store file is a pass (noted, skipped).
check-work-item-merge-evidence:
    uv run python3 .claude-plugin/scripts/bin/check_work_item_merge_evidence.py

# livespec core's doctor STATIC phase (reference-discipline + out-of-band
# invariants) against THIS repo's SPECIFICATION/ tree, wired fleet-wide per
# livespec epic livespec-6jfq. core ships the checker: doctor_static.py is
# self-contained (vendored deps + bare python3), so it runs under plain
# python3 and NEVER `uv run`. Resolve core's plugin root via
# LIVESPEC_CORE_PLUGIN_ROOT (CI sets it to a livespec checkout at this repo's
# .livespec.jsonc compat.pinned tag) → else the installed livespec@livespec
# plugin cache (local dev). The two reference-discipline checks
# (no-cross-spec-reference, no-spec-section-citation-in-code) are pure reads;
# doctor-out-of-band-edits is self-healing — on a drifted tree it writes a
# history backfill into the worktree and fails, and committing that backfill
# heals the track; on a clean tree it never fires.
check-doctor-static:
    bash dev-tooling/just-check-doctor-static.sh

# ---------------------------------------------------------------
# Canonical structural checks (shared from livespec-dev-tooling).
# Wired in alphabetical order to match the aggregate above.
# ---------------------------------------------------------------

# AGENTS.md `.ai/<topic>.md` reference-resolution static check
# (livespec core §"Fleet agent-instruction core"): every `.ai/`
# reference in AGENTS.md must resolve to an existing file. Canonical
# since livespec-dev-tooling v0.21; wired here at the v0.21.2 bump.
check-agents-ai-references-resolve:
    uv run python -m livespec_dev_tooling.checks.agents_ai_references_resolve

# In-repo gate for the wiring-completeness invariant
# (SPECIFICATION/contracts.md v094 §"Shared code sync —
# livespec-dev-tooling"). Parses the local `justfile`'s `check:`
# recipe and verifies every canonical slug emitted by
# `livespec_dev_tooling.canonical_checks` is wired in alphabetical
# order, with private extras appearing only after the canonical
# block. Self-bootstrapping: the slug `check-aggregate-completeness`
# is itself canonical, so dropping it would fail this check on the
# next run.
check-aggregate-completeness:
    uv run python -m livespec_dev_tooling.checks.aggregate_completeness

check-all-declared:
    uv run python -m livespec_dev_tooling.checks.all_declared

check-assert-never-exhaustiveness:
    uv run python -m livespec_dev_tooling.checks.assert_never_exhaustiveness

# Layer 1 mechanical check: shells out to `gh api` to read remote
# GitHub state; exits 0 with a structured warning when `gh` is
# unavailable or unauthenticated locally so per-commit pre-commit
# runs are not blocked. CI with GH_TOKEN exercises the full
# enforcement path.
check-branch-protection-alignment:
    uv run python -m livespec_dev_tooling.checks.branch_protection_alignment

# Path-scoped fast-feedback variant of check-coverage. With explicit
# `--paths <impl_path> [<impl_path>...]` (repo-root-relative) it scopes
# the per-file 100% gate to those paths. With NO args (the canonical
# aggregate / `just check` invocation) the check DERIVES the changed
# impl-`.py` set from `git diff --name-only origin/master...HEAD` and
# gates those — no longer a no-op (epic li-cvaudit, cvnoarg). The
# interactive developer use case still passes `--paths` explicitly:
# `just check-check-coverage-incremental --paths .claude-plugin/scripts/bin/foo.py`.
[positional-arguments]
check-check-coverage-incremental *args:
    uv run python -m livespec_dev_tooling.checks.check_coverage_incremental "$@"

# `check-static` — fastest-first fail-fast helper for fast agent/dev
# feedback (work-item livespec-dev-tooling-7us.8). Runs ONLY the cheap
# static checks — `ruff format --check .`, `ruff check .`, `pyright`
# (i.e. check-format, check-lint, check-types) — as a fail-fast
# sequence: it STOPS at the first failing check and exits non-zero, so
# a sub-2s ruff/pyright failure surfaces immediately instead of after
# `just check`'s slow pytest+coverage tail. This is a developer/agent
# convenience like the helper recipes above; it is deliberately NOT a
# member of the `check:` aggregate `targets=(...)` array, NOT a
# canonical slug (no livespec_dev_tooling/checks/ module), and NOT in
# the CI matrix. The authoritative full gate remains `just check`
# (still run at pre-push and in CI) — `check-static` is a fast
# pre-flight, never a replacement for it.
check-static:
    bash dev-tooling/just-check-static.sh

# `changed-files` — print the changed `.py` set this branch touches,
# repo-root-relative, one path per line, sorted + de-duplicated
# (work-item livespec-dev-tooling-7us.9). The set is the UNION of two
# git views, so an agent gets the live working set whether or not it has
# committed yet:
#   - `git diff --name-only origin/master...HEAD` — every `.py` this
#     branch's commits changed vs the merge-base with origin/master;
#   - `git diff --cached --name-only --diff-filter=AM` — added/modified
#     `.py` currently staged but not yet committed.
# This is the exact set `check-changed` consumes for its scoped gate.
# Helper recipe (like `check-static`): NOT a member of the `check:`
# aggregate `targets=(...)` array, NOT a canonical slug, NOT in the CI
# matrix.
changed-files:
    bash dev-tooling/just-changed-files.sh

# `check-changed` — modified-files INNER-LOOP gate for fast scoped
# feedback during iteration (work-item livespec-dev-tooling-7us.9). Feeds
# the `changed-files` set into `check-check-coverage-incremental --paths
# <set>`, which already (a) resolves each changed impl `.py` to its
# mirror-paired test and runs that pytest SUBSET, and (b) applies the
# path-scoped per-file coverage gate — i.e. it composes the existing
# scoping plumbing rather than re-deriving it. An empty changed set is a
# no-op (exit 0): nothing changed, nothing to gate.
#
# SCOPE — INNER-LOOP SPEEDUP ONLY, NOT a replacement for the final gate.
# It runs only the test subset + path-scopable checks for the files this
# branch touched, so an agent gets sub-suite feedback while iterating. The
# AUTHORITATIVE gate remains `just check`, which runs the FULL suite + the
# full AST scans + the aggregate 100% coverage gate at pre-push and in CI.
# Like `check-static`, this is a developer/agent convenience: NOT a member
# of the `check:` aggregate `targets=(...)` array, NOT a canonical slug,
# and NOT in the CI matrix.
check-changed:
    bash dev-tooling/just-check-changed.sh

# Always invoked plainly; the module self-manages its RUN/SKIP lever
# (epic li-cvaudit, cvtodo). `LIVESPEC_RUN_MUTATION` unset → the check
# logs "skipped" and exits 0; set to a non-empty value (CI sets it to
# `true`) → the mutmut suite runs. No external gate, no silent skip.
check-check-mutation:
    uv run python -m livespec_dev_tooling.checks.check_mutation

check-check-tools:
    uv run python -m livespec_dev_tooling.checks.check_tools

check-claude-md-coverage:
    uv run python -m livespec_dev_tooling.checks.claude_md_coverage

check-comment-line-anchors:
    uv run python -m livespec_dev_tooling.checks.comment_line_anchors

# Commit-pair gate: every commit touching source files also touches
# tests. Lefthook pre-commit only is the load-bearing per-commit
# invocation; wired into the aggregate per the wiring-completeness
# invariant.
check-commit-pairs-source-and-test:
    uv run python -m livespec_dev_tooling.checks.commit_pairs_source_and_test

check-file-lloc:
    uv run python -m livespec_dev_tooling.checks.file_lloc

# Fleet marketplace ref-pin guard: catalog plugin sources MUST stay
# checkout-relative (`./...` strings, or the Codex catalog's
# `{"source": "local", "path": "./..."}` object form). Github-type or
# other non-relative sources silently ignore the registered
# marketplace ref pin and clone default HEAD instead.
check-fleet-marketplace-relative-sources:
    uv run python -m livespec_dev_tooling.checks.fleet_marketplace_relative_sources

check-global-writes:
    uv run python -m livespec_dev_tooling.checks.global_writes

check-heading-coverage:
    uv run python -m livespec_dev_tooling.checks.heading_coverage

check-keyword-only-args:
    uv run python -m livespec_dev_tooling.checks.keyword_only_args

check-main-guard:
    uv run python -m livespec_dev_tooling.checks.main_guard

# Layer 1 mechanical check: shells out to `gh api` to read remote
# GitHub state; exits 0 with a structured warning when `gh` is
# unavailable or unauthenticated locally so per-commit pre-commit
# runs are not blocked. CI with GH_TOKEN exercises the full
# enforcement path.
check-master-ci-green:
    uv run python -m livespec_dev_tooling.checks.master_ci_green

check-match-keyword-only:
    uv run python -m livespec_dev_tooling.checks.match_keyword_only

check-newtype-domain-primitives:
    uv run python -m livespec_dev_tooling.checks.newtype_domain_primitives

# Destructive-default CLI wrapping gate (livespec/SPECIFICATION/
# non-functional-requirements.md §"Destructive-default CLI wrapping"):
# greps the agent-facing trees (dev-tooling/, .claude-plugin/,
# .claude/plugins/) for direct invocations of known-destructive-default
# CLIs (bd init, git push --force/-f, git reset --hard, gh repo delete)
# outside the explicit `[tool.livespec_dev_tooling].
# destructive_cli_allowlist` path-prefix allowlist.
check-no-direct-destructive-cli:
    uv run python -m livespec_dev_tooling.checks.no_direct_destructive_cli

check-no-direct-tool-invocation:
    uv run python -m livespec_dev_tooling.checks.no_direct_tool_invocation

check-no-except-outside-io:
    uv run python -m livespec_dev_tooling.checks.no_except_outside_io

check-no-inheritance:
    uv run python -m livespec_dev_tooling.checks.no_inheritance

# Always invoked plainly; the module self-manages its severity lever
# (epic li-cvaudit, cvtodo). The 201-250 LLOC soft-band scan ALWAYS
# runs; `LIVESPEC_FAIL_IF_LLOC_SOFT_WARNINGS_EXIST` unset → soft-band
# offenders warn + exit 0; set (CI sets it to `true`) → they fail.
check-no-lloc-soft-warnings:
    uv run python -m livespec_dev_tooling.checks.no_lloc_soft_warnings

check-no-raise-outside-io:
    uv run python -m livespec_dev_tooling.checks.no_raise_outside_io

# Always invoked plainly; the module self-manages its severity lever
# (epic li-cvaudit, cvtodo). The heading-coverage.json TODO scan ALWAYS
# runs; `LIVESPEC_FAIL_IF_HEADING_COVERAGE_TODOS_EXIST` unset → TODO
# offenders warn + exit 0 (authoring placeholders surface without
# blocking per-commit `just check`); set (CI sets it to `true`) → they
# fail. Replaces the prior LIVESPEC_RELEASE_GATE skip carve-out, which
# silently skipped the scan entirely when the gate was unset.
check-no-todo-registry:
    uv run python -m livespec_dev_tooling.checks.no_todo_registry

check-no-write-direct:
    uv run python -m livespec_dev_tooling.checks.no_write_direct

check-pbt-coverage-pure-modules:
    uv run python -m livespec_dev_tooling.checks.pbt_coverage_pure_modules

# Deliberately omit errexit; pytest fail-closes before the canonical shared module reads coverage.
check-per-file-coverage:
    #!/usr/bin/env bash
    set -uo pipefail
    # Clean-env producer (livespec-dev-tooling-yilyxr.8, dev-tooling PR #1462
    # design): COVERAGE_FILE unset so the repo-root .coverage exists for
    # check-coverage's consume-once reuse even under the dispatcher's
    # namespaced export, and measures identically to a clean CI job.
    env -u COVERAGE_FILE uv run pytest -n "$(bash dev-tooling/just-test-nprocs.sh)" --cov --cov-branch --cov-config=pyproject.toml --cov-report=term-missing || exit $?
    env -u COVERAGE_FILE uv run python -m livespec_dev_tooling.checks.per_file_coverage

# Shared baseline plugin-resolution Verifier (Conformance-Pattern,
# livespec-zs22.7.7 M6). The check is shipped by livespec-dev-tooling;
# this recipe is the project-root-scoped CI/just-check adoption.
check-plugin-resolution:
    uv run python -m livespec_dev_tooling.checks.plugin_resolution

# Family-wide commit-refuse hook invariant per livespec/SPECIFICATION/
# non-functional-requirements.md §"Primary-checkout commit-refuse hook"
# (v095). Supersedes the v091-v094 bare-flag mechanism, which caused
# stale-on-disk-read failures at primaries. The check is shipped by
# livespec-dev-tooling (>=v0.5.0); this recipe is the project-root-
# scoped CI/just-check adoption that the spec mandates for every
# consumer repo.
check-primary-checkout-commit-refuse-hook-installed:
    uv run python -m livespec_dev_tooling.checks.primary_checkout_commit_refuse_hook_installed

check-private-calls:
    uv run python -m livespec_dev_tooling.checks.private_calls

check-public-api-result-typed:
    uv run python -m livespec_dev_tooling.checks.public_api_result_typed

# Trailer-based Red→Green replay verification (hard gate). Invoked by
# lefthook commit-msg stage with the commit-message file path as argv[1]
# (the load-bearing per-commit verifier). The canonical aggregate /
# `just check` invokes this with NO msg_path; the module then DERIVES
# the message from `git log -1 --format=%B` (HEAD) and validates it —
# no longer a no-op (epic li-cvaudit, cvnoarg).
[positional-arguments]
check-red-green-replay *args:
    uv run python -m livespec_dev_tooling.checks.red_green_replay "$@"

check-rop-pipeline-shape:
    uv run python -m livespec_dev_tooling.checks.rop_pipeline_shape

check-skill-invocation-paths:
    uv run python -m livespec_dev_tooling.checks.skill_invocation_paths

check-supervisor-discipline:
    uv run python -m livespec_dev_tooling.checks.supervisor_discipline

check-tests-mirror-pairing:
    uv run python -m livespec_dev_tooling.checks.tests_mirror_pairing

# Forbid test-spawned Python subprocesses (`subprocess.run([sys.executable, ...])`)
# in tests/ — they self-instrument under `pytest --cov` and race concurrent
# coverage runs; prefer the in-process `main()` pattern. Canonical check added
# in livespec-dev-tooling v0.14.1 (4i5). In `just check` aggregate.
check-tests-no-subprocess-spawn:
    uv run python -m livespec_dev_tooling.checks.tests_no_subprocess_spawn

# Tool-backed-check completeness meta-check (epic li-pyright-gate,
# work-item li-pyright-gate-wi3; shared from livespec-dev-tooling
# v0.8.0). Asserts each tool-backed check (check-lint / check-format /
# check-types / check-coverage) is a LITERAL member of BOTH this
# justfile's `check:` targets=(...) array AND the CI check-python
# matrix. Self-passes because the targets array (private block) + CI
# matrix wire all four literally.
check-tool-backed-check-completeness:
    uv run python -m livespec_dev_tooling.checks.tool_backed_check_completeness

check-vendor-manifest:
    uv run python -m livespec_dev_tooling.checks.vendor_manifest

check-wrapper-shape:
    uv run python -m livespec_dev_tooling.checks.wrapper_shape

# ---------------------------------------------------------------
# CLI end-to-end harness (top-of-pyramid, user-surface tier).
# ---------------------------------------------------------------

# Run the CLI end-to-end harness against this plugin's own per-skill
# fixtures (per livespec/SPECIFICATION/contracts.md §"CLI end-to-end
# harness contract"). The harness ships from livespec-dev-tooling
# (v0.8.0) and is consumed via the imported test_workflow_full_round_
# trip entry point wired in tests/e2e-cli/. Defaults to the MOCK tier
# (LIVESPEC_E2E_HARNESS=mock — the one mocked boundary is the
# `claude -p` subprocess; real install-shape setup, real structural
# skill discovery, the real fail-closed time-bomb coverage gate, and
# the real per-skill orchestration loop all run). The fail-closed
# coverage gate raises CoverageGateError when a `/livespec-impl-
# git-jsonl:*` skill lacks a fixture, failing this target. The CI
# `e2e-cli` job delegates here (no direct tool invocation in the
# workflow). The mock-tier test ALSO runs as part of the normal suite
# under check-per-file-coverage; this target is the dedicated,
# explicitly-named tier entry point CI reports as its own status.
check-e2e-cli:
    uv run pytest tests/e2e-cli -v

# ---------------------------------------------------------------
# Pre-commit aggregate — Red-mode-aware. Classifies the staged
# tree shape; in Red mode it passes `skip="check-coverage
# check-per-file-coverage"` to `just check` so the coverage gates
# are omitted (the commit-msg replay hook is the verifier; coverage
# is checked at the Green amend). This is a self-contained recipe
# argument — there is NO ambient env var (epic li-cvaudit, cvredmd).
# Pre-push and CI keep invoking `just check` directly.
# ---------------------------------------------------------------

check-pre-commit:
    bash dev-tooling/just-check-pre-commit.sh

# When zero `.py` files are staged, `check-pre-commit` delegates here.
# Pre-push delegates here via `check-pre-push` for zero-py changesets.
# check-claude-md-coverage and check-heading-coverage are intentionally
# absent here: backlog work-items li-bb5suo (CLAUDE.md backfill) and
# li-4liaxt (heading-coverage backfill) close the gap; until those land
# they would force every doc-only commit to fail the pre-commit gate.
# They remain wired in the full `just check` aggregate (and surface in
# pre-push) as the load-bearing canonical contract.
check-pre-commit-doc-only:
    bash dev-tooling/just-check-pre-commit-doc-only.sh

# Skip the Python-code check subset when the pushed commits contain
# zero `.py` changes; those checks are deterministic functions of
# the source tree and would pass-or-fail identically against the
# merge-base. Falls back to `origin/master` when no upstream branch
# is configured locally.
check-pre-push:
    bash dev-tooling/just-check-pre-push.sh

# ---------------------------------------------------------------
# Pre-commit auxiliary gates.
# ---------------------------------------------------------------

# Ruff fix + format on staged .py files BEFORE the rest of the
# pre-commit gate runs. Non-blocking — unfixable issues fall through
# to check-lint / check-format inside `just check` later. Re-stages
# post-autofix bytes.
lint-autofix-staged:
    bash dev-tooling/just-lint-autofix-staged.sh

# ---------------------------------------------------------------
# Mutating targets (opt-in; not run in CI).
# ---------------------------------------------------------------

fmt:
    uv run ruff format .

lint-fix:
    uv run ruff check --fix .

# Re-vendor an upstream-sourced library into .claude-plugin/scripts/_vendor/
# from the upstream ref recorded in .vendor.jsonc (the only blessed
# mutation path per livespec/SPECIFICATION/constraints.md §"Vendoring
# procedure"). Maintainer-only; NOT run in CI. The family's
# release->bump-pin automation invokes this so cross-repo auto-bump can
# re-vendor. Shim entries (shim: true) are NOT re-vendored.
[positional-arguments]
vendor-update lib:
    uv run python -m livespec_dev_tooling.vendor_update "$1"

# ---------------------------------------------------------------
# One-shot migration utilities.
# ---------------------------------------------------------------

# Translate a beads .beads/issues.jsonl export into work-items.jsonl
# records. One-shot — re-running on the same input produces duplicates.
# Use during the Phase D.10 cutover only.
[positional-arguments]
migrate-beads beads_jsonl out_jsonl:
    bash dev-tooling/just-migrate-beads.sh "$1" "$2"

check-partition-completeness:
    uv run python -m livespec_dev_tooling.checks.partition_completeness

check-canonical-recipe-fidelity:
    uv run python -m livespec_dev_tooling.checks.canonical_recipe_fidelity

check-ci-matrix-completeness:
    uv run python -m livespec_dev_tooling.checks.ci_matrix_completeness

check-no-fmt-directives:
    uv run python -m livespec_dev_tooling.checks.no_fmt_directives

check-no-shadow-ledger-body-identical:
    uv run python -m livespec_dev_tooling.checks.no_shadow_ledger_body_identical

check-local-memory-drift-audit:
    uv run python -m livespec_dev_tooling.checks.local_memory_drift_audit

check-handoff-dispatch-routing:
    uv run python -m livespec_dev_tooling.checks.handoff_dispatch_routing

check-self-hosted-routing:
    uv run python -m livespec_dev_tooling.checks.self_hosted_routing

check-source-trees-scoped-to-consumer:
    uv run python -m livespec_dev_tooling.checks.source_trees_scoped_to_consumer

check-no-shadow-ledger-body-typechecks:
    uv run python -m livespec_dev_tooling.checks.no_shadow_ledger_body_typechecks

check-required-role-keys-declared:
    uv run python -m livespec_dev_tooling.checks.required_role_keys_declared

check-hook-trees-not-io-exempt:
    uv run python -m livespec_dev_tooling.checks.hook_trees_not_io_exempt

check-shell-quality:
    uv run python -m livespec_dev_tooling.checks.shell_quality

check-plan-anchor-declared:
    uv run python -m livespec_dev_tooling.checks.plan_anchor_declared

check-plan-thread-anchor-declared:
    just check-plan-anchor-declared

check-plan-epic-parity:
    uv run python -m livespec_dev_tooling.checks.plan_epic_parity

check-plan-thread-epic-parity:
    just check-plan-epic-parity

check-plan-no-tombstone:
    uv run python -m livespec_dev_tooling.checks.plan_no_tombstone

check-self-hosted-uv-lane:
    uv run python -m livespec_dev_tooling.checks.self_hosted_uv_lane

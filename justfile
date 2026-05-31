# justfile — livespec-impl-plaintext dev-tooling task runner.
#
# Generated from livespec/templates/impl-plugin/justfile.jinja at
# copier-copy time; re-sync via `copier update` when livespec
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
#   `check:` aggregate in alphabetical order; livespec-impl-plaintext-
#   private extras MAY follow after the canonical block. The in-repo
#   gate `check-aggregate-completeness` enforces this on every run.

# Default to listing targets when no recipe is invoked.
default:
    @just --list

# ---------------------------------------------------------------
# First-time setup.
# ---------------------------------------------------------------

bootstrap:
    # Idempotent `livespec.primaryPath` on the primary checkout's
    # git-common-dir config (per livespec/SPECIFICATION/
    # non-functional-requirements.md §"Primary-checkout commit-refuse
    # hook" / §"Commit-refuse hook bootstrap procedure" — family-wide
    # invariant inherited by every livespec-impl-* sibling). The
    # commit-refuse hook reads this config value to recognize the
    # primary checkout and refuse commits/pushes there, forcing every
    # edit through `git worktree add`. Targets the absolute path of
    # the git common dir's parent so the recipe writes the right
    # value when invoked from the primary checkout AND from secondary
    # worktrees.
    git config --file "$(git rev-parse --git-common-dir)/config" livespec.primaryPath "$(realpath "$(dirname "$(git rev-parse --git-common-dir)")")"
    # Install the commit-refuse hook (vendored from livespec-dev-
    # tooling v0.5.0 — see dev-tooling/livespec-commit-refuse-hook.sh)
    # at pre-commit AND pre-push. Refuses at the primary checkout;
    # delegates to lefthook at secondary worktrees via mise. The
    # commit-msg path keeps the legacy git-hook-wrapper since it
    # routes argv[1] to the v034 D3 replay-hook stage.
    mkdir -p .git/hooks
    cp dev-tooling/livespec-commit-refuse-hook.sh .git/hooks/pre-commit
    cp dev-tooling/livespec-commit-refuse-hook.sh .git/hooks/pre-push
    cp dev-tooling/git-hook-wrapper.sh .git/hooks/commit-msg
    chmod +x .git/hooks/pre-commit .git/hooks/pre-push .git/hooks/commit-msg
    just ensure-plugins

# Idempotent: `claude plugin marketplace add` and `claude plugin install`
# both exit 0 when the target is already present.
ensure-plugins:
    claude plugin marketplace add thewoolleyman/livespec
    claude plugin marketplace add thewoolleyman/livespec-impl-plaintext
    claude plugin install livespec@livespec
    claude plugin install livespec-impl-plaintext@livespec-impl-plaintext

# ---------------------------------------------------------------
# Aggregate check — runs every check below sequentially. Continues
# on failure (matches CI fail-fast: false behavior); exits non-zero
# if any target failed and prints the failure list.
# ---------------------------------------------------------------

check:
    #!/usr/bin/env bash
    set -uo pipefail
    # Canonical-check aggregate, per SPECIFICATION/contracts.md
    # §"Wiring-completeness invariant" (v094): every canonical slug
    # emitted by `livespec_dev_tooling.canonical_checks` MUST appear
    # here in alphabetical order; livespec-impl-plaintext-private
    # checks MAY follow after the canonical block in any order. The
    # in-repo gate is `check-aggregate-completeness`, which fails if
    # any canonical slug is missing or out-of-order.
    #
    # Aggregator continues on failure (matches CI fail-fast: false)
    # and exits non-zero with the failure list if any target failed.
    targets=(
        # ---- Canonical block (37 slugs, alphabetical) ----
        check-aggregate-completeness
        check-all-declared
        check-assert-never-exhaustiveness
        check-branch-protection-alignment
        check-check-coverage-incremental
        check-check-mutation
        check-check-tools
        check-claude-md-coverage
        check-comment-line-anchors
        check-commit-pairs-source-and-test
        check-file-lloc
        check-global-writes
        check-heading-coverage
        check-keyword-only-args
        check-main-guard
        check-master-ci-green
        check-match-keyword-only
        check-newtype-domain-primitives
        check-no-direct-tool-invocation
        check-no-except-outside-io
        check-no-inheritance
        check-no-lloc-soft-warnings
        check-no-raise-outside-io
        check-no-stale-revise-branches
        check-no-todo-registry
        check-no-write-direct
        check-pbt-coverage-pure-modules
        check-per-file-coverage
        check-primary-checkout-commit-refuse-hook-installed
        check-private-calls
        check-public-api-result-typed
        check-red-green-replay
        check-rop-pipeline-shape
        check-skill-invocation-paths
        check-supervisor-discipline
        check-tests-mirror-pairing
        check-tool-backed-check-completeness
        check-vendor-manifest
        check-wrapper-shape
        # ---- livespec-impl-plaintext-private block ----
        # Tool-backed checks (ruff lint, ruff format, pyright types,
        # aggregate coverage) — helper recipes, NOT canonical slugs
        # (not under livespec_dev_tooling/checks/), so check-aggregate-
        # completeness does not enforce them. They are wired here as
        # LITERAL members so the local `just check` aggregate gives full
        # lint / format / types / coverage feedback and matches the CI
        # check-python matrix; the check-tool-backed-check-completeness
        # meta-check (canonical block above, dev-tooling v0.8.0)
        # enforces that both-surfaces wiring (epic li-pyright-gate,
        # work-item li-pyright-gate-wi3, LITERAL-membership design).
        # check-coverage gates the aggregate `fail_under = 100` off the
        # SINGLE pytest run that the canonical check-per-file-coverage
        # already performed (it reads the existing `.coverage`), so
        # wiring it here adds NO duplicate suite run.
        check-format
        check-lint
        check-types
        check-coverage
    )
    failed=()
    for t in "${targets[@]}"; do
        printf '\n::: just %s\n' "$t"
        if ! just "$t"; then
            failed+=("$t")
        fi
    done
    if [[ ${#failed[@]} -gt 0 ]]; then
        printf '\nFailed targets (%d):\n' "${#failed[@]}"
        printf '  - %s\n' "${failed[@]}"
        exit 1
    fi
    printf '\nAll %d targets passed.\n' "${#targets[@]}"

# ---------------------------------------------------------------
# Tool-backed checks (livespec-impl-plaintext-private).
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
# itself so the aggregate gate still fires there. The Red-mode skip is
# preserved (commit-msg replay hook is the verifier; aggregate-time
# coverage is not load-bearing in Red mode). Mirrors dev-tooling's
# coverage-reuse recipe.
check-coverage:
    #!/usr/bin/env bash
    set -uo pipefail
    if [[ -n "${LIVESPEC_PRECOMMIT_RED_MODE:-}" ]]; then
        echo ":: check-coverage skipped (Red-mode pre-commit; verified at Green amend)"
        exit 0
    fi
    if [[ -f .coverage ]]; then
        echo ":: check-coverage: reading existing .coverage (produced by check-per-file-coverage); no duplicate suite run"
        uv run coverage report --fail-under=100
    else
        echo ":: check-coverage: no .coverage data file (CI standalone job); running the suite"
        uv run pytest -n auto --cov --cov-branch --cov-config=pyproject.toml --cov-report=term-missing
    fi

# ---------------------------------------------------------------
# Canonical structural checks (shared from livespec-dev-tooling).
# Wired in alphabetical order to match the aggregate above.
# ---------------------------------------------------------------

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

# Canonical-slug alias for the path-scoped incremental coverage
# check. The canonical slug derived from the module name
# `check_coverage_incremental.py` is `check-check-coverage-
# incremental`. Wired into the canonical aggregate (per the
# wiring-completeness invariant, SPECIFICATION/contracts.md v094)
# but short-circuits when called with no args — the full-tree
# per-file 100% gate is enforced by check-per-file-coverage.
check-check-coverage-incremental *args:
    #!/usr/bin/env bash
    set -uo pipefail
    if [[ -z "{{args}}" ]]; then
        echo ":: check-check-coverage-incremental skipped (no --paths provided; aggregate-mode no-op)"
        echo ":: full-tree per-file 100% gate is enforced by check-per-file-coverage"
        exit 0
    fi
    uv run python -m livespec_dev_tooling.checks.check_coverage_incremental {{args}}

# Release-gate ONLY — paired with check-no-todo-registry and
# check-no-lloc-soft-warnings on the release-tag CI workflow. Gated
# by LIVESPEC_RELEASE_GATE so the canonical aggregate can wire the
# slug (per SPECIFICATION/contracts.md §"Shared code sync —
# livespec-dev-tooling" wiring-completeness) without making per-
# commit `just check` runs choke on the multi-minute mutation
# suite. The release-tag workflow MUST set LIVESPEC_RELEASE_GATE=1
# before invoking this target.
check-check-mutation:
    #!/usr/bin/env bash
    set -uo pipefail
    if [[ -z "${LIVESPEC_RELEASE_GATE:-}" ]]; then
        echo ":: check-check-mutation skipped (LIVESPEC_RELEASE_GATE unset; release-gate-only check)"
        exit 0
    fi
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

check-no-direct-tool-invocation:
    uv run python -m livespec_dev_tooling.checks.no_direct_tool_invocation

check-no-except-outside-io:
    uv run python -m livespec_dev_tooling.checks.no_except_outside_io

check-no-inheritance:
    uv run python -m livespec_dev_tooling.checks.no_inheritance

# Release-gate ONLY — paired with check-check-mutation and check-
# no-todo-registry on the release-tag CI workflow. Gated by
# LIVESPEC_RELEASE_GATE so the canonical aggregate can wire the
# slug (per SPECIFICATION/contracts.md §"Shared code sync —
# livespec-dev-tooling" wiring-completeness) without making per-
# commit `just check` runs choke on legitimate authoring
# placeholders in the 201-250 LLOC soft band. Closes the M3
# soft-band drift loophole.
check-no-lloc-soft-warnings:
    #!/usr/bin/env bash
    set -uo pipefail
    if [[ -z "${LIVESPEC_RELEASE_GATE:-}" ]]; then
        echo ":: check-no-lloc-soft-warnings skipped (LIVESPEC_RELEASE_GATE unset; release-gate-only check)"
        exit 0
    fi
    uv run python -m livespec_dev_tooling.checks.no_lloc_soft_warnings

check-no-raise-outside-io:
    uv run python -m livespec_dev_tooling.checks.no_raise_outside_io

# Refuse new revise passes while a stale spec/* branch is ahead of
# master. Invoked by livespec's /livespec:revise SKILL.md pre-step
# refusal; included in the canonical aggregate for cross-cutting
# self-host coverage (per SPECIFICATION/contracts.md wiring-
# completeness invariant). The `--allow-stale-branches` flag
# surfaces the diagnostics as info rather than gating the aggregate;
# load-bearing enforcement remains at the /livespec:revise pre-step
# refusal.
check-no-stale-revise-branches:
    uv run python -m livespec_dev_tooling.checks.no_stale_revise_branches --allow-stale-branches

# Release-gate ONLY — paired with check-check-mutation and check-
# no-lloc-soft-warnings on the release-tag CI workflow. Gated by
# LIVESPEC_RELEASE_GATE so the canonical aggregate can wire the
# slug (per SPECIFICATION/contracts.md §"Shared code sync —
# livespec-dev-tooling" wiring-completeness) without making per-
# commit `just check` runs choke on TODO entries that are
# legitimate authoring placeholders. The release-tag workflow
# MUST set LIVESPEC_RELEASE_GATE=1 before invoking this target.
check-no-todo-registry:
    #!/usr/bin/env bash
    set -uo pipefail
    if [[ -z "${LIVESPEC_RELEASE_GATE:-}" ]]; then
        echo ":: check-no-todo-registry skipped (LIVESPEC_RELEASE_GATE unset; release-gate-only check)"
        exit 0
    fi
    uv run python -m livespec_dev_tooling.checks.no_todo_registry

check-no-write-direct:
    uv run python -m livespec_dev_tooling.checks.no_write_direct

check-pbt-coverage-pure-modules:
    uv run python -m livespec_dev_tooling.checks.pbt_coverage_pure_modules

# Full per-file 100% line+branch coverage gate. Canonical-slug
# alias for the shared per_file_coverage check. The Red-mode skip
# preserved: when LIVESPEC_PRECOMMIT_RED_MODE is set by the Red-
# mode-aware pre-commit aggregate, pytest is skipped (commit-msg
# replay hook is the verifier; aggregate-time coverage is not
# load-bearing in Red mode).
check-per-file-coverage:
    #!/usr/bin/env bash
    set -uo pipefail
    if [[ -n "${LIVESPEC_PRECOMMIT_RED_MODE:-}" ]]; then
        echo ":: check-per-file-coverage skipped (Red-mode pre-commit; verified at Green amend)"
        exit 0
    fi
    # pytest-cov defaults `--cov-config` to `.coveragerc`, which
    # bypasses pyproject.toml's `[tool.coverage.run]` (including
    # the `omit = [...]` carve-outs). Pass the config path
    # explicitly so the vendored-tree exclusion takes effect.
    uv run pytest -n auto --cov --cov-branch --cov-config=pyproject.toml --cov-report=term-missing
    uv run python -m livespec_dev_tooling.checks.per_file_coverage

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

# Trailer-based Red→Green replay verification (hard gate). Invoked
# by lefthook commit-msg stage (NOT pre-commit) — the hook requires
# the commit-message file path as argv[1] to write trailers via
# `git interpret-trailers --in-place`. Wired into the canonical
# aggregate (per SPECIFICATION/contracts.md v094 wiring-completeness)
# but the recipe short-circuits when called with no args — the
# load-bearing verifier is the commit-msg hook, not `just check`.
check-red-green-replay *args:
    #!/usr/bin/env bash
    set -uo pipefail
    if [[ -z "{{args}}" ]]; then
        echo ":: check-red-green-replay skipped (no msg_path provided; aggregate-mode no-op)"
        echo ":: load-bearing verifier is the commit-msg hook (lefthook)"
        exit 0
    fi
    uv run python -m livespec_dev_tooling.checks.red_green_replay {{args}}

check-rop-pipeline-shape:
    uv run python -m livespec_dev_tooling.checks.rop_pipeline_shape

check-skill-invocation-paths:
    uv run python -m livespec_dev_tooling.checks.skill_invocation_paths

check-supervisor-discipline:
    uv run python -m livespec_dev_tooling.checks.supervisor_discipline

check-tests-mirror-pairing:
    uv run python -m livespec_dev_tooling.checks.tests_mirror_pairing

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
# plaintext:*` skill lacks a fixture, failing this target. The CI
# `e2e-cli` job delegates here (no direct tool invocation in the
# workflow). The mock-tier test ALSO runs as part of the normal suite
# under check-per-file-coverage; this target is the dedicated,
# explicitly-named tier entry point CI reports as its own status.
check-e2e-cli:
    uv run pytest tests/e2e-cli -v

# ---------------------------------------------------------------
# Pre-commit aggregate — Red-mode-aware. Classifies the staged
# tree shape; sets LIVESPEC_PRECOMMIT_RED_MODE=1 in Red mode so
# check-per-file-coverage skips (commit-msg replay hook is the
# verifier). Pre-push and CI keep invoking `just check` directly.
# ---------------------------------------------------------------

check-pre-commit:
    #!/usr/bin/env bash
    set -uo pipefail
    staged=$(git diff --cached --name-only --diff-filter=AM)
    py_staged=$(echo "$staged" | grep -E '\.py$' || true)
    test_staged=$(echo "$staged" | grep -E '^tests/.*\.py$' || true)
    impl_staged=$(echo "$staged" | grep -E '^(\.claude-plugin/scripts/|dev-tooling/checks/).*\.py$' || true)
    test_count=0
    impl_count=0
    [[ -n "$test_staged" ]] && test_count=$(echo "$test_staged" | wc -l)
    [[ -n "$impl_staged" ]] && impl_count=$(echo "$impl_staged" | wc -l)
    if [[ -z "$py_staged" ]]; then
        echo ":: doc-only mode detected (zero .py files staged): running just check-pre-commit-doc-only"
        echo ":: pre-push + CI keep the full aggregate as the load-bearing safety net"
        just check-pre-commit-doc-only
        exit $?
    fi
    if [[ "$test_count" -eq 1 ]] && [[ "$impl_count" -eq 0 ]]; then
        echo ":: Red-mode shape detected: $test_staged"
        echo ":: skipping check-per-file-coverage (commit-msg replay hook is the verifier)"
        export LIVESPEC_PRECOMMIT_RED_MODE=1
    fi
    just check

# When zero `.py` files are staged, `check-pre-commit` delegates here.
# Pre-push delegates here via `check-pre-push` for zero-py changesets.
# check-claude-md-coverage and check-heading-coverage are intentionally
# absent here: backlog work-items li-bb5suo (CLAUDE.md backfill) and
# li-4liaxt (heading-coverage backfill) close the gap; until those land
# they would force every doc-only commit to fail the pre-commit gate.
# They remain wired in the full `just check` aggregate (and surface in
# pre-push) as the load-bearing canonical contract.
check-pre-commit-doc-only:
    #!/usr/bin/env bash
    set -uo pipefail
    targets=(
        check-vendor-manifest
        check-no-direct-tool-invocation
        check-check-tools
    )
    failed=()
    for t in "${targets[@]}"; do
        printf '\n::: just %s\n' "$t"
        if ! just "$t"; then
            failed+=("$t")
        fi
    done
    if [[ ${#failed[@]} -gt 0 ]]; then
        printf '\nFailed targets (%d):\n' "${#failed[@]}"
        printf '  - %s\n' "${failed[@]}"
        exit 1
    fi
    printf '\nAll %d doc-only targets passed.\n' "${#targets[@]}"

# Skip the Python-code check subset when the pushed commits contain
# zero `.py` changes; those checks are deterministic functions of
# the source tree and would pass-or-fail identically against the
# merge-base. Falls back to `origin/master` when no upstream branch
# is configured locally.
check-pre-push:
    #!/usr/bin/env bash
    set -uo pipefail
    upstream=$(git rev-parse --abbrev-ref --symbolic-full-name @{upstream} 2>/dev/null || echo "origin/master")
    changeset=$(git diff --name-only "${upstream}..HEAD")
    py_changed=$(echo "$changeset" | grep -E '\.py$' || true)
    if [[ -z "$py_changed" ]]; then
        echo ":: doc-only push detected (zero .py changes vs ${upstream}): running check-pre-commit-doc-only"
        just check-pre-commit-doc-only
        exit $?
    fi
    just check

# ---------------------------------------------------------------
# Pre-commit auxiliary gates.
# ---------------------------------------------------------------

# Ruff fix + format on staged .py files BEFORE the rest of the
# pre-commit gate runs. Non-blocking — unfixable issues fall through
# to check-lint / check-format inside `just check` later. Re-stages
# post-autofix bytes.
lint-autofix-staged:
    #!/usr/bin/env bash
    set -uo pipefail
    staged=$(git diff --cached --name-only --diff-filter=AM | grep -E '\.py$' || true)
    if [[ -z "$staged" ]]; then
        exit 0
    fi
    echo "$staged" | xargs uv run ruff check --fix --exit-zero
    echo "$staged" | xargs uv run ruff format
    echo "$staged" | xargs git add

# ---------------------------------------------------------------
# Mutating targets (opt-in; not run in CI).
# ---------------------------------------------------------------

fmt:
    uv run ruff format .

lint-fix:
    uv run ruff check --fix .

# ---------------------------------------------------------------
# One-shot migration utilities.
# ---------------------------------------------------------------

# Translate a beads .beads/issues.jsonl export into work-items.jsonl
# records. One-shot — re-running on the same input produces duplicates.
# Use during the Phase D.10 cutover only.
migrate-beads beads_jsonl out_jsonl:
    uv run python3 .claude-plugin/scripts/bin/migrate_beads.py \
        --beads-jsonl {{beads_jsonl}} \
        --work-items-out {{out_jsonl}}

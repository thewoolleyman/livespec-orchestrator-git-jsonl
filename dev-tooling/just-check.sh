#!/usr/bin/env bash
# Deliberately omit errexit so the aggregate reports every failing target before
# exiting non-zero.
set -uo pipefail

# Sync the environment ONCE per aggregate pass, then run every target with
# UV_NO_SYNC=1 so per-target `uv run` invocations skip redundant re-syncs.
if ! uv sync --all-groups; then
    echo "ERROR: up-front 'uv sync --all-groups' failed; aborting the check aggregate" >&2
    exit 1
fi
export UV_NO_SYNC=1

skip_targets=("$@")
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
    check-plan-thread-anchor-declared
    check-plan-thread-epic-parity
    check-plugin-resolution
    check-primary-checkout-commit-refuse-hook-installed
    check-private-calls
    check-public-api-result-typed
    check-red-green-replay
    check-required-role-keys-declared
    check-rop-pipeline-shape
    check-self-hosted-routing
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
    check-no-workflow-edits
    check-spec-governance-default-block
    check-work-item-merge-evidence
    check-doctor-static
)

failed=()
ran=0
for target in "${targets[@]}"; do
    skip_this=0
    for skip_target in "${skip_targets[@]}"; do
        if [[ "$target" == "$skip_target" ]]; then
            skip_this=1
            break
        fi
    done
    if [[ "$skip_this" -eq 1 ]]; then
        printf '\n::: just %s (skipped)\n' "$target"
        continue
    fi
    ran=$((ran + 1))
    printf '\n::: just %s\n' "$target"
    if ! just "$target"; then
        failed+=("$target")
    fi
done

printf '\n::: just install-worktree-pack (branch-protection prerequisite)\n'
if ! just install-worktree-pack; then
    failed+=("install-worktree-pack")
else
    printf '\n::: just check-branch-protection (server-side worktree-discipline tripwire)\n'
    if ! just check-branch-protection; then
        failed+=("check-branch-protection")
    fi
fi

if [[ ${#failed[@]} -gt 0 ]]; then
    printf '\nFailed targets (%d):\n' "${#failed[@]}"
    printf '  - %s\n' "${failed[@]}"
    exit 1
fi
printf '\nAll %d targets passed.\n' "${#targets[@]}"
if [[ ${#skip_targets[@]} -eq 0 ]]; then
    uv run python -m livespec_dev_tooling.green_token write || true
fi

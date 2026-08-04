#!/usr/bin/env bash
# Deliberately omit errexit so the doc-only pre-commit subset reports every
# failing target before exiting non-zero.
set -uo pipefail

targets=(
    check-vendor-manifest
    check-no-direct-tool-invocation
    check-check-tools
)
failed=()
for target in "${targets[@]}"; do
    printf '\n::: just %s\n' "$target"
    if ! just "$target"; then
        failed+=("$target")
    fi
done
if [[ ${#failed[@]} -gt 0 ]]; then
    printf '\nFailed targets (%d):\n' "${#failed[@]}"
    printf '  - %s\n' "${failed[@]}"
    exit 1
fi
printf '\nAll %d doc-only targets passed.\n' "${#targets[@]}"

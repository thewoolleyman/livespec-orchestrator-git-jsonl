#!/usr/bin/env bash
set -euo pipefail

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
    echo ":: skipping coverage gates (commit-msg replay hook is the verifier; coverage runs at Green amend)"
    just check-skipping check-coverage check-per-file-coverage
    exit $?
fi
head_msg=$(git log -1 --format=%B 2>/dev/null || true)
if [[ "$impl_count" -ge 1 ]] \
    && grep -q 'TDD-Red-Test-File-Checksum:' <<< "$head_msg" \
    && ! grep -q 'TDD-Green-Verified-At:' <<< "$head_msg"; then
    echo ":: Green-amend shape detected (impl staged; HEAD carries Red-only trailers)"
    echo ":: skipping no-arg check-red-green-replay (commit-msg replay hook verifies the Green amend)"
    just check-skipping check-red-green-replay
    exit $?
fi
just check

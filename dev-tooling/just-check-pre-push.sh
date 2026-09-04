#!/usr/bin/env bash
set -euo pipefail

# PR gate ≡ master gate (livespec plan pr-gate-master-parity R3, epic
# livespec-citqsd): pre-push runs the FULL `just check` aggregate regardless of
# whether the pushed commits touch .py. The retired zero-.py branch delegated a
# doc-only push to check-pre-commit-doc-only — a weaker gate than master's — the
# same skew the CI change-detection gate carried. The green-token memoization
# below is preserved: a working tree byte-identical to the last green `just
# check` skips the aggregate (CI stays authoritative), independent of changeset
# content.
if uv run python -m livespec_dev_tooling.green_token check 2>&1; then
    echo ":: pre-push: green token matched - tree byte-identical to last green check; skipping full aggregate (CI is authoritative)"
    exit 0
fi
just check

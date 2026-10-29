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
# Delegated gate (bd-gj-cbbyic; constraints.md §"Delegated pre-push gate"): on a
# host that can read the gates kubeconfig the gate runs as a cluster Job, in
# place of the local aggregate below. `exec` is load-bearing: the client's
# result IS the push's result, so a delegated run that reaches no verdict
# refuses the push and can never fall through to a local `just check`. A host
# that cannot delegate (a Fabro sandbox, or the gate pod itself) gets a non-zero
# `enabled`, reports that it gated locally, and continues to the aggregate.
if uv run python -m livespec_dev_tooling.gate_remote_delegate enabled; then
    echo ":: pre-push: delegating the gate to the cluster (the local aggregate does not run)"
    exec uv run python -m livespec_dev_tooling.gate_remote_delegate run
fi
echo ":: pre-push: gated locally - delegation does not apply to this host; running full just check"
just check

#!/usr/bin/env bash
set -euo pipefail

uv run python -m livespec_dev_tooling.fleet.local_reconcile
just install-worktree-pack
chmod +x dev-tooling/worktree-hydrate.sh

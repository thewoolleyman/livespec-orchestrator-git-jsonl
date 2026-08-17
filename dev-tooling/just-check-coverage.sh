#!/usr/bin/env bash
set -euo pipefail

if [[ -f .coverage ]]; then
    echo ":: check-coverage: reading existing .coverage (produced by check-per-file-coverage); no duplicate suite run"
    status=0
    env -u COVERAGE_FILE uv run coverage report --fail-under=100 || status=$?
    # Consume-once (livespec-dev-tooling-yilyxr.8): delete after the read so
    # no later standalone run can report from stale coverage data.
    rm -f .coverage
    [ "$status" -eq 0 ] || exit "$status"
else
    echo ":: check-coverage: no .coverage data file (CI standalone job); running the suite"
    env -u COVERAGE_FILE uv run pytest -n "$(bash dev-tooling/just-test-nprocs.sh)" --cov --cov-branch --cov-config=pyproject.toml --cov-report=term-missing
fi

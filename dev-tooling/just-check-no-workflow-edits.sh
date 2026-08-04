#!/usr/bin/env bash
set -euo pipefail

base_ref="${LIVESPEC_WORKFLOW_EDIT_BASE:-origin/master}"
mapfile -t changed < <(
    {
        git diff --name-only "${base_ref}...HEAD" -- .github/workflows/
        git diff --name-only --cached -- .github/workflows/
        git diff --name-only -- .github/workflows/
    } | sort -u
)
if (( ${#changed[@]} > 0 )); then
    echo "ERROR: factory branches must not edit .github/workflows/:" >&2
    printf '  %s\n' "${changed[@]}" >&2
    exit 1
fi

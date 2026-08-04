#!/usr/bin/env bash
set -euo pipefail

uv run python3 .claude-plugin/scripts/bin/migrate_beads.py \
    --beads-jsonl "$1" \
    --work-items-out "$2"

#!/usr/bin/env python3
"""Shebang wrapper for merge-evidence backfill migration."""

from _bootstrap import bootstrap

bootstrap()

from livespec_orchestrator_git_jsonl.migration.merge_evidence_backfill import main

raise SystemExit(main())

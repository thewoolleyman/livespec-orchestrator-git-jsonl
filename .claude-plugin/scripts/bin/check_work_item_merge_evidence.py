#!/usr/bin/env python3
"""Shebang wrapper for check-work-item-merge-evidence. No logic; see livespec_impl_git_jsonl.checks.work_item_merge_evidence."""

from _bootstrap import bootstrap

bootstrap()

from livespec_impl_git_jsonl.checks.work_item_merge_evidence import main

raise SystemExit(main())

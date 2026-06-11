#!/usr/bin/env python3
"""Shebang wrapper for check-no-raw-store-read. No logic; see livespec_impl_git_jsonl.checks.no_raw_store_read."""

from _bootstrap import bootstrap

bootstrap()

from livespec_impl_git_jsonl.checks.no_raw_store_read import main

raise SystemExit(main())

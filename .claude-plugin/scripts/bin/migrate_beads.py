#!/usr/bin/env python3
"""Shebang wrapper for migrate-beads. See livespec_impl_git_jsonl.migration.beads_to_jsonl."""

from _bootstrap import bootstrap

bootstrap()

from livespec_impl_git_jsonl.migration.beads_to_jsonl import main

raise SystemExit(main())

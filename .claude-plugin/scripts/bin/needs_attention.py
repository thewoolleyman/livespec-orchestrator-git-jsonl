#!/usr/bin/env python3
"""Shebang wrapper for needs-attention. No logic; see livespec_orchestrator_git_jsonl.commands.needs_attention."""

from _bootstrap import bootstrap

bootstrap()

from livespec_orchestrator_git_jsonl.commands.needs_attention import main

raise SystemExit(main())

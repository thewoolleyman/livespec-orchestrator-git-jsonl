#!/usr/bin/env python3
"""Shebang wrapper for depends-on typed-form migration."""

from _bootstrap import bootstrap

bootstrap()

from livespec_orchestrator_git_jsonl.migration.depends_on_typed_form import main

raise SystemExit(main())

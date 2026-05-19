"""One-shot migration utilities for legacy substrates.

Currently houses `beads_to_jsonl`, which translates an exported beads
issues.jsonl (or `bd list --status=all --format=json` output) into the
livespec-impl-plaintext work-items JSONL record schema.

Per the multi-repo-split-execution-plan §Phase D, this migration is the
dogfooding validation gate: livespec's own beads-tracked backlog
flows through this script into the plaintext store at the moment
livespec itself switches its `.livespec.jsonc` from beads to
plaintext (Phase D.10).
"""

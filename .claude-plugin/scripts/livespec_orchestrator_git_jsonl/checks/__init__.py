"""Orchestrator-private store-integrity checks (v008 append-only-store disciplines).

Each module exports `main(argv=None) -> int` (0 = pass, 1 = fail) and
is invoked through its `.claude-plugin/scripts/bin/check_<slug>.py`
wrapper by the matching `just check-<slug>` recipe. Per
SPECIFICATION/contracts.md, these
checks wire into THIS repo's `just check` aggregate — NOT into
livespec's doctor (the work-items store is orchestrator-private under
the re-steered contract).
"""

__all__: list[str] = []

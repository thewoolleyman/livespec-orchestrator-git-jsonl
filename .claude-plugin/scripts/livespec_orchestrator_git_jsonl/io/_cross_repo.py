"""Cross-repo manifest and entry parsing on the `Result` railway.

The io/-layer boundary against `livespec_runtime.cross_repo.types`, so no
caller outside io/ needs a try/except for `CrossRepoSchemaError`. The two
parsers upstream are no longer the same SHAPE, and each function below
therefore does a different amount of work — see each docstring.

Public surface:

- `parse_cross_repo_manifest_result(*, parsed)` — parse a dict-shaped
  `cross_repo_targets` block; converts the raised `CrossRepoSchemaError`
  onto the failure track.
- `parse_depends_on_entry_result(*, raw)` — parse a typed `depends_on`
  entry dict; a pass-through, because the upstream parser already
  answers on the failure track.

A caller wanting the absent-shaped answer writes `.value_or(None)` at
its own call site, so discarding the schema error stays a stated policy
of the caller rather than a property of this layer.
"""

from typing import Any

from livespec_runtime.cross_repo.errors import CrossRepoSchemaError
from livespec_runtime.cross_repo.types import (
    CrossRepoManifest,
    DependsOnEntry,
    parse_cross_repo_manifest,
    parse_depends_on_entry,
)
from returns.result import Failure, Result, Success

__all__: list[str] = ["parse_cross_repo_manifest_result", "parse_depends_on_entry_result"]


def parse_cross_repo_manifest_result(
    *, parsed: dict[str, Any]
) -> Result[CrossRepoManifest, CrossRepoSchemaError]:
    """Parse a cross_repo_targets block, carrying the schema error if it fails.

    ⚠️ RENAMED FROM `*_optional`, because the suffix described the return
    shape and the shape changed. These are thin adapters over
    `livespec_runtime.cross_repo.types`' RAISING parsers — this repo's
    boundary against them — and they used to discard the schema error the
    sibling had gone to the trouble of raising.
    """
    try:
        return Success(parse_cross_repo_manifest(parsed=parsed))
    except CrossRepoSchemaError as invalid:
        return Failure(invalid)


def parse_depends_on_entry_result(
    *, raw: dict[str, Any]
) -> Result[DependsOnEntry, CrossRepoSchemaError]:
    """Parse a typed depends_on entry dict, carrying the schema error if it fails.

    A PASS-THROUGH, unlike its manifest sibling: since livespec-runtime
    v0.28.0 `parse_depends_on_entry` discharges `CrossRepoSchemaError` onto
    the failure track itself, so this boundary has nothing left to convert.
    Re-wrapping that result in `Success` would type as
    `Success[Result[...]]` and — worse than the type error — hand callers a
    Success whose payload is a Failure, so `.value_or(None)` yields the
    error object instead of `None` and every malformed entry reads as a
    PARSED one. The railway is already correct; adapting it again breaks it.
    """
    return parse_depends_on_entry(parsed=raw)

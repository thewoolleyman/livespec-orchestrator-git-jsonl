"""Cross-repo manifest and entry parsing with optional-return semantics.

Wraps `livespec_runtime.cross_repo.types` parsers so that callers outside
the io/ layer need no try/except for `CrossRepoSchemaError`.

Public surface:

- `parse_cross_repo_manifest_optional(*, parsed)` — parse a dict-shaped
  `cross_repo_targets` block; returns None on `CrossRepoSchemaError`.
- `parse_depends_on_entry_optional(*, raw)` — parse a typed `depends_on`
  entry dict; returns None on `CrossRepoSchemaError` or unknown kind.
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
    """Parse a typed depends_on entry dict, carrying the schema error if it fails."""
    try:
        return Success(parse_depends_on_entry(parsed=raw))
    except CrossRepoSchemaError as invalid:
        return Failure(invalid)

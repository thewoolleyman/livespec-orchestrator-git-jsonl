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

__all__: list[str] = ["parse_cross_repo_manifest_optional", "parse_depends_on_entry_optional"]


def parse_cross_repo_manifest_optional(*, parsed: dict[str, Any]) -> CrossRepoManifest | None:
    """Parse a cross_repo_targets block; return None on schema error."""
    try:
        return parse_cross_repo_manifest(parsed=parsed)
    except CrossRepoSchemaError:
        return None


def parse_depends_on_entry_optional(*, raw: dict[str, Any]) -> DependsOnEntry | None:
    """Parse a typed depends_on entry dict; return None on schema error or unknown kind."""
    try:
        return parse_depends_on_entry(parsed=raw)
    except CrossRepoSchemaError:
        return None

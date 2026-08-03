"""Spec Reader adapter for livespec-orchestrator-git-jsonl.

Implements the four required capabilities defined in
livespec/SPECIFICATION/contracts.md and concretized for this plugin
in SPECIFICATION/contracts.md.

This v001 implementation is a thin file pass-through: every read goes
straight to the filesystem; no caching, no section-level indexing, no
embedding-based retrieval. The required-capability surface is satisfied
by direct `Path.read_text()` calls plus a unified-diff body for the
version-diff capability.

Public functions (all keyword-only):

- `read_current_specification(*, spec_root)` — returns a SpecSnapshot of
  the live spec tree at <spec-root>/, excluding `proposed_changes/`.
- `read_specification_history(*, spec_root, version)` — returns a
  SpecSnapshot of the <spec-root>/history/vNNN/ tree at the requested
  integer version.
- `current_specification_version(*, spec_root)` — returns the latest
  integer N such that <spec-root>/history/vNNN/ exists.
- `diff_specification_versions(*, spec_root, version_a, version_b)` —
  returns a SpecDiff comparing two history versions, file-by-file.

The well-known spec file set is discovered by directory traversal rather
than hardcoded. The Spec Reader honors the `version-directories-complete`
exemption (a vNNN/ directory may carry a `PRUNED_HISTORY.json` marker
indicating it was pruned per /livespec:prune-history); pruned
versions are returned as SpecSnapshots whose `files` map carries only the
`PRUNED_HISTORY.json` content.
"""

import difflib
import re
from pathlib import Path

from returns.io import IOFailure, IOResult, IOSuccess
from returns.unsafe import unsafe_perform_io

from livespec_orchestrator_git_jsonl.errors import (
    SpecRootNotFoundError,
    SpecVersionNotFoundError,
)
from livespec_orchestrator_git_jsonl.types import FileDiff, SpecDiff, SpecSnapshot

# The two ways a spec tree can be unavailable, as ONE alias so a consumer that
# reads either capability names a single failure type. They stay distinct
# classes because they answer different questions: "there is no spec tree here"
# is an operator typo; "that version was never ratified" is a real query about a
# real tree.
SpecTreeUnavailable = SpecRootNotFoundError | SpecVersionNotFoundError

__all__: list[str] = [
    "current_specification_version",
    "diff_specification_versions",
    "read_current_specification",
    "read_specification_history",
]

_VERSION_DIR_PATTERN = re.compile(r"^v(\d+)$")


def read_current_specification(*, spec_root: Path) -> IOResult[SpecSnapshot, SpecTreeUnavailable]:
    """Return a SpecSnapshot of the live <spec-root>/ tree, or say it is not there.

    ⚠️ ABSENT AND EMPTY ARE DIFFERENT CLAIMS. Without the guard below,
    `_read_spec_directory` rglobs a directory that does not exist, yields
    nothing, and this returns `SpecSnapshot(version=0, files={})` — the exact
    value a spec root that EXISTS and is empty produces. `detect_impl_gaps`
    then extracts zero rules and reports zero gaps, so a mistyped
    `--spec-target` reads as full conformance. The reassuring answer is the one
    that was fabricated, which is why nothing surfaced it.
    """
    if not spec_root.is_dir():
        return IOFailure(SpecRootNotFoundError(spec_root=spec_root))
    files = _read_spec_directory(directory=spec_root, exclude={"history", "proposed_changes"})
    version = current_specification_version(spec_root=spec_root)
    return IOSuccess(SpecSnapshot(version=version, files=files))


def read_specification_history(
    *, spec_root: Path, version: int
) -> IOResult[SpecSnapshot, SpecTreeUnavailable]:
    """Return a SpecSnapshot of <spec-root>/history/v{version:03d}/, or why not.

    The refusal is UNCHANGED in substance — this capability always rejected a
    missing version directory. It is now carried as a value rather than raised,
    per `io/store.py`'s existing `IOFailure(exc)` precedent, so both reads of
    this adapter answer the same shape.
    """
    version_dir = _version_directory(spec_root=spec_root, version=version)
    if not version_dir.exists():
        return IOFailure(SpecVersionNotFoundError(spec_root=spec_root, version=version))
    files = _read_spec_directory(directory=version_dir, exclude=set())
    return IOSuccess(SpecSnapshot(version=version, files=files))


def current_specification_version(*, spec_root: Path) -> int:
    """Return the latest vNNN integer present under <spec-root>/history/."""
    history_dir = spec_root / "history"
    if not history_dir.exists():
        return 0
    versions: list[int] = []
    for child in history_dir.iterdir():
        if not child.is_dir():
            continue
        match = _VERSION_DIR_PATTERN.match(child.name)
        if match is not None:
            versions.append(int(match.group(1)))
    return max(versions) if versions else 0


def diff_specification_versions(
    *, spec_root: Path, version_a: int, version_b: int
) -> IOResult[SpecDiff, SpecTreeUnavailable]:
    """Return a SpecDiff comparing two history versions, or the first failure.

    Written as explicit early returns rather than a `.bind` chain on purpose:
    pyright cannot narrow through `returns`' `KindN` higher-kinded types, and
    this module has three railway sites rather than the "roughly half of all
    lines" that justifies the file-level pragma in `_prune_history_railway.py`.
    Restructuring is that comment's own first-named canonical fix; silencing a
    whole module for three call sites would trade real enforcement for brevity.
    """
    outcome_a = read_specification_history(spec_root=spec_root, version=version_a)
    if isinstance(outcome_a, IOFailure):
        return IOResult.from_failure(unsafe_perform_io(outcome_a.failure()))
    outcome_b = read_specification_history(spec_root=spec_root, version=version_b)
    if isinstance(outcome_b, IOFailure):
        return IOResult.from_failure(unsafe_perform_io(outcome_b.failure()))
    return IOSuccess(
        _diff_snapshots(
            snapshot_a=unsafe_perform_io(outcome_a.unwrap()),
            snapshot_b=unsafe_perform_io(outcome_b.unwrap()),
            version_a=version_a,
            version_b=version_b,
        )
    )


def _diff_snapshots(
    *, snapshot_a: SpecSnapshot, snapshot_b: SpecSnapshot, version_a: int, version_b: int
) -> SpecDiff:
    """Compare two ALREADY-READ snapshots file by file."""
    all_paths = sorted(set(snapshot_a.files.keys()) | set(snapshot_b.files.keys()))
    per_file: dict[str, FileDiff] = {}
    for path in all_paths:
        content_a = snapshot_a.files.get(path, "")
        content_b = snapshot_b.files.get(path, "")
        if content_a == content_b:
            continue
        per_file[path] = _file_diff(path=path, content_a=content_a, content_b=content_b)
    return SpecDiff(version_a=version_a, version_b=version_b, per_file=per_file)


def _read_spec_directory(*, directory: Path, exclude: set[str]) -> dict[str, str]:
    files: dict[str, str] = {}
    for candidate in directory.rglob("*"):
        if not candidate.is_file():
            continue
        relative = candidate.relative_to(directory)
        if any(part in exclude for part in relative.parts):
            continue
        files[str(relative)] = candidate.read_text(encoding="utf-8")
    return files


def _version_directory(*, spec_root: Path, version: int) -> Path:
    return spec_root / "history" / f"v{version:03d}"


def _file_diff(*, path: str, content_a: str, content_b: str) -> FileDiff:
    a_lines = content_a.splitlines(keepends=True)
    b_lines = content_b.splitlines(keepends=True)
    added = 0
    removed = 0
    for line in difflib.ndiff(a_lines, b_lines):
        if line.startswith("+ "):
            added += 1
        elif line.startswith("- "):
            removed += 1
    unified = "".join(
        difflib.unified_diff(a_lines, b_lines, fromfile=f"a/{path}", tofile=f"b/{path}", n=3)
    )
    return FileDiff(path=path, added_lines=added, removed_lines=removed, unified_diff=unified)

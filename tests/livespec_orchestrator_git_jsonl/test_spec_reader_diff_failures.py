"""Failure-track coverage for `diff_specification_versions`.

A NEW file rather than an addition to `test_spec_reader.py`, because that file
is the byte-recorded Red of this change set and must not move between the Red
and Green halves of the pair.
"""

from pathlib import Path

from livespec_orchestrator_git_jsonl.errors import SpecVersionNotFoundError
from livespec_orchestrator_git_jsonl.spec_reader import diff_specification_versions
from returns.io import IOFailure
from returns.unsafe import unsafe_perform_io


def _failure(outcome: object) -> object:
    assert isinstance(outcome, IOFailure), f"expected a failure, got {outcome}"
    return unsafe_perform_io(outcome.failure())  # pyright: ignore[reportAttributeAccessIssue]


def _seed_history(*, spec_root: Path, version: int, content: str) -> None:
    version_dir = spec_root / "history" / f"v{version:03d}"
    version_dir.mkdir(parents=True, exist_ok=True)
    _ = (version_dir / "spec.md").write_text(content, encoding="utf-8")


def test_diff_specification_versions_missing_left_version_is_a_failure(tmp_path: Path) -> None:
    """Either side being absent fails the diff; neither is silently empty.

    Before the conversion this raised out of the adapter. It now carries the
    same refusal as a value, and the two sides are checked independently so the
    failure names WHICH version was missing.
    """
    spec_root = tmp_path / "SPECIFICATION"
    _seed_history(spec_root=spec_root, version=2, content="# v2\n")

    failure = _failure(diff_specification_versions(spec_root=spec_root, version_a=1, version_b=2))

    assert isinstance(failure, SpecVersionNotFoundError)
    assert failure.version == 1


def test_diff_specification_versions_missing_right_version_is_a_failure(tmp_path: Path) -> None:
    spec_root = tmp_path / "SPECIFICATION"
    _seed_history(spec_root=spec_root, version=1, content="# v1\n")

    failure = _failure(diff_specification_versions(spec_root=spec_root, version_a=1, version_b=9))

    assert isinstance(failure, SpecVersionNotFoundError)
    assert failure.version == 9

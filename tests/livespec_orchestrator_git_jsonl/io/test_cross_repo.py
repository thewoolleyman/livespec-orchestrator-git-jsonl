"""Tests for io/_cross_repo.py cross-repo manifest and entry helpers."""

from livespec_orchestrator_git_jsonl.io._cross_repo import (
    parse_cross_repo_manifest_result,
    parse_depends_on_entry_result,
)
from livespec_runtime.cross_repo.errors import CrossRepoSchemaError
from livespec_runtime.cross_repo.types import CrossRepoManifest, LocalDependency
from returns.result import Failure, Success


def test_parse_cross_repo_manifest_empty_dict() -> None:
    outcome = parse_cross_repo_manifest_result(parsed={})
    assert isinstance(outcome, Success)
    assert outcome.unwrap().targets == {}


def test_parse_cross_repo_manifest_valid_target() -> None:
    parsed = {"my-repo": {"github_url": "https://github.com/org/my-repo"}}
    outcome = parse_cross_repo_manifest_result(parsed=parsed)
    assert isinstance(outcome, Success)
    manifest = outcome.unwrap()
    assert isinstance(manifest, CrossRepoManifest)
    assert "my-repo" in manifest.targets


def test_parse_cross_repo_manifest_carries_the_schema_error_on_invalid() -> None:
    """The error the sibling raises is now KEPT, where the twin used to drop it."""
    outcome = parse_cross_repo_manifest_result(parsed={"bad-repo": {"no_github_url": True}})

    assert isinstance(outcome, Failure)
    assert isinstance(outcome.failure(), CrossRepoSchemaError)


def test_parse_depends_on_entry_valid_local() -> None:
    outcome = parse_depends_on_entry_result(raw={"kind": "local", "work_item_id": "wi-001"})
    assert isinstance(outcome, Success)
    entry = outcome.unwrap()
    assert isinstance(entry, LocalDependency)
    assert entry.work_item_id == "wi-001"


def test_parse_depends_on_entry_carries_the_schema_error_on_invalid() -> None:
    outcome = parse_depends_on_entry_result(raw={"kind": "local"})

    assert isinstance(outcome, Failure)
    assert isinstance(outcome.failure(), CrossRepoSchemaError)


def test_parse_depends_on_entry_carries_the_schema_error_on_unknown_kind() -> None:
    outcome = parse_depends_on_entry_result(raw={"kind": "unknown_kind_xyz"})

    assert isinstance(outcome, Failure)
    assert isinstance(outcome.failure(), CrossRepoSchemaError)


def test_value_or_none_is_how_a_caller_opts_into_the_absent_shape() -> None:
    """What the deleted `*_optional` twins did, now stated at the call site."""
    assert parse_depends_on_entry_result(raw={"kind": "local"}).value_or(None) is None
    assert parse_cross_repo_manifest_result(parsed={"b": {"x": 1}}).value_or(None) is None

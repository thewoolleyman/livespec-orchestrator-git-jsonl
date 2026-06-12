"""Tests for io/_cross_repo.py cross-repo manifest and entry helpers."""

from livespec_impl_git_jsonl.io._cross_repo import (
    parse_cross_repo_manifest_optional,
    parse_depends_on_entry_optional,
)
from livespec_runtime.cross_repo.types import CrossRepoManifest, LocalDependency


def test_parse_cross_repo_manifest_optional_empty_dict() -> None:
    result = parse_cross_repo_manifest_optional(parsed={})
    assert isinstance(result, CrossRepoManifest)
    assert result.targets == {}


def test_parse_cross_repo_manifest_optional_valid_target() -> None:
    parsed = {"my-repo": {"github_url": "https://github.com/org/my-repo"}}
    result = parse_cross_repo_manifest_optional(parsed=parsed)
    assert isinstance(result, CrossRepoManifest)
    assert "my-repo" in result.targets


def test_parse_cross_repo_manifest_optional_returns_none_on_invalid() -> None:
    parsed = {"bad-repo": {"no_github_url": True}}
    result = parse_cross_repo_manifest_optional(parsed=parsed)
    assert result is None


def test_parse_depends_on_entry_optional_valid_local() -> None:
    raw = {"kind": "local", "work_item_id": "wi-001"}
    result = parse_depends_on_entry_optional(raw=raw)
    assert isinstance(result, LocalDependency)
    assert result.work_item_id == "wi-001"


def test_parse_depends_on_entry_optional_returns_none_on_invalid() -> None:
    raw = {"kind": "local"}
    result = parse_depends_on_entry_optional(raw=raw)
    assert result is None


def test_parse_depends_on_entry_optional_returns_none_on_unknown_kind() -> None:
    raw = {"kind": "unknown_kind_xyz"}
    result = parse_depends_on_entry_optional(raw=raw)
    assert result is None

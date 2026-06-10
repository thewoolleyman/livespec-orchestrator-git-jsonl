"""Tests for the shared config-resolution helper."""

from pathlib import Path

from livespec_impl_git_jsonl.commands._config import resolve_store_config


def test_resolve_store_config_uses_defaults(tmp_path: Path) -> None:
    config = resolve_store_config(cwd=tmp_path, work_items_arg=None, memos_arg=None)
    assert config.work_items_path == tmp_path / "work-items.jsonl"
    assert config.memos_path == tmp_path / "memos.jsonl"


def test_resolve_store_config_honors_arg_overrides(tmp_path: Path) -> None:
    config = resolve_store_config(
        cwd=tmp_path,
        work_items_arg="custom/work.jsonl",
        memos_arg="custom/memos.jsonl",
    )
    assert config.work_items_path == tmp_path / "custom/work.jsonl"
    assert config.memos_path == tmp_path / "custom/memos.jsonl"

"""Tests for the shared config-resolution helper."""

from pathlib import Path

from livespec_impl_git_jsonl.commands._config import resolve_store_config


def test_resolve_store_config_uses_defaults(tmp_path: Path) -> None:
    config = resolve_store_config(cwd=tmp_path, work_items_arg=None)
    assert config.work_items_path == tmp_path / "work-items.jsonl"


def test_resolve_store_config_honors_arg_override(tmp_path: Path) -> None:
    config = resolve_store_config(
        cwd=tmp_path,
        work_items_arg="custom/work.jsonl",
    )
    assert config.work_items_path == tmp_path / "custom/work.jsonl"

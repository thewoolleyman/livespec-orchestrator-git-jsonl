"""Malformed-shape coverage for needs-attention spec-next resolution."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from livespec_orchestrator_git_jsonl.commands.needs_attention import (
    _as_str_argv,
    _claude_installed_core_roots,
    _read_spec_clis_next_argv,
)


@pytest.mark.parametrize(
    "value",
    ["x", [], [1, 2], ["python3", 1]],
)
def test_as_str_argv_rejects_non_string_argv_shapes(value: object) -> None:
    assert _as_str_argv(value=value) is None


@pytest.mark.parametrize(
    "body",
    [
        "[1, 2, 3]",
        '{"spec_clis": "x"}',
        '{"spec_clis": {"next": "x"}}',
        '{"spec_clis": {"next": []}}',
        '{"spec_clis": {"next": [1, 2]}}',
    ],
)
def test_read_spec_clis_next_argv_off_happy_path_returns_none(tmp_path: Path, body: str) -> None:
    (tmp_path / ".livespec.jsonc").write_text(body, encoding="utf-8")

    assert _read_spec_clis_next_argv(project_root=tmp_path) is None


@pytest.mark.parametrize(
    "registry_text",
    [
        json.dumps([1, 2]),
        json.dumps({}),
        json.dumps({"plugins": "x"}),
        json.dumps({"plugins": {"livespec@livespec": "x"}}),
        json.dumps({"plugins": {"livespec@livespec": ["str", {"installPath": ""}, {"x": 1}]}}),
    ],
)
def test_claude_installed_core_roots_malformed_yields_nothing(
    tmp_path: Path, registry_text: str
) -> None:
    registry = tmp_path / "installed_plugins.json"
    registry.write_text(registry_text, encoding="utf-8")

    assert list(_claude_installed_core_roots(registry=registry)) == []

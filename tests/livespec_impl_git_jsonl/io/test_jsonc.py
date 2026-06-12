"""Tests for io/_jsonc.py JSONC parsing helpers."""

import pytest
from livespec_impl_git_jsonl.io._jsonc import JsoncParseError, loads, loads_optional


def test_loads_valid() -> None:
    result = loads(text='{"key": "value"}')
    assert result == {"key": "value"}


def test_loads_strips_line_comments() -> None:
    text = '{\n  // a comment\n  "k": 1\n}'
    result = loads(text=text)
    assert result == {"k": 1}


def test_loads_preserves_double_slash_inside_string() -> None:
    text = '{"url": "https://example.com"}'
    result = loads(text=text)
    assert result == {"url": "https://example.com"}


def test_loads_raises_on_malformed() -> None:
    with pytest.raises(JsoncParseError) as exc_info:
        loads(text="not json at all {{{")
    assert "jsonc parse failed" in exc_info.value.detail


def test_loads_optional_valid() -> None:
    result = loads_optional(text='{"x": 42}')
    assert result == {"x": 42}


def test_loads_optional_returns_none_on_malformed() -> None:
    result = loads_optional(text="{bad}")
    assert result is None

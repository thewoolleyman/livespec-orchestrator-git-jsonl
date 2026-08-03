"""Tests for the minimal JSONC stripper."""

from typing import Any

from livespec_orchestrator_git_jsonl.commands import _jsonc
from returns.result import Failure, Success


def _decoded(text: str) -> Any:
    """The parsed value, asserting the parse took the success track."""
    outcome = _jsonc.loads(text=text)
    assert isinstance(outcome, Success), f"expected success, got {outcome}"
    return outcome.unwrap()


def test_loads_plain_json() -> None:
    assert _decoded('{"a": 1, "b": [1, 2, 3]}') == {"a": 1, "b": [1, 2, 3]}


def test_loads_strips_line_comments() -> None:
    text = """
    {
      // top comment
      "a": 1,
      "b": 2 // trailing comment
    }
    """
    assert _decoded(text) == {"a": 1, "b": 2}


def test_loads_preserves_double_slash_inside_strings() -> None:
    assert _decoded('{"url": "https://example.com/path"}') == {"url": "https://example.com/path"}


def test_loads_handles_escaped_quote_in_string() -> None:
    text = r'{"q": "say \"hi\" //not a comment"}'
    assert _decoded(text) == {"q": 'say "hi" //not a comment'}


def test_loads_reports_malformed_json_on_the_failure_track() -> None:
    outcome = _jsonc.loads(text="{not valid")

    assert isinstance(outcome, Failure)
    assert isinstance(outcome.failure(), _jsonc.JsoncParseError)

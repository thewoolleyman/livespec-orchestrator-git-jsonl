"""Tests for io/_jsonc.py JSONC parsing helpers."""

from typing import Any

from livespec_orchestrator_git_jsonl.io._jsonc import JsoncParseError, loads
from returns.result import Failure, Success


def _decoded(text: str) -> Any:
    """The parsed value, asserting the parse took the success track."""
    outcome = loads(text=text)
    assert isinstance(outcome, Success), f"expected success, got {outcome}"
    return outcome.unwrap()


def test_loads_valid() -> None:
    assert _decoded('{"key": "value"}') == {"key": "value"}


def test_loads_strips_line_comments() -> None:
    assert _decoded('{\n  // a comment\n  "k": 1\n}') == {"k": 1}


def test_loads_preserves_double_slash_inside_string() -> None:
    assert _decoded('{"url": "https://example.com"}') == {"url": "https://example.com"}


def test_loads_reports_malformed_input_on_the_failure_track() -> None:
    """Same error type, same `detail` — only the channel moved."""
    outcome = loads(text="not json at all {{{")

    assert isinstance(outcome, Failure)
    failure = outcome.failure()
    assert isinstance(failure, JsoncParseError)
    assert "jsonc parse failed" in failure.detail


def test_value_or_none_is_how_a_caller_opts_into_the_absent_shape() -> None:
    """The replacement for the deleted `loads_optional`, pinned at the call shape.

    Its two tests asserted exactly this pair of behaviours; they are kept
    together here so the deletion cannot quietly drop the coverage.
    """
    assert loads(text='{"x": 42}').value_or(None) == {"x": 42}
    assert loads(text="{bad}").value_or(None) is None

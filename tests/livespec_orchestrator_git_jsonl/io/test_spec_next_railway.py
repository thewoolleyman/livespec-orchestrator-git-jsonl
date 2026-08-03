"""The `io/` layer reports what it could not do instead of fabricating an answer.

`run_capture` turned an unspawnable command into `ProcessResult(stdout="",
returncode=1)` — a well-formed result describing a process that never ran, and
indistinguishable at the call site from a command that ran and exited 1.
`load_json_file_optional` collapsed three different situations — the file is
absent, the file is unreadable, the file is not JSON — into one `None`.

These tests pin the two answers that were previously invented.
"""

from __future__ import annotations

from pathlib import Path

from livespec_orchestrator_git_jsonl.io.spec_next import (
    CommandUnavailable,
    ProcessResult,
    load_json_file_optional,
    run_capture,
)
from returns.io import IOFailure, IOSuccess
from returns.unsafe import unsafe_perform_io

__all__: list[str] = []


def test_run_capture_carries_a_real_exit_code_on_the_success_track() -> None:
    """A command that RAN is a success, whatever it exited with."""
    outcome = run_capture(argv=["sh", "-c", "printf out; exit 3"], timeout=10)

    assert isinstance(outcome, IOSuccess)
    assert unsafe_perform_io(outcome.unwrap()) == ProcessResult(stdout="out", returncode=3)


def test_run_capture_does_not_invent_an_exit_code_for_a_command_that_never_ran() -> None:
    """⛔ The defect: an unspawnable command used to become `returncode=1`.

    A caller reading that could not tell it from a command that ran and failed,
    so a missing binary was reported as a real answer.
    """
    outcome = run_capture(argv=["git-jsonl-no-such-binary"], timeout=10)

    assert isinstance(outcome, IOFailure)
    failure = unsafe_perform_io(outcome.failure())
    assert isinstance(failure, CommandUnavailable)
    assert "git-jsonl-no-such-binary" in failure.argv


def test_an_absent_json_file_is_an_answer_not_a_failure(tmp_path: Path) -> None:
    """`None` on the SUCCESS track: the file is genuinely not there."""
    outcome = load_json_file_optional(path=tmp_path / "nope.json")

    assert isinstance(outcome, IOSuccess)
    assert unsafe_perform_io(outcome.unwrap()) is None


def test_an_unparseable_json_file_is_a_failure_not_an_absence(tmp_path: Path) -> None:
    """⛔ The other half of the defect: 'not JSON' used to read as 'not there'."""
    bad = tmp_path / "bad.json"
    _ = bad.write_text("{not json", encoding="utf-8")

    outcome = load_json_file_optional(path=bad)

    assert isinstance(outcome, IOFailure)
    assert "bad.json" in unsafe_perform_io(outcome.failure()).path

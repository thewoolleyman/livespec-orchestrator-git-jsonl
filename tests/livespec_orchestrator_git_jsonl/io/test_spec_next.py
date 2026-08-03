"""Tests for spec-`next` I/O helpers."""

import subprocess
from pathlib import Path
from typing import Any

from livespec_orchestrator_git_jsonl.io.spec_next import (
    CommandUnavailable,
    JsonFileUnreadable,
    load_json_file_optional,
    run_capture,
)
from returns.io import IOFailure, IOResult, IOSuccess
from returns.unsafe import unsafe_perform_io


def _answer(outcome: IOResult[Any, Any]) -> Any:
    """The value on the success track, asserting the read did not fail."""
    assert isinstance(outcome, IOSuccess), f"expected success, got {outcome}"
    return unsafe_perform_io(outcome.unwrap())


def _failure(outcome: IOResult[Any, Any]) -> Any:
    """The failure a read carries, asserting it took the failure track."""
    assert isinstance(outcome, IOFailure), f"expected a failure, got {outcome}"
    return unsafe_perform_io(outcome.failure())


def test_load_json_file_is_absent_when_missing(tmp_path: Path) -> None:
    """Absent stays an ANSWER — `None` on the success track."""
    assert _answer(load_json_file_optional(path=tmp_path / "missing.json")) is None


def test_load_json_file_returns_parsed_json(tmp_path: Path) -> None:
    path = tmp_path / "file.json"
    _ = path.write_text('{"a": 1}', encoding="utf-8")

    assert _answer(load_json_file_optional(path=path)) == {"a": 1}


def test_load_json_file_reports_invalid_json_as_a_failure(tmp_path: Path) -> None:
    """⛔ Previously indistinguishable from "the file is not there"."""
    path = tmp_path / "file.json"
    _ = path.write_text("{not json", encoding="utf-8")

    failure = _failure(load_json_file_optional(path=path))
    assert isinstance(failure, JsonFileUnreadable)
    assert failure.path == str(path)


def test_run_capture_returns_process_result() -> None:
    result = _answer(run_capture(argv=["python3", "-c", "print('ok')"], timeout=10))

    assert result.returncode == 0
    assert result.stdout == "ok\n"


def test_run_capture_reports_a_missing_executable_as_a_failure() -> None:
    """⛔ THE DEFECT: this used to be `returncode=1`, a real exit code.

    A caller could not tell "the command ran and failed" from "the command
    does not exist".
    """
    failure = _failure(run_capture(argv=["/definitely/missing/executable"], timeout=10))

    assert isinstance(failure, CommandUnavailable)
    assert "/definitely/missing/executable" in failure.argv


def test_run_capture_reports_a_timeout_as_a_failure() -> None:
    """A command that outran its timeout produced no exit code to report."""
    failure = _failure(run_capture(argv=["python3", "-c", "import time; time.sleep(2)"], timeout=1))

    assert isinstance(failure, CommandUnavailable)
    assert failure.detail != ""


def test_run_capture_keeps_a_real_nonzero_exit_on_the_success_track() -> None:
    result = _answer(
        run_capture(argv=["python3", "-c", "import sys; print('bad'); sys.exit(7)"], timeout=10)
    )

    assert result.returncode == 7
    assert result.stdout == "bad\n"


def test_timeout_expired_is_subprocess_error() -> None:
    assert issubclass(subprocess.TimeoutExpired, subprocess.SubprocessError)

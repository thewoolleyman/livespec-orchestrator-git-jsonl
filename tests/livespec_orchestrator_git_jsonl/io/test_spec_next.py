"""Tests for spec-`next` I/O helpers."""

import subprocess
from pathlib import Path

from livespec_orchestrator_git_jsonl.io.spec_next import (
    load_json_file_optional,
    loads_json_optional,
    run_capture,
)


def test_loads_json_optional_returns_parsed_json() -> None:
    assert loads_json_optional(text='{"a": 1}') == {"a": 1}


def test_loads_json_optional_returns_none_on_invalid_json() -> None:
    assert loads_json_optional(text="{not json") is None


def test_load_json_file_optional_returns_none_when_missing(tmp_path: Path) -> None:
    assert load_json_file_optional(path=tmp_path / "missing.json") is None


def test_load_json_file_optional_returns_parsed_json(tmp_path: Path) -> None:
    path = tmp_path / "file.json"
    path.write_text('{"a": 1}', encoding="utf-8")

    assert load_json_file_optional(path=path) == {"a": 1}


def test_load_json_file_optional_returns_none_on_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "file.json"
    path.write_text("{not json", encoding="utf-8")

    assert load_json_file_optional(path=path) is None


def test_run_capture_returns_process_result() -> None:
    result = run_capture(argv=["python3", "-c", "print('ok')"], timeout=10)

    assert result.returncode == 0
    assert result.stdout == "ok\n"


def test_run_capture_returns_nonzero_result_on_missing_executable() -> None:
    result = run_capture(argv=["/definitely/missing/executable"], timeout=10)

    assert result.returncode == 1
    assert result.stdout == ""


def test_run_capture_returns_nonzero_result_on_timeout() -> None:
    result = run_capture(
        argv=["python3", "-c", "import time; time.sleep(2)"],
        timeout=1,
    )

    assert result.returncode == 1
    assert result.stdout == ""


def test_run_capture_returns_nonzero_process_result() -> None:
    result = run_capture(
        argv=["python3", "-c", "import sys; print('bad'); sys.exit(7)"],
        timeout=10,
    )

    assert result.returncode == 7
    assert result.stdout == "bad\n"


def test_timeout_expired_is_subprocess_error() -> None:
    assert issubclass(subprocess.TimeoutExpired, subprocess.SubprocessError)

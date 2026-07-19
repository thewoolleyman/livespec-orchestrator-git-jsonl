"""Tests for the io/store.py raw JSONL file I/O layer."""

import json
from pathlib import Path
from typing import Any

from livespec_orchestrator_git_jsonl.errors import MalformedRecordLineError, StoreFileMissingError
from livespec_orchestrator_git_jsonl.io.store import append_record, iter_records, parse_jsonl_line
from returns.io import IOFailure, IOResult, IOSuccess
from returns.result import Failure, Result, Success
from returns.unsafe import unsafe_perform_io


def _io_failure(result: IOResult[list[tuple[int, dict[str, Any]]], Exception]) -> Exception:
    assert isinstance(result, IOFailure)
    return unsafe_perform_io(result.failure())


def _line_failure(
    result: Result[dict[str, Any], MalformedRecordLineError],
) -> MalformedRecordLineError:
    assert isinstance(result, Failure)
    return result.failure()


def test_iter_records_returns_failure_on_missing_file(tmp_path: Path) -> None:
    path = tmp_path / "absent.jsonl"
    result = iter_records(path=path)
    assert isinstance(result, IOResult)
    failure = _io_failure(result)
    assert isinstance(failure, StoreFileMissingError)
    assert failure.path == path


def test_iter_records_returns_success_with_parsed_dicts(tmp_path: Path) -> None:
    path = tmp_path / "store.jsonl"
    r1 = {"id": "wi-001", "v": 1}
    r2 = {"id": "wi-002", "v": 2}
    path.write_text(
        json.dumps(r1, separators=(",", ":"), sort_keys=True)
        + "\n"
        + json.dumps(r2, separators=(",", ":"), sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    result = iter_records(path=path)
    assert isinstance(result, IOSuccess)
    assert unsafe_perform_io(result.unwrap()) == [(1, r1), (2, r2)]


def test_iter_records_returns_failure_on_malformed_json(tmp_path: Path) -> None:
    path = tmp_path / "store.jsonl"
    path.write_text("not valid json\n", encoding="utf-8")
    result = iter_records(path=path)
    failure = _io_failure(result)
    assert isinstance(failure, MalformedRecordLineError)
    assert failure.line_number == 1


def test_iter_records_returns_failure_on_empty_line(tmp_path: Path) -> None:
    path = tmp_path / "store.jsonl"
    path.write_text('{"id":"a"}\n\n{"id":"b"}\n', encoding="utf-8")
    result = iter_records(path=path)
    failure = _io_failure(result)
    assert isinstance(failure, MalformedRecordLineError)
    assert failure.line_number == 2


def test_iter_records_returns_failure_on_non_dict_json(tmp_path: Path) -> None:
    path = tmp_path / "store.jsonl"
    path.write_text("[1, 2, 3]\n", encoding="utf-8")
    result = iter_records(path=path)
    failure = _io_failure(result)
    assert isinstance(failure, MalformedRecordLineError)
    assert "record root must be a JSON object" in failure.detail


def test_append_record_returns_io_success_and_creates_file(tmp_path: Path) -> None:
    path = tmp_path / "store.jsonl"
    assert not path.exists()
    result = append_record(path=path, payload={"x": 1})
    assert isinstance(result, IOResult)
    assert isinstance(result, IOSuccess)
    assert unsafe_perform_io(result.unwrap()) is None
    assert path.exists()
    assert json.loads(path.read_text(encoding="utf-8")) == {"x": 1}


def test_append_record_appends_multiple(tmp_path: Path) -> None:
    path = tmp_path / "store.jsonl"
    assert isinstance(append_record(path=path, payload={"n": 1}), IOSuccess)
    assert isinstance(append_record(path=path, payload={"n": 2}), IOSuccess)
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines == ['{"n":1}', '{"n":2}']


def test_append_record_creates_parent_dirs(tmp_path: Path) -> None:
    path = tmp_path / "deep" / "nested" / "store.jsonl"
    assert not path.parent.exists()
    assert isinstance(append_record(path=path, payload={"k": "v"}), IOSuccess)
    assert path.exists()


def test_parse_jsonl_line_valid(tmp_path: Path) -> None:
    path = tmp_path / "store.jsonl"
    result = parse_jsonl_line(path=path, line_number=1, raw_line='{"a":1}\n')
    assert isinstance(result, Result)
    assert isinstance(result, Success)
    assert result.unwrap() == {"a": 1}


def test_parse_jsonl_line_strips_newline(tmp_path: Path) -> None:
    path = tmp_path / "store.jsonl"
    result = parse_jsonl_line(path=path, line_number=1, raw_line='{"b":2}')
    assert isinstance(result, Success)
    assert result.unwrap() == {"b": 2}


def test_parse_jsonl_line_returns_failure_on_empty(tmp_path: Path) -> None:
    path = tmp_path / "store.jsonl"
    result = parse_jsonl_line(path=path, line_number=3, raw_line="\n")
    failure = _line_failure(result)
    assert failure.line_number == 3
    assert "empty line" in failure.detail


def test_parse_jsonl_line_returns_failure_on_bad_json(tmp_path: Path) -> None:
    path = tmp_path / "store.jsonl"
    result = parse_jsonl_line(path=path, line_number=7, raw_line="bad json\n")
    failure = _line_failure(result)
    assert failure.line_number == 7
    assert "JSON parse error" in failure.detail


def test_parse_jsonl_line_returns_failure_on_non_dict(tmp_path: Path) -> None:
    path = tmp_path / "store.jsonl"
    result = parse_jsonl_line(path=path, line_number=5, raw_line="[1,2]\n")
    failure = _line_failure(result)
    assert failure.line_number == 5
    assert "record root must be a JSON object" in failure.detail

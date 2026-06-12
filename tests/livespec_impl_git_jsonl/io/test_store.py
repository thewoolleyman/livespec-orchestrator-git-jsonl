"""Tests for the io/store.py raw JSONL file I/O layer."""

import json
from pathlib import Path

import pytest
from livespec_impl_git_jsonl.errors import MalformedRecordLineError, StoreFileMissingError
from livespec_impl_git_jsonl.io.store import append_record, iter_records, parse_jsonl_line


def test_iter_records_raises_on_missing_file(tmp_path: Path) -> None:
    path = tmp_path / "absent.jsonl"
    with pytest.raises(StoreFileMissingError) as exc_info:
        list(iter_records(path=path))
    assert exc_info.value.path == path


def test_iter_records_yields_parsed_dicts(tmp_path: Path) -> None:
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
    records = list(iter_records(path=path))
    assert records == [(1, r1), (2, r2)]


def test_iter_records_raises_on_malformed_json(tmp_path: Path) -> None:
    path = tmp_path / "store.jsonl"
    path.write_text("not valid json\n", encoding="utf-8")
    with pytest.raises(MalformedRecordLineError) as exc_info:
        list(iter_records(path=path))
    assert exc_info.value.line_number == 1


def test_iter_records_raises_on_empty_line(tmp_path: Path) -> None:
    path = tmp_path / "store.jsonl"
    path.write_text('{"id":"a"}\n\n{"id":"b"}\n', encoding="utf-8")
    with pytest.raises(MalformedRecordLineError) as exc_info:
        list(iter_records(path=path))
    assert exc_info.value.line_number == 2


def test_iter_records_raises_on_non_dict_json(tmp_path: Path) -> None:
    path = tmp_path / "store.jsonl"
    path.write_text("[1, 2, 3]\n", encoding="utf-8")
    with pytest.raises(MalformedRecordLineError) as exc_info:
        list(iter_records(path=path))
    assert "record root must be a JSON object" in exc_info.value.detail


def test_append_record_creates_file(tmp_path: Path) -> None:
    path = tmp_path / "store.jsonl"
    assert not path.exists()
    append_record(path=path, payload={"x": 1})
    assert path.exists()
    assert json.loads(path.read_text(encoding="utf-8")) == {"x": 1}


def test_append_record_appends_multiple(tmp_path: Path) -> None:
    path = tmp_path / "store.jsonl"
    append_record(path=path, payload={"n": 1})
    append_record(path=path, payload={"n": 2})
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines == ['{"n":1}', '{"n":2}']


def test_append_record_creates_parent_dirs(tmp_path: Path) -> None:
    path = tmp_path / "deep" / "nested" / "store.jsonl"
    assert not path.parent.exists()
    append_record(path=path, payload={"k": "v"})
    assert path.exists()


def test_parse_jsonl_line_valid(tmp_path: Path) -> None:
    path = tmp_path / "store.jsonl"
    result = parse_jsonl_line(path=path, line_number=1, raw_line='{"a":1}\n')
    assert result == {"a": 1}


def test_parse_jsonl_line_strips_newline(tmp_path: Path) -> None:
    path = tmp_path / "store.jsonl"
    result = parse_jsonl_line(path=path, line_number=1, raw_line='{"b":2}')
    assert result == {"b": 2}


def test_parse_jsonl_line_raises_on_empty(tmp_path: Path) -> None:
    path = tmp_path / "store.jsonl"
    with pytest.raises(MalformedRecordLineError) as exc_info:
        parse_jsonl_line(path=path, line_number=3, raw_line="\n")
    assert exc_info.value.line_number == 3
    assert "empty line" in exc_info.value.detail


def test_parse_jsonl_line_raises_on_bad_json(tmp_path: Path) -> None:
    path = tmp_path / "store.jsonl"
    with pytest.raises(MalformedRecordLineError) as exc_info:
        parse_jsonl_line(path=path, line_number=7, raw_line="bad json\n")
    assert exc_info.value.line_number == 7
    assert "JSON parse error" in exc_info.value.detail


def test_parse_jsonl_line_raises_on_non_dict(tmp_path: Path) -> None:
    path = tmp_path / "store.jsonl"
    with pytest.raises(MalformedRecordLineError) as exc_info:
        parse_jsonl_line(path=path, line_number=5, raw_line="[1,2]\n")
    assert exc_info.value.line_number == 5
    assert "record root must be a JSON object" in exc_info.value.detail

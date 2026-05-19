"""Tests for the EXPECTED-error exception classes."""

from pathlib import Path

from livespec_impl_plaintext.errors import (
    MalformedRecordLineError,
    SchemaViolationError,
    SpecVersionNotFoundError,
    StoreFileMissingError,
)


def test_store_file_missing_error_message_and_attrs() -> None:
    path = Path("/tmp/work-items.jsonl")
    err = StoreFileMissingError(path=path)
    assert err.path == path
    assert str(err) == f"JSONL store file not found: {path}"


def test_malformed_record_line_error_message_and_attrs() -> None:
    path = Path("/tmp/work-items.jsonl")
    err = MalformedRecordLineError(
        path=path, line_number=42, raw_line="not-json\n", detail="JSON parse error: foo"
    )
    assert err.path == path
    assert err.line_number == 42
    assert err.raw_line == "not-json\n"
    assert err.detail == "JSON parse error: foo"
    assert str(err) == f"Malformed JSONL record at {path}:42: JSON parse error: foo"


def test_schema_violation_error_message_and_attrs() -> None:
    path = Path("/tmp/work-items.jsonl")
    err = SchemaViolationError(path=path, line_number=7, detail="missing key")
    assert err.path == path
    assert err.line_number == 7
    assert err.detail == "missing key"
    assert str(err) == f"Schema violation at {path}:7: missing key"


def test_spec_version_not_found_error_message_and_attrs() -> None:
    spec_root = Path("/tmp/SPECIFICATION")
    err = SpecVersionNotFoundError(spec_root=spec_root, version=42)
    assert err.spec_root == spec_root
    assert err.version == 42
    assert str(err) == (
        f"Specification history version v042 not found under {spec_root / 'history'}"
    )

"""Tests for the bare-string + blocked_by → typed depends_on migration.

Per `livespec/SPECIFICATION/contracts.md` v072 §"Cross-repo dependency
awareness" + work-item li-f5wmjr §"(3) Data migration".
"""

from __future__ import annotations

import json
from pathlib import Path

from livespec_impl_plaintext.migration import depends_on_typed_form as migration

__all__: list[str] = []


def _write(path: Path, records: list[dict[str, object]]) -> None:
    """Write JSONL records to a file."""
    path.write_text(
        "".join(json.dumps(r, separators=(",", ":"), sort_keys=True) + "\n" for r in records),
        encoding="utf-8",
    )


def _read(path: Path) -> list[dict[str, object]]:
    """Read JSONL records back into Python dicts."""
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _materialize(records: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    """Latest-record-per-id (all test fixtures use string ids)."""
    return {str(r["id"]): r for r in records}


def test_converts_bare_string_depends_on_to_typed_local(*, tmp_path: Path) -> None:
    """Bare-string depends_on becomes {kind: local, work_item_id: <id>}."""
    path = tmp_path / "work-items.jsonl"
    _write(
        path,
        [
            {"id": "a", "status": "closed", "depends_on": []},
            {"id": "b", "status": "open", "depends_on": ["a"]},
        ],
    )
    migrated = migration.migrate_file(path=path)
    assert migrated == 1
    index = _materialize(_read(path))
    assert index["b"]["depends_on"] == [{"kind": "local", "work_item_id": "a"}]


def test_merges_blocked_by_into_depends_on(*, tmp_path: Path) -> None:
    """blocked_by entries are merged into depends_on; blocked_by dropped."""
    path = tmp_path / "work-items.jsonl"
    _write(
        path,
        [
            {"id": "a", "status": "open", "depends_on": [], "blocked_by": ["x", "y"]},
        ],
    )
    migrated = migration.migrate_file(path=path)
    assert migrated == 1
    index = _materialize(_read(path))
    assert "blocked_by" not in index["a"]
    assert index["a"]["depends_on"] == [
        {"kind": "local", "work_item_id": "x"},
        {"kind": "local", "work_item_id": "y"},
    ]


def test_deduplicates_overlap_between_depends_on_and_blocked_by(*, tmp_path: Path) -> None:
    """An id present in both depends_on and blocked_by lands once."""
    path = tmp_path / "work-items.jsonl"
    _write(
        path,
        [
            {"id": "a", "status": "open", "depends_on": ["x"], "blocked_by": ["x", "y"]},
        ],
    )
    migrated = migration.migrate_file(path=path)
    assert migrated == 1
    index = _materialize(_read(path))
    assert index["a"]["depends_on"] == [
        {"kind": "local", "work_item_id": "x"},
        {"kind": "local", "work_item_id": "y"},
    ]


def test_already_typed_records_pass_through(*, tmp_path: Path) -> None:
    """Records already in the typed form are not re-emitted."""
    path = tmp_path / "work-items.jsonl"
    _write(
        path,
        [
            {"id": "a", "status": "open", "depends_on": [{"kind": "local", "work_item_id": "x"}]},
        ],
    )
    migrated = migration.migrate_file(path=path)
    assert migrated == 0
    # File is unchanged byte-for-byte.
    records = _read(path)
    assert len(records) == 1
    assert records[0]["depends_on"] == [{"kind": "local", "work_item_id": "x"}]


def test_dry_run_does_not_write(*, tmp_path: Path) -> None:
    """--dry-run reports the count without modifying the file."""
    path = tmp_path / "work-items.jsonl"
    original = [{"id": "a", "status": "open", "depends_on": ["b"]}]
    _write(path, original)
    before = path.read_text()
    migrated = migration.migrate_file(path=path, dry_run=True)
    assert migrated == 1
    assert path.read_text() == before


def test_preserves_append_only_history(*, tmp_path: Path) -> None:
    """Existing records (legacy + transitions) are preserved; transitions appended."""
    path = tmp_path / "work-items.jsonl"
    _write(
        path,
        [
            {"id": "a", "status": "open", "depends_on": ["b"]},  # legacy
            {"id": "a", "status": "in_progress", "depends_on": ["b"]},  # legacy transition
        ],
    )
    initial_lines = path.read_text().splitlines()
    migrated = migration.migrate_file(path=path)
    assert migrated == 1
    final_lines = path.read_text().splitlines()
    # Initial two lines preserved verbatim.
    assert final_lines[: len(initial_lines)] == initial_lines
    # A transition record appended.
    assert len(final_lines) == len(initial_lines) + 1
    transition = json.loads(final_lines[-1])
    assert transition["id"] == "a"
    assert transition["status"] == "in_progress"  # latest materialized status
    assert transition["depends_on"] == [{"kind": "local", "work_item_id": "b"}]


def test_main_dry_run_returns_zero(*, tmp_path: Path, capsys) -> None:
    """CLI dry-run returns 0 and reports the would-migrate count."""
    path = tmp_path / "work-items.jsonl"
    _write(path, [{"id": "a", "status": "open", "depends_on": ["b"]}])
    rc = migration.main(argv=["--path", str(path), "--dry-run"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "would migrate 1 record" in out


def test_main_missing_path_returns_one(*, tmp_path: Path, capsys) -> None:
    """CLI returns 1 (with stderr message) when --path doesn't exist."""
    rc = migration.main(argv=["--path", str(tmp_path / "missing.jsonl")])
    err = capsys.readouterr().err
    assert rc == 1
    assert "does not exist" in err


def test_typed_entry_passes_through_in_mixed_record(*, tmp_path: Path) -> None:
    """A record with both bare-strings AND already-typed entries preserves typed entries verbatim."""
    path = tmp_path / "work-items.jsonl"
    typed_entry = {"kind": "pull_request", "repo": "runtime", "number": 5}
    _write(
        path,
        [
            {"id": "a", "status": "open", "depends_on": ["b", typed_entry]},
        ],
    )
    migrated = migration.migrate_file(path=path)
    assert migrated == 1
    index = _materialize(_read(path))
    assert index["a"]["depends_on"] == [
        {"kind": "local", "work_item_id": "b"},
        typed_entry,
    ]


def test_tolerates_blank_lines_and_no_id_lines(*, tmp_path: Path) -> None:
    """Blank lines and lines without `id` are silently skipped during materialization."""
    path = tmp_path / "work-items.jsonl"
    # Hand-craft a JSONL that contains blank lines + a no-id line.
    raw = "\n" '{"no_id":"field-only"}\n' '{"id":"a","status":"open","depends_on":["b"]}\n' "\n"
    _ = path.write_text(raw, encoding="utf-8")
    migrated = migration.migrate_file(path=path)
    assert migrated == 1


def test_appends_trailing_newline_when_missing(*, tmp_path: Path) -> None:
    """When the last line lacks a trailing newline, the migration normalizes it before appending."""
    path = tmp_path / "work-items.jsonl"
    # Hand-craft a file whose last line has no trailing newline.
    raw = '{"id":"a","status":"open","depends_on":["b"]}'
    _ = path.write_text(raw, encoding="utf-8")
    migrated = migration.migrate_file(path=path)
    assert migrated == 1
    final = path.read_text(encoding="utf-8")
    # All lines end with newline now.
    for line in final.splitlines(keepends=True):
        assert line.endswith("\n")

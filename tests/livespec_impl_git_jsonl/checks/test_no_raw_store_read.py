"""Tests for the `check-no-raw-store-read` store-integrity check.

Per SPECIFICATION/contracts.md §"Append-only store disciplines" →
"Store-integrity checks (orchestrator-private)" and "Read path only via
the query surface": the check fires fail when shipped code opens a
declared backing store path directly, bypassing the reducer/query
surface. Scope is committed code under the shipped trees — the rule
cannot police ad-hoc interactive shell reads (the self-identification
and order-independent-reduction obligations defend that residual
surface).
"""

from pathlib import Path

import pytest
from livespec_impl_git_jsonl.checks.no_raw_store_read import main

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _write_module(*, root: Path, relative: str, source: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(source, encoding="utf-8")


def _fixture_root(*, tmp_path: Path) -> Path:
    """A minimal conforming shipped tree (canonical store module only)."""
    root = tmp_path / "project"
    _write_module(
        root=root,
        relative=".claude-plugin/scripts/livespec_impl_git_jsonl/store.py",
        source=(
            "from pathlib import Path\n"
            "\n"
            "\n"
            "def read_raw(*, path: Path) -> str:\n"
            '    with Path("work-items.jsonl").open(encoding="utf-8") as handle:\n'
            "        return handle.read()\n"
        ),
    )
    return root


def test_main_passes_on_conforming_tree(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = _fixture_root(tmp_path=tmp_path)
    _write_module(
        root=root,
        relative=".claude-plugin/scripts/livespec_impl_git_jsonl/clean.py",
        source=(
            "from pathlib import Path\n"
            "\n"
            "\n"
            "def read_notes(*, path: Path) -> str:\n"
            '    return path.read_text(encoding="utf-8")\n'
        ),
    )
    rc = main(argv=["--root", str(root)])
    captured = capsys.readouterr()
    assert rc == 0
    assert "OK" in captured.out


def test_main_exempts_the_canonical_store_module(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = _fixture_root(tmp_path=tmp_path)
    rc = main(argv=["--root", str(root)])
    captured = capsys.readouterr()
    assert rc == 0
    assert "store.py" not in captured.out


def test_main_fails_on_literal_store_basename_open(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = _fixture_root(tmp_path=tmp_path)
    _write_module(
        root=root,
        relative=".claude-plugin/scripts/livespec_impl_git_jsonl/offender.py",
        source=(
            "from pathlib import Path\n"
            "\n"
            "\n"
            "def sneaky_read(*, root: Path) -> str:\n"
            '    return (root / "work-items.jsonl").read_text(encoding="utf-8")\n'
        ),
    )
    rc = main(argv=["--root", str(root)])
    captured = capsys.readouterr()
    assert rc == 1
    assert "offender.py:5" in captured.out
    assert "work-items.jsonl" in captured.out
    assert "FAIL" in captured.out


def test_main_fails_on_declared_path_attribute_open(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = _fixture_root(tmp_path=tmp_path)
    _write_module(
        root=root,
        relative=".claude-plugin/scripts/livespec_impl_git_jsonl/attr_offender.py",
        source=(
            "def sneaky_read(*, config: object) -> str:\n"
            "    return config.work_items_path.read_text(encoding='utf-8')\n"
        ),
    )
    rc = main(argv=["--root", str(root)])
    captured = capsys.readouterr()
    assert rc == 1
    assert "attr_offender.py:2" in captured.out
    assert "work_items_path" in captured.out


def test_main_fails_on_builtin_open_of_declared_path_name(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = _fixture_root(tmp_path=tmp_path)
    _write_module(
        root=root,
        relative="dev-tooling/open_offender.py",
        source=(
            "def sneaky_read(*, work_items_path: str) -> str:\n"
            "    with open(work_items_path, encoding='utf-8') as handle:\n"
            "        return handle.read()\n"
        ),
    )
    rc = main(argv=["--root", str(root)])
    captured = capsys.readouterr()
    assert rc == 1
    assert "open_offender.py:2" in captured.out


def test_main_ignores_vendored_code(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = _fixture_root(tmp_path=tmp_path)
    _write_module(
        root=root,
        relative=".claude-plugin/scripts/_vendor/somelib/reader.py",
        source=(
            "from pathlib import Path\n"
            "\n"
            "\n"
            "def vendored_read(*, root: Path) -> str:\n"
            '    return (root / "work-items.jsonl").read_text(encoding="utf-8")\n'
        ),
    )
    rc = main(argv=["--root", str(root)])
    captured = capsys.readouterr()
    assert rc == 0
    assert "OK" in captured.out


def test_main_ignores_non_open_calls_and_unrelated_literals(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = _fixture_root(tmp_path=tmp_path)
    _write_module(
        root=root,
        relative=".claude-plugin/scripts/livespec_impl_git_jsonl/benign.py",
        source=(
            "def helper(*, callbacks: list[object]) -> object:\n"
            '    name = str("work-items.jsonl")\n'
            '    result = callbacks[0]("notes.txt")\n'
            "    numbered = open(__file__, buffering=8)\n"
            "    return (name, result, numbered)\n"
        ),
    )
    rc = main(argv=["--root", str(root)])
    captured = capsys.readouterr()
    assert rc == 0
    assert "OK" in captured.out


def test_main_passes_when_shipped_trees_absent(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = tmp_path / "empty-project"
    root.mkdir()
    rc = main(argv=["--root", str(root)])
    captured = capsys.readouterr()
    assert rc == 0
    assert "OK" in captured.out


def test_main_conformance_run_against_this_repo(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = main(argv=["--root", str(_REPO_ROOT)])
    captured = capsys.readouterr()
    assert rc == 0
    assert "OK" in captured.out

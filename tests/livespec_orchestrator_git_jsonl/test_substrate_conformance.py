"""Substrate-identity conformance for the JSONL realization.

These pin the observable properties SPECIFICATION/spec.md and
SPECIFICATION/constraints.md name as unique to this plugin: the
substrate is plain, database-free JSONL a user can read line by line;
runtime dependencies are vendored rather than declared; and the JSONL
stores carry the merge=union attribute that makes git the conflict
boundary.
"""

import json
from pathlib import Path

from livespec_orchestrator_git_jsonl.store import append_work_item, read_work_items
from livespec_orchestrator_git_jsonl.types import WorkItem
from returns.io import IOSuccess

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _item(*, id_: str) -> WorkItem:
    return WorkItem(
        id=id_,
        type="task",
        status="ready",  # type: ignore[arg-type]
        title=f"{id_} title",
        description="d",
        origin="freeform",
        gap_id=None,
        rank="a1",
        assignee=None,
        depends_on=(),
        captured_at="2026-05-19T00:00:00Z",
        resolution=None,
        reason=None,
        audit=None,
        superseded_by=None,
    )


def test_the_substrate_is_plain_jsonl_readable_without_a_database(tmp_path: Path) -> None:
    """spec.md Purpose: the substrate is plain JSONL, no embedded database.

    Two appended records land as two plain-text lines, each an
    independent JSON object recoverable with a plain reader — the
    "nothing the user can't read with cat" property the Purpose section
    rests on. Control: a binary/database substrate would not round-trip
    through json.loads over the raw lines.
    """
    path = tmp_path / "work-items.jsonl"
    append_work_item(path=path, item=_item(id_="li-aaa111"))
    append_work_item(path=path, item=_item(id_="li-bbb222"))
    raw = path.read_text(encoding="utf-8")
    assert raw.endswith("\n")
    lines = raw.splitlines()
    assert len(lines) == 2
    ids = [json.loads(line)["id"] for line in lines]
    assert ids == ["li-aaa111", "li-bbb222"]
    reduced = read_work_items(path=path)
    assert isinstance(reduced, IOSuccess)


def test_no_pypi_runtime_dependencies_are_declared() -> None:
    """constraints.md "Inherited from livespec": deps are vendored, not declared.

    The inherited constraint forbids PyPI runtime dependencies; libraries
    are vendored under `.claude-plugin/scripts/_vendor/`. Control: a
    populated `[project].dependencies` array, or a missing vendor tree,
    would fail.
    """
    lines = [
        line.strip()
        for line in (_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8").splitlines()
    ]
    assert "[project.dependencies]" not in lines
    assert not any(line.startswith("dependencies =") for line in lines)
    assert (_REPO_ROOT / ".claude-plugin" / "scripts" / "_vendor").is_dir()


def test_jsonl_stores_declare_merge_union_so_git_is_the_conflict_boundary() -> None:
    """constraints.md "Process boundaries": git serialization resolves races.

    The plugin adds no lockfile; concurrent appends are reconciled by git.
    The enabling mechanism is the `*.jsonl merge=union` gitattribute.
    Control: removing the attribute would fail this assertion.
    """
    attributes = (_REPO_ROOT / ".gitattributes").read_text(encoding="utf-8")
    assert "*.jsonl merge=union" in attributes

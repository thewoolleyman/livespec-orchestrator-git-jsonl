"""Tests for the needs-attention thin binding."""

import json
import shlex
from pathlib import Path

import pytest
from livespec_orchestrator_git_jsonl.commands import needs_attention
from livespec_orchestrator_git_jsonl.commands.needs_attention import (
    CoreRootBases,
    SpecNextSeam,
    _adapt_top_candidate,
    _candidate_urgency,
    _claude_installed_core_roots,
    _codex_installed_core_roots,
    _read_spec_clis_next_argv,
    _resolve_core_plugin_root,
    _resolve_spec_next_command,
    _spec_next,
    _spec_output_from_candidate,
    _SpecNextResult,
    build_attention,
    main,
    render_json,
    render_markdown,
)
from livespec_orchestrator_git_jsonl.store import append_work_item
from livespec_orchestrator_git_jsonl.types import WorkItem
from livespec_runtime.needs_attention import SpecNextOutput


def _stub_spec_output() -> SpecNextOutput:
    return SpecNextOutput(
        op="revise",
        spec_target="SPECIFICATION",
        summary="Revise a pending proposed change.",
        command="codex exec livespec:revise --project-root /workspace/repo",
        urgency="medium",
    )


def _stub_spec_next(monkeypatch: pytest.MonkeyPatch, *, output: SpecNextOutput | None) -> None:
    def _fake(*, project_root: Path) -> SpecNextOutput | None:
        _ = project_root
        return output

    monkeypatch.setattr(needs_attention, "_spec_next", _fake)


def _seam(
    *,
    command: list[str] | None,
    result: _SpecNextResult | None = None,
    raises: Exception | None = None,
    calls: dict[str, object] | None = None,
) -> SpecNextSeam:
    def _resolve(*, project_root: Path) -> list[str] | None:
        _ = project_root
        return command

    def _run(*, argv: list[str]) -> _SpecNextResult:
        if calls is not None:
            calls["argv"] = argv
            calls["run"] = True
        if raises is not None:
            raise raises
        assert result is not None
        return result

    return SpecNextSeam(resolve_command=_resolve, run=_run)


def _item(
    *,
    id_: str,
    status: str,
    rank: str = "a2",
    blocked_reason: str | None = None,
    factory_safety: str | None = None,
) -> WorkItem:
    return WorkItem(
        id=id_,
        type="task",
        status=status,  # type: ignore[arg-type]
        title=f"{id_} title",
        description="d",
        origin="freeform",
        gap_id=None,
        rank=rank,
        assignee=None,
        depends_on=(),
        captured_at="2026-05-19T00:00:00Z",
        resolution=None,
        reason=None,
        audit=None,
        superseded_by=None,
        blocked_reason=blocked_reason,  # type: ignore[arg-type]
        factory_safety=factory_safety,  # type: ignore[arg-type]
    )


def test_build_attention_composes_available_git_jsonl_primitives(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_spec_next(monkeypatch, output=_stub_spec_output())
    path = tmp_path / "work-items.jsonl"
    append_work_item(path=path, item=_item(id_="gj-ready", status="ready", rank="a1"))
    append_work_item(path=path, item=_item(id_="gj-approval", status="pending-approval"))
    append_work_item(path=path, item=_item(id_="gj-accept", status="acceptance", rank="a3"))
    append_work_item(
        path=path,
        item=_item(id_="gj-block", status="blocked", rank="a4", blocked_reason="needs-human"),
    )

    attention = build_attention(
        project_root=tmp_path,
        repo_name="repo",
        work_items_path=str(path),
        include_hygiene=False,
    )

    assert [item.id for item in attention] == [
        "valve:approve:gj-approval",
        "valve:accept:gj-accept",
        "valve:set-admission:gj-block",
        "impl:gj-ready",
        "spec:revise:SPECIFICATION",
    ]
    assert {item.kind for item in attention} == {"human-valve", "impl", "spec"}
    assert "plan:needs-attention" not in [item.id for item in attention]
    assert attention[0].handoff.action_id == "approve:gj-approval"
    assert "list-work-items" in attention[0].handoff.command
    assert "next" in attention[3].handoff.command


def test_build_attention_drops_spec_item_when_spec_next_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_spec_next(monkeypatch, output=None)

    attention = build_attention(project_root=tmp_path, repo_name="repo", include_hygiene=False)

    assert [item.kind for item in attention if item.kind == "spec"] == []


def test_build_attention_surfaces_not_factory_safe_items(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_spec_next(monkeypatch, output=None)
    path = tmp_path / "work-items.jsonl"
    append_work_item(
        path=path,
        item=_item(
            id_="gj-host",
            status="ready",
            factory_safety="needs-host-secrets",
        ),
    )

    attention = build_attention(
        project_root=tmp_path,
        repo_name="repo",
        work_items_path=str(path),
        include_hygiene=False,
    )

    host_only = [item for item in attention if item.kind == "host-only"]
    assert len(host_only) == 1
    assert host_only[0].id == "host-only:factory-safety:gj-host"
    assert host_only[0].source_ref.work_item == "gj-host"
    assert host_only[0].handoff.kind == "shell"
    assert "list-work-items" in host_only[0].handoff.command


def test_build_attention_omits_not_factory_safe_item_from_impl_lane(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A not-factory-safe item is host-routed, never recommended for dispatch.

    Parity with the beads-fabro sibling, whose `impl_next` filters
    `factory_safety is None` at the same call site. Without this the same
    work-item is surfaced BOTH as `host-only` ("do not dispatch") and as
    `impl` ("drive this next") in one output. git-jsonl runs no dispatcher,
    so no admission gate backstops a wrong recommendation.
    """
    _stub_spec_next(monkeypatch, output=None)
    path = tmp_path / "work-items.jsonl"
    # gj-host outranks gj-safe, so it would win the impl lane if not filtered.
    append_work_item(
        path=path,
        item=_item(id_="gj-host", status="ready", factory_safety="needs-host-secrets"),
    )
    append_work_item(path=path, item=_item(id_="gj-safe", status="ready", rank="a5"))

    attention = build_attention(
        project_root=tmp_path,
        repo_name="repo",
        work_items_path=str(path),
        include_hygiene=False,
    )

    impl = [item for item in attention if item.kind == "impl"]
    assert [item.source_ref.work_item for item in impl] == ["gj-safe"]


def test_render_json_wraps_flat_attention_array(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_spec_next(monkeypatch, output=_stub_spec_output())
    attention = build_attention(project_root=tmp_path, repo_name="repo", include_hygiene=False)

    payload = json.loads(render_json(attention=attention))

    assert list(payload) == ["attention"]
    assert payload["attention"][0]["id"] == "spec:revise:SPECIFICATION"


def test_render_markdown_lists_handoff_commands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_spec_next(monkeypatch, output=_stub_spec_output())
    attention = build_attention(project_root=tmp_path, repo_name="repo", include_hygiene=False)

    rendered = render_markdown(attention=attention)

    assert rendered.startswith("# Needs Attention\n")
    assert "`spec:revise:SPECIFICATION`" in rendered
    assert "codex exec livespec:revise" in rendered


def test_render_markdown_empty_attention() -> None:
    assert render_markdown(attention=[]) == "No attention items.\n"


def test_main_json_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _stub_spec_next(monkeypatch, output=_stub_spec_output())
    rc = main(
        argv=["--json", "--skip-hygiene", "--project-root", str(tmp_path), "--repo-name", "repo"]
    )

    captured = capsys.readouterr()
    assert rc == 0
    assert json.loads(captured.out)["attention"][0]["id"] == "spec:revise:SPECIFICATION"


def test_main_markdown_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _stub_spec_next(monkeypatch, output=_stub_spec_output())
    rc = main(argv=["--skip-hygiene", "--project-root", str(tmp_path), "--repo-name", "repo"])

    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out.startswith("# Needs Attention\n")


def test_spec_next_inlines_top_actionable_candidate(tmp_path: Path) -> None:
    stdout = json.dumps(
        {
            "candidates": [
                {
                    "action": "revise",
                    "reason": "proposed change pending; queue depth 1",
                    "urgency": "high",
                    "target": "proposed_changes/owned-heading-coverage-todos.md",
                }
            ]
        }
    )
    calls: dict[str, object] = {}
    seam = _seam(
        command=["python3", "/core/scripts/bin/next.py"],
        result=_SpecNextResult(stdout=stdout, returncode=0),
        calls=calls,
    )

    output = _spec_next(project_root=tmp_path, seam=seam)

    assert output is not None
    assert output.op == "revise"
    assert output.spec_target == "proposed_changes/owned-heading-coverage-todos.md"
    assert output.summary == "proposed change pending; queue depth 1"
    assert output.urgency == "high"
    assert output.command == (
        f"codex exec livespec:revise --project-root {shlex.quote(str(tmp_path))}"
    )
    assert calls["argv"] == [
        "python3",
        "/core/scripts/bin/next.py",
        "--project-root",
        str(tmp_path),
    ]


def test_spec_next_returns_none_when_candidates_empty(tmp_path: Path) -> None:
    seam = _seam(
        command=["python3", "/core/next.py"],
        result=_SpecNextResult(stdout=json.dumps({"candidates": []}), returncode=0),
    )
    assert _spec_next(project_root=tmp_path, seam=seam) is None


def test_spec_next_returns_none_when_seam_run_raises(tmp_path: Path) -> None:
    seam = _seam(
        command=["python3", "/core/next.py"],
        raises=OSError("boom"),
    )
    assert _spec_next(project_root=tmp_path, seam=seam) is None


def test_spec_next_returns_none_when_cli_exits_nonzero(tmp_path: Path) -> None:
    seam = _seam(
        command=["python3", "/core/next.py"],
        result=_SpecNextResult(stdout="", returncode=2),
    )
    assert _spec_next(project_root=tmp_path, seam=seam) is None


def test_spec_next_returns_none_when_stdout_unparseable(tmp_path: Path) -> None:
    seam = _seam(
        command=["python3", "/core/next.py"],
        result=_SpecNextResult(stdout="not json", returncode=0),
    )
    assert _spec_next(project_root=tmp_path, seam=seam) is None


def test_spec_next_does_not_run_cli_when_unresolvable(tmp_path: Path) -> None:
    calls: dict[str, object] = {}
    seam = _seam(command=None, result=_SpecNextResult(stdout="{}", returncode=0), calls=calls)

    assert _spec_next(project_root=tmp_path, seam=seam) is None
    assert "run" not in calls


@pytest.mark.parametrize(
    ("value", "expected"),
    [("high", "high"), ("low", "low"), ("medium", "medium"), ("bogus", "medium")],
)
def test_candidate_urgency(value: object, expected: str) -> None:
    assert _candidate_urgency(value=value) == expected


def test_spec_output_from_candidate_defaults_summary_and_target(tmp_path: Path) -> None:
    output = _spec_output_from_candidate(candidate={"action": "critique"}, project_root=tmp_path)
    assert output is not None
    assert output.summary == "Spec-side critique is ready."
    assert output.spec_target == "SPECIFICATION"
    assert output.urgency == "medium"
    assert output.command == (
        f"codex exec livespec:critique --project-root {shlex.quote(str(tmp_path))}"
    )


def test_spec_output_from_candidate_non_actionable_returns_none(tmp_path: Path) -> None:
    assert _spec_output_from_candidate(candidate="x", project_root=tmp_path) is None
    assert _spec_output_from_candidate(candidate={"reason": "r"}, project_root=tmp_path) is None
    assert _spec_output_from_candidate(candidate={"action": "none"}, project_root=tmp_path) is None


def test_adapt_top_candidate_skips_inert_then_selects_actionable(tmp_path: Path) -> None:
    stdout = json.dumps(
        {
            "candidates": [
                "not-a-dict",
                {"action": "none", "reason": "nothing"},
                {"action": "propose-change", "reason": "gap found", "urgency": "medium"},
            ]
        }
    )
    output = _adapt_top_candidate(stdout=stdout, project_root=tmp_path)
    assert output is not None
    assert output.op == "propose-change"


def test_adapt_top_candidate_invalid_payloads_return_none(tmp_path: Path) -> None:
    assert _adapt_top_candidate(stdout='"a string"', project_root=tmp_path) is None
    assert _adapt_top_candidate(stdout='{"candidates": {}}', project_root=tmp_path) is None


def _plant_next(root: Path) -> Path:
    (root / "scripts" / "bin").mkdir(parents=True)
    _ = (root / "scripts" / "bin" / "next.py").write_text("# core next\n", encoding="utf-8")
    return root


def _empty_bases(tmp_path: Path) -> CoreRootBases:
    return CoreRootBases(
        claude_registry=tmp_path / "no-claude" / "installed_plugins.json",
        codex_cache=tmp_path / "no-codex-cache",
    )


def test_resolve_core_root_prefers_fleet_sibling(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    sibling = _plant_next(workspace / "livespec" / ".claude-plugin")
    project = workspace / "governed"
    project.mkdir(parents=True)

    assert _resolve_core_plugin_root(project_root=project, bases=_empty_bases(tmp_path)) == sibling


def test_resolve_core_root_uses_claude_installed_cache(tmp_path: Path) -> None:
    core = _plant_next(tmp_path / "claude-cache" / "livespec")
    registry = tmp_path / "installed_plugins.json"
    _ = registry.write_text(
        json.dumps({"plugins": {"livespec@livespec": [{"installPath": str(core)}]}}),
        encoding="utf-8",
    )
    bases = CoreRootBases(claude_registry=registry, codex_cache=tmp_path / "no-codex")
    project = tmp_path / "governed"
    project.mkdir()

    assert _resolve_core_plugin_root(project_root=project, bases=bases) == core


def test_resolve_core_root_uses_codex_installed_cache(tmp_path: Path) -> None:
    codex_cache = tmp_path / "codex-cache"
    core = _plant_next(codex_cache / "livespec" / "livespec" / "0.7.1")
    bases = CoreRootBases(claude_registry=tmp_path / "missing.json", codex_cache=codex_cache)
    project = tmp_path / "governed"
    project.mkdir()

    assert _resolve_core_plugin_root(project_root=project, bases=bases) == core


def test_resolve_core_root_codex_cache_picks_highest_version(tmp_path: Path) -> None:
    codex_cache = tmp_path / "codex-cache"
    _ = _plant_next(codex_cache / "livespec" / "livespec" / "0.7.1")
    highest = _plant_next(codex_cache / "livespec" / "livespec" / "0.10.0")
    (codex_cache / "livespec" / "livespec" / "main").mkdir()
    bases = CoreRootBases(claude_registry=tmp_path / "missing.json", codex_cache=codex_cache)
    project = tmp_path / "governed"
    project.mkdir()

    assert _resolve_core_plugin_root(project_root=project, bases=bases) == highest


def test_resolve_core_root_none_when_all_tiers_miss(tmp_path: Path) -> None:
    project = tmp_path / "governed"
    project.mkdir()

    assert _resolve_core_plugin_root(project_root=project, bases=_empty_bases(tmp_path)) is None


def test_claude_installed_core_roots_yields_install_paths(tmp_path: Path) -> None:
    registry = tmp_path / "installed_plugins.json"
    _ = registry.write_text(
        json.dumps(
            {"plugins": {"livespec@livespec": [{"installPath": "/a"}, {"installPath": "/b"}]}}
        ),
        encoding="utf-8",
    )
    assert list(_claude_installed_core_roots(registry=registry)) == [Path("/a"), Path("/b")]


def test_claude_installed_core_roots_malformed_yields_nothing(tmp_path: Path) -> None:
    registry = tmp_path / "installed_plugins.json"
    _ = registry.write_text("{ not json", encoding="utf-8")
    assert list(_claude_installed_core_roots(registry=registry)) == []


def test_codex_installed_core_roots_yields_version_dirs_highest_first(tmp_path: Path) -> None:
    base = tmp_path / "cache" / "livespec" / "livespec"
    (base / "0.7.1").mkdir(parents=True)
    (base / "0.10.0").mkdir()

    roots = list(_codex_installed_core_roots(cache=tmp_path / "cache"))

    assert roots == [base / "0.10.0", base / "0.7.1"]


def test_read_spec_clis_next_argv_missing_file(tmp_path: Path) -> None:
    assert _read_spec_clis_next_argv(project_root=tmp_path) is None


def test_read_spec_clis_next_argv_returns_configured_argv(tmp_path: Path) -> None:
    _ = (tmp_path / ".livespec.jsonc").write_text(
        '{"spec_clis": {"next": ["python3", "/abs/next.py"]}}', encoding="utf-8"
    )
    assert _read_spec_clis_next_argv(project_root=tmp_path) == ["python3", "/abs/next.py"]


def test_resolve_spec_next_command_none_when_core_unresolvable(tmp_path: Path) -> None:
    project = tmp_path / "governed"
    project.mkdir()
    assert _resolve_spec_next_command(project_root=project, bases=_empty_bases(tmp_path)) is None


def test_resolve_spec_next_command_substitutes_default_template(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    sibling = _plant_next(workspace / "livespec" / ".claude-plugin")
    project = workspace / "governed"
    project.mkdir(parents=True)

    command = _resolve_spec_next_command(project_root=project, bases=_empty_bases(tmp_path))

    assert command == ["python3", f"{sibling}/scripts/bin/next.py"]

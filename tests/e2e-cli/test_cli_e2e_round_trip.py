"""CLI end-to-end harness wiring for livespec-orchestrator-git-jsonl (mock tier).

Per `livespec/SPECIFICATION/contracts.md`
(requirement 6 — single canonical implementation in `livespec-dev-tooling`;
requirement 7 — consumer obligations), this repo consumes the imported
`test_workflow_full_round_trip` entry point from
`livespec_dev_tooling.testing.cli_e2e` (shipped at dev-tooling v0.8.0) and
wires it into its own pytest collection against this plugin's per-skill
fixtures under `tests/e2e-cli/fixtures/`.

This is the **mock tier** (`LIVESPEC_E2E_HARNESS=mock`, the default): real
install-shape setup, real structural skill discovery over the on-disk
`.claude-plugin/` tree, the real fail-closed time-bomb coverage gate, and the
real per-skill orchestration loop all run — the ONLY mocked boundary is the
`claude -p` subprocess itself (the `CliRunner` seam), supplied here as a
deterministic injected runner that materializes each fixture's expected files.
The `real` tier (`LIVESPEC_E2E_HARNESS=real`) shells out to the actual
`claude` binary, requires `ANTHROPIC_API_KEY`, installs the upstream
`livespec` plugin paired in lockstep, and is NOT part of `just check`.

The plugin slash-command prefix (`livespec-orchestrator-git-jsonl`) and the skill set
are discovered structurally from `<plugin>/plugin.json` `name` + the
`skills/*/SKILL.md` layout — there is no parallel manifest (contract
requirement 3). Every discovered skill MUST carry a fixture or the coverage
gate fails the run; no skill is exempt (`EXEMPT_SKILLS` is empty).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from livespec_dev_tooling.testing import cli_e2e
from livespec_dev_tooling.testing.cli_e2e import CliResult, FixturedSkill, HarnessConfig

_VENDOR_DIR = Path(cli_e2e.__file__).resolve().parent.parent / "_vendor"
if str(_VENDOR_DIR) not in sys.path:
    sys.path.insert(0, str(_VENDOR_DIR))

from returns.primitives.exceptions import (  # noqa: E402  — vendor-path-aware import.
    UnwrapFailedError,
)
from returns.result import Failure, Success  # noqa: E402  — vendor-path-aware import.

# The canonical entry point is named `test_workflow_full_round_trip` (fixed by
# the contract's consumer import path). Importing that bare `test_*` name into
# a pytest module would make pytest try to COLLECT it as a test with a missing
# `config` fixture — so it is aliased here under a non-`test_`-prefixed name
# and invoked explicitly from the wrapper test below.
run_full_round_trip = cli_e2e.test_workflow_full_round_trip


def _round_trip_result(outcome: object) -> cli_e2e.WorkflowResult:
    """Normalize BOTH harness return shapes so the dev-tooling pin can move either way.

    Through `v1.0.x`, `test_workflow_full_round_trip` RAISED `WorkflowFailedError`
    on a failing step and returned a bare `WorkflowResult`. After the ROP
    conversion in dev-tooling it returns a `Result[WorkflowResult, ...]` instead.

    *** THE FAILURE THIS EXISTS TO PREVENT IS SILENT. *** A `Failure` is TRUTHY and
    carries no `.passed`, so a wrapper written for the old shape does NOT blow up
    against the new one — it simply STOPS CHECKING, and this suite goes GREEN on a
    broken round trip. That is `livespec-dev-tooling-dx8l`'s failure mode aimed at
    a test gate: the guard does not fail, it stops being a guard. This repo is the
    one whose master dx8l actually reddened, so the shape is not hypothetical here.

    Accepting BOTH shapes satisfies "consumer wiring lands before the change that
    assumes it" for EVERY pin version at once, so the pin can move in either
    direction — forward to the conversion or back on a revert — without re-breaking.

    Duck-typed on purpose: the helper must not depend on dev-tooling's vendored
    `returns` layout at call time, since it has to work across pin versions on
    both sides of the conversion. The tests below pin the REAL `Success`/`Failure`
    shapes, so the tolerance is proven rather than assumed.
    """
    if isinstance(outcome, cli_e2e.WorkflowResult):
        return outcome  # pre-conversion shape; a failing step would already have raised
    unwrap = getattr(outcome, "unwrap", None)
    assert unwrap is not None, (
        f"unexpected harness return shape {type(outcome).__name__}; "
        "expected a WorkflowResult or a returns Result"
    )
    # `.unwrap()` RAISES on a Failure, so a failed round trip fails this test LOUDLY
    # rather than passing silently. Asserting on the unwrapped VALUE is the point:
    # proving the call succeeded is exactly what the silent-pass bug also does.
    unwrapped = unwrap()
    assert isinstance(
        unwrapped, cli_e2e.WorkflowResult
    ), f"harness Result carried {type(unwrapped).__name__}, not a WorkflowResult"
    return unwrapped


__all__: list[str] = []


# Repo-root-relative anchors: this file lives at
# `<repo>/tests/e2e-cli/test_cli_e2e_round_trip.py`, so the repo root is three
# parents up. The installed-plugin location discovery walks is this repo's own
# `.claude-plugin/` tree (its `plugin.json` + `skills/*/SKILL.md`); the
# fixtures root is the sibling `fixtures/` directory next to this file.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_PLUGIN_DIR = _REPO_ROOT / ".claude-plugin"
_FIXTURES_ROOT = Path(__file__).resolve().parent / "fixtures"

# No skill is exempt: every discovered impl-git-jsonl skill MUST carry a
# fixture (contract requirement 5). An empty exempt table keeps the time-bomb
# coverage gate fully armed — adding a new skill to the plugin trips it until a
# fixture directory lands here.
_EXEMPT_SKILLS: frozenset[str] = frozenset()


class _MaterializingCliRunner:
    """The injected `claude -p` seam — the one mocked boundary (mock tier).

    A real `claude -p <prompt>` run of each skill's slash command would create
    that skill's output artifacts; this deterministic stand-in reads each
    fixture's declared `expected_files` and materializes exactly those paths
    under the run's `cwd` (the tmp `project_root`), then returns a successful
    `CliResult`. Everything else in the harness — discovery, fixture loading,
    the coverage gate, the orchestration loop — runs for real against on-disk
    trees. The per-skill expected-file map is built from the loaded fixtures so
    the stand-in stays in lockstep with the fixture set with no duplication.
    """

    def __init__(self, *, expected_by_prompt: dict[str, tuple[str, ...]]) -> None:
        self._expected_by_prompt = expected_by_prompt

    def run(
        self,
        *,
        prompt: str,
        home: Path,
        cwd: Path,
        resume_session_id: str | None,
    ) -> CliResult:
        # `home` is part of the `CliRunner` protocol signature (the real runner
        # sets `HOME=home` for the `claude` subprocess) but the mock tier never
        # shells out, so the tmp HOME is unused here; bind it to satisfy the
        # unused-argument lint (ARG002) without dropping the protocol parameter.
        _ = home
        for rel in self._expected_by_prompt.get(prompt, ()):
            target = cwd / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            _ = target.write_text("materialized by the mock-tier runner\n", encoding="utf-8")
        return CliResult(exit_code=0, stdout="", stderr="", session_id=resume_session_id)


def _expected_by_prompt(*, fixtures: dict[str, FixturedSkill]) -> dict[str, tuple[str, ...]]:
    """Map each fixture's prompt text → its declared expected-file tuple."""
    return {fixture.prompt: fixture.expected_files for fixture in fixtures.values()}


def _config() -> HarnessConfig:
    return HarnessConfig(
        impl_plugin_id="livespec-orchestrator-git-jsonl",
        marketplace="thewoolleyman/livespec-orchestrator-git-jsonl",
        enabled_plugins=(
            "livespec@livespec",
            "livespec-orchestrator-git-jsonl@livespec-orchestrator-git-jsonl",
        ),
        plugin_install_dirs=(_PLUGIN_DIR,),
        fixtures_root=_FIXTURES_ROOT,
        exempt_skills=_EXEMPT_SKILLS,
    )


def test_cli_e2e_round_trip_against_impl_git_jsonl(*, tmp_path: Path) -> None:
    """Drive the imported harness against this plugin's own fixtures (mock tier).

    Asserts the full discovery → coverage-gate → per-skill orchestration loop
    passes: every `/livespec-orchestrator-git-jsonl:*` skill discovered structurally
    from `.claude-plugin/` carries a fixture under `tests/e2e-cli/fixtures/`,
    and each skill's mock round-trip materializes its declared expected files
    and exits 0. `run_full_round_trip` raises `CoverageGateError` (fail-closed)
    on a fixture gap and `WorkflowFailedError` on any failing step, so a green
    run proves both the coverage gate is satisfied and every step round-trips.
    """
    config = _config()
    fixtures = cli_e2e.discover_fixtures(fixtures_root=config.fixtures_root)
    runner = _MaterializingCliRunner(expected_by_prompt=_expected_by_prompt(fixtures=fixtures))
    result = _round_trip_result(
        run_full_round_trip(
            config=config,
            home=tmp_path / "home",
            project_root=tmp_path / "project",
            injected_runner=runner,
        )
    )
    # The discovered skill set is exactly the fixtured skill set (the coverage
    # gate enforces no gaps); the round-trip passed every step.
    assert set(result.discovered_skills) == set(result.fixtured_skills)
    assert result.passed is True
    # Every discovered skill was driven (none silently skipped) — `next` is one
    # of the thin-transport skills and MUST appear among the run steps.
    driven = {step.skill for step in result.steps}
    assert driven == set(result.discovered_skills)
    assert "next" in driven


def test_round_trip_result_accepts_the_pre_conversion_shape() -> None:
    """A bare `WorkflowResult` passes straight through — the shape today's pin returns."""
    result = cli_e2e.WorkflowResult(discovered_skills=("next",), fixtured_skills=("next",))

    assert _round_trip_result(result) is result


def test_round_trip_result_unwraps_the_post_conversion_success_to_its_value() -> None:
    """A `Success` yields the WorkflowResult ITSELF, not the container.

    Asserting on the VALUE is the whole point. `frozenset(IOResult.unwrap())`
    silently yielding a set holding the wrapper — the bug that shipped in
    dev-tooling's own conversion — passes any test that only checks the call
    succeeded. A wrapper reaching the caller in place of its payload is exactly
    what this class of bug produces.
    """
    result = cli_e2e.WorkflowResult(discovered_skills=("next",), fixtured_skills=("next",))

    unwrapped = _round_trip_result(Success(result))

    assert unwrapped is result
    assert isinstance(unwrapped, cli_e2e.WorkflowResult)
    assert unwrapped.discovered_skills == ("next",)


def test_round_trip_result_fails_loudly_on_the_post_conversion_failure() -> None:
    """A `Failure` RAISES rather than passing.

    This is the assertion the whole helper exists for. A `Failure` is TRUTHY and
    has no `.passed`, so wiring written for the old shape would neither raise nor
    check — this suite would go green on a broken round trip.
    """
    with pytest.raises(UnwrapFailedError):
        _ = _round_trip_result(Failure(RuntimeError("two skills failed")))

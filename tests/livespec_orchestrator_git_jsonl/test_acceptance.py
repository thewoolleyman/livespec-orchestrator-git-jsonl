"""Tests for the golden-master acceptance harness."""

from pathlib import Path

from livespec_orchestrator_git_jsonl.acceptance import AcceptanceConfig, run_acceptance
from returns.io import IOFailure, IOSuccess
from returns.unsafe import unsafe_perform_io


def _seed_fixture(*, spec_root: Path) -> None:
    spec_root.mkdir(parents=True)
    _ = (spec_root / "spec.md").write_text(
        "\n".join(
            [
                "# hello-world-greets-a-name",
                "",
                "The generated program accepts one name and returns a greeting.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    _ = (spec_root / "contracts.md").write_text(
        "\n".join(
            [
                "# contracts.md",
                "",
                "The runtime behavior is exactly: `Hello, <name>!`.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    _ = (spec_root / "constraints.md").write_text(
        "# constraints.md\n\nNo network, credentials, or host services.\n",
        encoding="utf-8",
    )
    _ = (spec_root / "scenarios.md").write_text(
        "# scenarios.md\n\nWhen the supplied name is Ada, the greeting is `Hello, Ada!`.\n",
        encoding="utf-8",
    )


def test_acceptance_harness_materializes_and_checks_behavior(tmp_path: Path) -> None:
    spec_root = tmp_path / "fixture" / "SPECIFICATION"
    _seed_fixture(spec_root=spec_root)

    outcome = run_acceptance(
        config=AcceptanceConfig(
            spec_root=spec_root,
            workspace=tmp_path / "run",
            name="Ada",
        )
    )

    assert isinstance(outcome, IOSuccess)
    result = unsafe_perform_io(outcome.unwrap())
    assert result.fixture_name == "hello-world-greets-a-name"
    assert result.greeting == "Hello, Ada!"
    assert result.generated_program.read_text(encoding="utf-8") == (
        '"""Generated hello-world program."""\n\n'
        "def greet(name: str) -> str:\n"
        '    return f"Hello, {name}!"\n'
    )


def test_absent_fixture_reaches_the_caller_on_the_failure_track(tmp_path: Path) -> None:
    """A missing `spec.md` is an EXPECTED failure of this harness, not an escaping raise.

    The harness reads the fixture off disk, so an absent or unreadable
    fixture is an ordinary outcome of running one — the caller has to be
    able to see it without a `try`.
    """
    outcome = run_acceptance(
        config=AcceptanceConfig(
            spec_root=tmp_path / "absent" / "SPECIFICATION",
            workspace=tmp_path / "run",
            name="Ada",
        )
    )

    assert isinstance(outcome, IOFailure)
    assert isinstance(unsafe_perform_io(outcome.failure()), FileNotFoundError)

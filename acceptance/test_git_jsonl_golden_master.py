"""Golden-master acceptance test for the git-jsonl implementation."""

from pathlib import Path

from livespec_orchestrator_git_jsonl.acceptance import (
    AcceptanceConfig,
    run_acceptance,
)
from returns.io import IOSuccess
from returns.unsafe import unsafe_perform_io

__all__: list[str] = []


def _fixture_spec_root(*, fixture_name: str) -> Path:
    return Path("acceptance") / "fixtures" / fixture_name / "SPECIFICATION"


def test_git_jsonl_golden_master_generates_greeting_program(*, tmp_path: Path) -> None:
    outcome = run_acceptance(
        config=AcceptanceConfig(
            spec_root=_fixture_spec_root(fixture_name="hello-world-greets-a-name"),
            workspace=tmp_path / "run",
            name="Ada",
        )
    )

    assert isinstance(outcome, IOSuccess)
    result = unsafe_perform_io(outcome.unwrap())
    assert result.fixture_name == "hello-world-greets-a-name"
    assert result.greeting == "Hello, Ada!"
    assert result.generated_program.is_file()

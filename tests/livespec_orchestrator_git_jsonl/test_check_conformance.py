"""Conformance exercises that run an enforcing check-runner against this repo.

Each test invokes a real check-runner in-process (no subprocess, per the
tests-no-subprocess-spawn rule) against THIS repo's source and asserts a
clean verdict, then runs the same runner against a control-armed
violating fixture and asserts it reddens. This binds a spec heading to
the check that actually enforces it, verified against this repo rather
than only against the check's own synthetic fixtures.
"""

from pathlib import Path

import pytest
from livespec_dev_tooling.checks.skill_invocation_paths import main as skill_invocation_paths_main

_REPO_ROOT = Path(__file__).resolve().parents[2]


def test_skill_invocation_paths_clean_on_this_repo_and_catches_a_wrapper_path_shell_out(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """contracts.md "Cross-boundary handoffs": handoffs invoke via the canonical form.

    The handoff mechanism is namespace invocation, never a direct shell-out
    to a wrapper path. `skill_invocation_paths` enforces that every shipped
    SKILL.md uses the canonical wrapper-invocation form. This runs it against
    THIS repo (clean) and against a fixture whose SKILL.md hard-codes an
    `uv run .claude-plugin/scripts/bin/*.py` shell-out (reddens).
    """
    monkeypatch.chdir(_REPO_ROOT)
    assert skill_invocation_paths_main() == 0

    (tmp_path / ".claude-plugin" / "scripts").mkdir(parents=True)
    skill_dir = tmp_path / ".claude-plugin" / "skills" / "offender"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "# offender\n\n```bash\nuv run python .claude-plugin/scripts/bin/offender.py\n```\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    assert skill_invocation_paths_main() == 1

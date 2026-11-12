"""Controls for the delegated pre-push gate opt-in (bd-gj-cbbyic).

This repository opts in to livespec-dev-tooling's delegated pre-push gate. A push
from a host that can read the gates kubeconfig runs the delegation client in place
of `just check`; any other host (a Fabro sandbox) runs the gate locally and says so.
"""

from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest
from livespec_dev_tooling.config import load_delegated_gate
from livespec_dev_tooling.green_token import main as green_token_main

__all__: list[str] = []

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO_ROOT / "dev-tooling" / "just-check-pre-push.sh"
_CLIENT = "livespec_dev_tooling.gate_remote_delegate"
_AGGREGATE_TARGETS = re.compile(
    r"^check:\n.*?^    targets=\(\n(?P<targets>.*?)^    \)$", re.MULTILINE | re.DOTALL
)


def _write_executable(*, path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _scrub_coverage_env(*, env: dict[str, str]) -> dict[str, str]:
    return {
        key: value
        for key, value in env.items()
        if key != "COVERAGE_PROCESS_START" and not key.startswith("COV_CORE_")
    }


def _lines(*, path: Path) -> list[str]:
    if not path.exists():
        return []
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line]


def _run_pre_push(
    *,
    tmp_path: Path,
    enabled_exit: int,
    run_exit: int,
) -> tuple[subprocess.CompletedProcess[str], list[str], list[str]]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True)
    just_log = tmp_path / "just.log"
    uv_log = tmp_path / "uv.log"
    bash = shutil.which("bash")
    assert bash is not None

    _write_executable(
        path=bin_dir / "uv",
        body=f"""#!/usr/bin/env bash
set -euo pipefail
printf '%s\\n' "$*" >> "{uv_log}"
case "$*" in
  "run python -m livespec_dev_tooling.green_token check") exit 1 ;;
  "run python -m {_CLIENT} enabled") exit {enabled_exit} ;;
  "run python -m {_CLIENT} run") exit {run_exit} ;;
esac
echo "unexpected uv invocation: $*" >&2
exit 99
""",
    )
    _write_executable(
        path=bin_dir / "just",
        body=f"""#!/usr/bin/env bash
set -euo pipefail
printf '%s\\n' "$*" >> "{just_log}"
if [[ "$*" == "check" ]]; then
  exit 0
fi
echo "unexpected just invocation: $*" >&2
exit 99
""",
    )

    env = _scrub_coverage_env(env=os.environ.copy())
    env["PATH"] = f"{bin_dir}:{env['PATH']}"
    completed = subprocess.run(
        [bash, str(_SCRIPT)],
        cwd=_REPO_ROOT,
        env=env,
        check=False,
        text=True,
        capture_output=True,
    )
    return completed, _lines(path=just_log), _lines(path=uv_log)


def test_repository_declares_the_delegated_gate_opt_in() -> None:
    assert load_delegated_gate(repo_root=_REPO_ROOT) is True


def test_delegating_push_runs_the_client_and_never_the_local_aggregate(
    tmp_path: Path,
) -> None:
    completed, just_calls, uv_calls = _run_pre_push(tmp_path=tmp_path, enabled_exit=0, run_exit=0)

    assert completed.returncode == 0
    assert f"run python -m {_CLIENT} run" in uv_calls
    assert "check" not in just_calls


def test_delegated_refusal_is_the_push_result_with_no_local_fallthrough(
    tmp_path: Path,
) -> None:
    completed, just_calls, uv_calls = _run_pre_push(tmp_path=tmp_path, enabled_exit=0, run_exit=1)

    assert completed.returncode == 1
    assert f"run python -m {_CLIENT} run" in uv_calls
    assert "check" not in just_calls


def test_non_delegating_host_gates_locally_and_reports_it(
    tmp_path: Path,
) -> None:
    completed, just_calls, uv_calls = _run_pre_push(tmp_path=tmp_path, enabled_exit=1, run_exit=1)

    assert completed.returncode == 0
    assert f"run python -m {_CLIENT} enabled" in uv_calls
    assert f"run python -m {_CLIENT} run" not in uv_calls
    assert "check" in just_calls
    assert "gated locally" in completed.stdout


def test_every_check_aggregate_member_declares_purity(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The token may memoize only members whose declaration makes that decision explicit."""
    inventory_path = _REPO_ROOT / "check-targets.txt"
    assert inventory_path.is_file(), "the check aggregate needs a committed purity inventory"

    justfile = (_REPO_ROOT / "justfile").read_text(encoding="utf-8")
    targets_match = _AGGREGATE_TARGETS.search(justfile)
    assert targets_match is not None
    aggregate_members = tuple(
        line.strip()
        for line in targets_match.group("targets").splitlines()
        if line.strip().startswith("check-")
    )
    inventory_members = tuple(
        line.split("#", 1)[0].strip()
        for line in inventory_path.read_text(encoding="utf-8").splitlines()
        if line.split("#", 1)[0].strip().startswith("check-")
    )
    assert inventory_members == aggregate_members

    monkeypatch.chdir(_REPO_ROOT)
    monkeypatch.setattr(sys, "argv", ["green_token", "undeclared", *aggregate_members])
    assert green_token_main() == 0, capsys.readouterr().err


def test_check_aggregate_refuses_and_names_an_undeclared_member(tmp_path: Path) -> None:
    """An incomplete declaration inventory cannot produce a green aggregate verdict."""
    inventory = tmp_path / "check-targets.txt"
    inventory.write_text("check-fixture-bare\n", encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    invoked = tmp_path / "invoked.log"
    _write_executable(
        path=bin_dir / "uv",
        body="""#!/usr/bin/env bash
case "$*" in
  "sync --all-groups") exit 0 ;;
  *"green_token undeclared"*) printf 'check-fixture-bare\\n'; exit 1 ;;
  *) exit 99 ;;
esac
""",
    )
    _write_executable(
        path=bin_dir / "just",
        body=f"""#!/usr/bin/env bash
printf '%s\\n' "$*" >> "{invoked}"
exit 99
""",
    )
    bash = shutil.which("bash")
    assert bash is not None
    env = _scrub_coverage_env(env=os.environ.copy())
    env.update(
        {"PATH": f"{bin_dir}{os.pathsep}{env['PATH']}", "CHECK_TARGETS_FILE": str(inventory)}
    )

    completed = subprocess.run(
        [bash, str(_REPO_ROOT / "dev-tooling" / "just-check.sh")],
        cwd=tmp_path,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "check-fixture-bare" in completed.stdout + completed.stderr
    assert not invoked.exists(), "the purity audit must refuse before dispatching a member"

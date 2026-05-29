"""Guard: every SKILL.md wrapper invocation resolves post-flatten (li-m4q4h5).

Claude Code's plugin installer FLATTENS `.claude-plugin/scripts/` to
`scripts/` and `.claude-plugin/skills/` to `skills/` in the installed
cache; the cache carries NO `.claude-plugin/` directory and omits
`pyproject.toml` / `uv.lock` / `.python-version` (so `uv run` cannot
synthesize a venv). A fenced run command that quotes
`uv run python3 .claude-plugin/scripts/bin/<name>.py` is therefore
broken in the installed cache on two counts: the literal path does not
exist post-flatten, and `uv run` has no project to resolve.

The canonical invocation form is
`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/bin/<name>.py" "$@"`:
`${CLAUDE_PLUGIN_ROOT}` is the established Claude Code plugin
convention and resolves to the plugin root in BOTH the flattened cache
and `--plugin-dir .` dev mode, with `scripts/` directly beneath it in
both; plain `python3` works because `bin/_bootstrap.py` adds
`scripts/_vendor/` to `sys.path` and the shipped command code imports
only stdlib + the vendored `livespec_runtime`.

This guard parses every fenced run command across the plugin's
SKILL.md files that invokes a `scripts/bin/<name>.py` wrapper (the
`## Invocation` blocks plus any wrapper run commands quoted elsewhere,
e.g. `capture-impl-gaps`'s detection step), asserts each uses the
`${CLAUDE_PLUGIN_ROOT}/` form (never `uv run`, never a bare
`.claude-plugin/scripts/...` literal), and asserts the referenced file
EXISTS under `.claude-plugin/` in the source repo (i.e. that the path
is real once `${CLAUDE_PLUGIN_ROOT}/` maps to `.claude-plugin/`).
"""

import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SKILLS_DIR = _REPO_ROOT / ".claude-plugin" / "skills"
_PLUGIN_ROOT = _REPO_ROOT / ".claude-plugin"

_PLUGIN_ROOT_TOKEN = "${CLAUDE_PLUGIN_ROOT}/"
_FENCE = "```"
# A run command is any line inside a fenced block that invokes a
# `scripts/bin/<name>.py` wrapper. Matching on the `bin/<name>.py`
# tail keeps the guard scoped to wrapper invocations (the surface the
# flatten/uv bug affects), ignoring illustrative Python snippets that
# merely `import` package modules.
_WRAPPER_INVOCATION_RE = re.compile(r"bin/[a-z_]+\.py\b")
# The path token form we require: ${CLAUDE_PLUGIN_ROOT}/scripts/bin/<name>.py
_PLUGIN_ROOT_PATH_RE = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/(\S+?\.py)")


def _skill_files() -> list[Path]:
    return sorted(_SKILLS_DIR.glob("*/SKILL.md"))


def _invocation_commands(*, skill_path: Path) -> list[str]:
    """Return fenced run-command lines invoking a `scripts/bin/*.py` wrapper.

    Walks the file line by line, tracking fenced code blocks (between
    ``` fences), and collects every in-fence line that invokes a
    `bin/<name>.py` wrapper. Prose references outside fences (e.g. the
    `capture-impl-gaps` prerequisite narration, or `process-memos`'s
    deliberate "never call the wrapper directly" counter-example) are
    not run commands and are intentionally excluded.
    """
    lines = skill_path.read_text(encoding="utf-8").splitlines()
    commands: list[str] = []
    in_fence = False
    for line in lines:
        if line.strip().startswith(_FENCE):
            in_fence = not in_fence
            continue
        if not in_fence:
            continue
        stripped = line.strip()
        if _WRAPPER_INVOCATION_RE.search(stripped):
            commands.append(stripped)
    return commands


def _skill_invocation_command_params() -> list[tuple[str, str]]:
    """Return (skill_name, command) pairs for parametrization."""
    params: list[tuple[str, str]] = []
    for skill_path in _skill_files():
        skill_name = skill_path.parent.name
        for command in _invocation_commands(skill_path=skill_path):
            params.append((skill_name, command))
    return params


def test_at_least_one_invocation_command_found() -> None:
    """Sanity: the parser must discover wrapper invocations to guard."""
    assert _skill_invocation_command_params(), (
        "no `scripts/bin/*.py` run commands discovered under "
        f"{_SKILLS_DIR}; the guard would vacuously pass"
    )


@pytest.mark.parametrize(
    ("skill_name", "command"),
    _skill_invocation_command_params(),
)
def test_invocation_uses_plugin_root_and_resolves(*, skill_name: str, command: str) -> None:
    assert "uv run" not in command, (
        f"{skill_name}: wrapper invocation must not use `uv run` "
        f"(the installed cache omits pyproject.toml / uv.lock): {command!r}"
    )
    assert ".claude-plugin/scripts" not in command, (
        f"{skill_name}: wrapper invocation must not hard-code the "
        f"`.claude-plugin/scripts/...` literal (flattened in the cache): {command!r}"
    )
    assert _PLUGIN_ROOT_TOKEN in command, (
        f"{skill_name}: wrapper invocation must use "
        f"`{_PLUGIN_ROOT_TOKEN}scripts/bin/<name>.py`: {command!r}"
    )
    match = _PLUGIN_ROOT_PATH_RE.search(command)
    assert match is not None, (
        f"{skill_name}: could not extract a "
        f"`{_PLUGIN_ROOT_TOKEN}<path>.py` token from: {command!r}"
    )
    relative_path = match.group(1)
    resolved = _PLUGIN_ROOT / relative_path
    assert resolved.is_file(), (
        f"{skill_name}: `${{CLAUDE_PLUGIN_ROOT}}/{relative_path}` does not "
        f"resolve to a real file under {_PLUGIN_ROOT} (expected {resolved})"
    )

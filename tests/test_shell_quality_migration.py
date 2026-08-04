"""Positive controls for the v1.18.7 justfile shell-quality migration."""

from __future__ import annotations

import re
from pathlib import Path

__all__: list[str] = []

_REPO_ROOT = Path(__file__).resolve().parents[1]
_INTERPOLATION_SENTINEL = "__JUST_INTERPOLATION__"


def _justfile_text() -> str:
    return (_REPO_ROOT / "justfile").read_text(encoding="utf-8")


def _recipe_body(*, recipe_name: str) -> str:
    lines = _justfile_text().splitlines()
    header_index = next(
        index
        for index, line in enumerate(lines)
        if re.fullmatch(rf"{re.escape(recipe_name)}(?:\s+.*)?:", line)
    )
    body: list[str] = []
    for line in lines[header_index + 1 :]:
        if line and not line.startswith((" ", "\t")) and ":" in line:
            break
        body.append(line)
    return "\n".join(body)


def _executable_lines(*, body: str) -> list[str]:
    return [
        line.strip()
        for line in body.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def _flatten_body_line(*, parts: list[object]) -> tuple[str, bool]:
    text = ""
    interpolated = False
    for part in parts:
        if isinstance(part, str):
            text += part
        else:
            interpolated = True
            text += _INTERPOLATION_SENTINEL
    return text.strip(), interpolated


def test_migrated_governed_recipes_are_thin_delegators() -> None:
    migrated_recipes = {
        "bootstrap",
        "changed-files",
        "check-changed",
        "check-coverage",
        "check-doctor-static",
        "check-no-workflow-edits",
        "check-pre-commit",
        "check-pre-commit-doc-only",
        "check-pre-push",
        "check-static",
        "ensure-codex-plugins",
        "lint-autofix-staged",
        "migrate-beads",
    }

    for recipe_name in migrated_recipes:
        body = _recipe_body(recipe_name=recipe_name)

        assert len(_executable_lines(body=body)) == 1
        assert "{{" not in body
        assert "}}" not in body


def test_check_recipe_documents_errexit_deviation_and_retains_target_registry() -> None:
    justfile = _justfile_text()
    body = _recipe_body(recipe_name="check")

    assert "Deliberately omit errexit" in justfile
    assert "set -uo pipefail" in body
    assert "targets=(" in body
    assert "bash dev-tooling/just-check.sh" in body
    assert "{{" not in body
    assert "}}" not in body


def test_per_file_coverage_documents_errexit_deviation_and_stays_canonical() -> None:
    justfile = _justfile_text()
    body = _recipe_body(recipe_name="check-per-file-coverage")

    assert "pytest fail-closes" in justfile
    assert "set -uo pipefail" in body
    assert "livespec_dev_tooling.checks.per_file_coverage" in body
    assert "{{" not in body
    assert "}}" not in body


def test_rejected_interpolation_control_is_detectable() -> None:
    rendered, interpolated = _flatten_body_line(
        parts=[
            "uv run python -m livespec_dev_tooling.checks.red_green_replay ",
            {"variable": "args"},
        ]
    )

    assert interpolated
    assert _INTERPOLATION_SENTINEL in rendered


def test_clean_positional_forwarding_surface_is_non_interpolated() -> None:
    body = _recipe_body(recipe_name="check-red-green-replay")

    assert 'red_green_replay "$@"' in body
    assert "{{" not in body
    assert "}}" not in body


def test_executable_line_filter_ignores_blank_and_comment_lines() -> None:
    assert _executable_lines(body="\n    # rationale\n    bash helper.sh\n") == ["bash helper.sh"]


def test_recipe_body_reader_handles_final_recipe() -> None:
    # Derive the final recipe instead of naming one: a name pinned here stops
    # exercising the no-following-header path as soon as a recipe is appended.
    lines = _justfile_text().splitlines()
    header = re.compile(r"([A-Za-z][A-Za-z0-9_-]*)(?:\s+.*)?:")
    final_index, final_recipe_name = next(
        (index, match.group(1))
        for index, line in reversed(list(enumerate(lines)))
        if (match := header.fullmatch(line)) is not None
    )

    body = _recipe_body(recipe_name=final_recipe_name)

    assert body == "\n".join(lines[final_index + 1 :])
    assert _executable_lines(body=body)

"""I/O helpers for the needs-attention spec-`next` bridge."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__: list[str] = [
    "ProcessResult",
    "load_json_file_optional",
    "loads_json_optional",
    "run_capture",
]


@dataclass(frozen=True, slots=True, kw_only=True)
class ProcessResult:
    """Captured stdout + exit code from a subprocess invocation."""

    stdout: str
    returncode: int


def loads_json_optional(*, text: str) -> Any:
    """Parse JSON text; return None on parse failure."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def load_json_file_optional(*, path: Path) -> Any:
    """Read and parse a JSON file; return None when absent, unreadable, or invalid."""
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def run_capture(*, argv: list[str], timeout: int) -> ProcessResult:
    """Run argv and capture stdout; expected OS/subprocess errors become exit 1."""
    try:
        completed = subprocess.run(  # noqa: S603
            argv,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return ProcessResult(stdout="", returncode=1)
    return ProcessResult(stdout=completed.stdout, returncode=completed.returncode)

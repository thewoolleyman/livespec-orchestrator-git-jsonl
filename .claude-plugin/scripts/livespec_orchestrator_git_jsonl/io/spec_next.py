"""I/O helpers for the needs-attention spec-`next` bridge.

⛔ NOTHING HERE INVENTS AN ANSWER. Both readers used to: `run_capture`
returned `ProcessResult(stdout="", returncode=1)` when the command could not
be SPAWNED — a well-formed result describing a process that never started,
indistinguishable at the call site from one that ran and exited 1 — and
`load_json_file_optional` collapsed "absent", "unreadable" and "not JSON"
into a single `None`.

⚠️ THAT SENTENCE SAID "Both readers" WHILE THIS MODULE EXPORTED THREE. The
third was `loads_json_optional`, which returned `None` on a caught
`json.JSONDecodeError` — and `json.loads("null")` returns `None` too, so its
failure signal WAS a legitimate value and no caller could separate them even
in principle. It is now DELETED rather than converted: `io/_jsonc.py::loads`
already carries the parse failure as `Result[Any, JsoncParseError]`, so the
twin had nothing left to do. The count and the claim now agree.

Only the absent file is an ANSWER, and it is the one thing still spelled
`None`, on the SUCCESS track. Everything else is a named failure carrying
what could not be done.
"""

from __future__ import annotations

import json
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from returns.io import IOFailure, IOResult, IOSuccess

__all__: list[str] = [
    "CommandUnavailable",
    "JsonFileUnreadable",
    "ProcessResult",
    "load_json_file_optional",
    "run_capture",
]


@dataclass(frozen=True, slots=True, kw_only=True)
class CommandUnavailable:
    """A command that could not be SPAWNED, or did not finish in time.

    Deliberately NOT inhabited by "it ran and exited non-zero" — that is an
    ANSWER and rides the success track with its exit code intact. What lives
    here is the case the caller previously could not see at all.
    """

    argv: str
    detail: str


@dataclass(frozen=True, slots=True, kw_only=True)
class JsonFileUnreadable:
    """A JSON file that EXISTS but could not be read or parsed.

    Deliberately NOT inhabited by "the file is absent": a missing registry is
    the ordinary state this bridge is built to tolerate, so it stays an
    answer. Being unable to READ a file that is there is not the same claim.
    """

    path: str
    detail: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ProcessResult:
    """Captured stdout + exit code from a subprocess invocation."""

    stdout: str
    returncode: int


def load_json_file_optional(*, path: Path) -> IOResult[Any, JsonFileUnreadable]:
    """Parse a JSON file; `None` on the success track when it is simply ABSENT.

    ⚠️ The `Any` success type carries `None` for the absent case on purpose.
    An absent registry is the ordinary state the spec-`next` bridge tolerates,
    so it is an ANSWER; a file that exists and will not read or parse is not.
    """
    if not path.is_file():
        return IOSuccess(None)
    try:
        decoded: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as unreadable:
        return IOFailure(JsonFileUnreadable(path=str(path), detail=str(unreadable)))
    return IOSuccess(decoded)


def run_capture(*, argv: list[str], timeout: int) -> IOResult[ProcessResult, CommandUnavailable]:
    """Run argv and capture stdout, or name the command that never answered.

    A non-zero EXIT is data and stays on the success track. Only a command
    that could not be spawned, or that outran its timeout, is a failure —
    and those used to be reported as `returncode=1`, which is a real exit
    code some other command really does return.
    """
    try:
        completed = subprocess.run(  # noqa: S603
            argv,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError) as unusable:
        return IOFailure(
            CommandUnavailable(
                argv=shlex.join(argv), detail=str(unusable) or type(unusable).__name__
            )
        )
    return IOSuccess(ProcessResult(stdout=completed.stdout, returncode=completed.returncode))

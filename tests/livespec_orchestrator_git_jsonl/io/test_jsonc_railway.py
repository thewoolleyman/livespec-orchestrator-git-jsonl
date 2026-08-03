"""JSONC parsing answers on a railway rather than raising.

`io/_jsonc` is the module the package's docstring calls *"the only place JSONC
parse errors are caught"*, and it caught them twice: `loads` raised
`JsoncParseError`, and `loads_optional` existed solely to swallow that raise
back into `None` so *"callers outside io/ avoid try/except"*.

Once the parse itself returns a `Result`, the second function has nothing left
to do — a caller that wants the absent-shaped answer writes `.value_or(None)` —
so these tests pin the one surface that remains.

`Result`, not `IOResult`: the parse is pure. The file read happens in the
caller, which is where the I/O boundary actually is.
"""

from __future__ import annotations

from typing import Any

from livespec_orchestrator_git_jsonl.io._jsonc import JsoncParseError, loads
from returns.result import Failure, Success

__all__: list[str] = []


def test_loads_carries_the_decoded_value_on_the_success_track() -> None:
    outcome = loads(text='{"a": 1} // trailing comment')

    assert isinstance(outcome, Success)
    decoded: Any = outcome.unwrap()
    assert decoded == {"a": 1}


def test_loads_routes_malformed_jsonc_to_the_failure_track() -> None:
    """The diagnostic is unchanged; only the channel it travels on is."""
    outcome = loads(text="{not valid")

    assert isinstance(outcome, Failure)
    failure = outcome.failure()
    assert isinstance(failure, JsoncParseError)
    assert "jsonc parse failed" in failure.detail

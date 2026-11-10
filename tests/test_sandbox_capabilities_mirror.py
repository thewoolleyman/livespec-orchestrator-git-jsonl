"""Conformance: this repository's committed sandbox-capability mirror.

`dispatcher.sandbox_capabilities` in `.livespec.jsonc` is the committed
MIRROR of the capability set the sandbox image this repository's
dispatches run on publishes at `/etc/livespec/sandbox-capabilities`. A
host-side surface — the filing display, and the `dod_gate` preflight the
control host runs from this repository's root — cannot reach into a
sandbox, so the mirror is what it reads. With the key absent the
preflight refuses outright rather than grading its capability check.

The mirror is MEASURED, never guessed, but which capabilities the
sandbox image publishes is a committed VALUE, not a contract: the image
changes and the mirror is re-measured to follow it. This test therefore
asserts only the mirror's SHAPE — the key is present and is a list of
lowercase snake_case capability names — and never the committed names or
their order, so re-measuring the mirror leaves it passing.

The surface under test is this repository's OWN committed
`.livespec.jsonc`, read from the checkout — the mirror is a thing this
repository COMMITS, so the committed file IS the realization. Reading it
is tree-reading, never a host read: `/etc/livespec/sandbox-capabilities`
is deliberately NOT consulted here, because it exists only inside a
sandbox and this suite also runs on hosts that have none. The post-merge
preflight that grades check 5 against this array is the separate
host-captured proof.

Control-armed: `_malformed` is exercised against a synthetic list
carrying the shapes the resolving module rejects — a hyphenated name, a
capitalised one, and the empty string — and flags exactly those, so the
clean verdict on the committed array is a reading rather than a vacuous
pass; `_shape_problem` is exercised against synthetic blocks the test
writes itself, so the absent-key and not-a-list-of-names failures are
proven without touching the committed file.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from livespec_orchestrator_git_jsonl.io._jsonc import loads

_REPO_ROOT = Path(__file__).resolve().parents[1]
_CONFIG_FILE = ".livespec.jsonc"
_IMPL_PLUGIN = "livespec-orchestrator-beads-fabro"
_MIRROR_KEY = "sandbox_capabilities"

# Lowercase snake_case as the contract spells it: a lowercase letter
# first, then lowercase letters and digits, with single underscores
# between non-empty runs.
_CAPABILITY_NAME = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")


def _malformed(*, names: list[Any]) -> tuple[Any, ...]:
    """Return the entries that are not lowercase snake_case names, in order.

    A name the image does not publish in this shape silently fails to
    match wherever the gate compares against it, so a typo reports a
    finding against an item whose declaration was correct the whole
    time. That is why the shape is asserted here rather than assumed.
    """
    return tuple(
        entry
        for entry in names
        if not isinstance(entry, str) or _CAPABILITY_NAME.match(entry) is None
    )


def _dispatcher_block() -> dict[str, Any]:
    text = (_REPO_ROOT / _CONFIG_FILE).read_text(encoding="utf-8")
    config: dict[str, Any] = loads(text=text).unwrap()
    return config[_IMPL_PLUGIN]["dispatcher"]


def _shape_problem(*, dispatcher: dict[str, Any]) -> str | None:
    """Return why the block's mirror is not a list of capability names, or None."""
    if _MIRROR_KEY not in dispatcher:
        return "absent"
    capabilities: Any = dispatcher[_MIRROR_KEY]
    if not isinstance(capabilities, list):
        return "not a list"
    if _malformed(names=capabilities):
        return "malformed names"
    return None


def test_the_predicate_flags_names_that_are_not_lowercase_snake_case() -> None:
    # Positive control for the offender branch: the three shapes the
    # resolving module rejects are flagged, and the conforming names
    # beside them are not.
    synthetic = ["terminal", "headless-browser", "HeadlessBrowser", "", "x11_display", 7]
    assert _malformed(names=synthetic) == ("headless-browser", "HeadlessBrowser", "", 7)


def test_the_shape_check_fails_on_an_absent_or_non_list_or_malformed_mirror() -> None:
    assert _shape_problem(dispatcher={}) == "absent"
    assert _shape_problem(dispatcher={_MIRROR_KEY: "terminal"}) == "not a list"
    assert _shape_problem(dispatcher={_MIRROR_KEY: None}) == "not a list"
    assert _shape_problem(dispatcher={_MIRROR_KEY: ["terminal", "Bad-Name"]}) == "malformed names"
    assert _shape_problem(dispatcher={_MIRROR_KEY: [3]}) == "malformed names"
    assert _shape_problem(dispatcher={_MIRROR_KEY: ["alpha", "beta_2"]}) is None
    assert _shape_problem(dispatcher={_MIRROR_KEY: []}) is None


def test_this_repository_commits_a_well_shaped_sandbox_capability_mirror() -> None:
    assert _shape_problem(dispatcher=_dispatcher_block()) is None

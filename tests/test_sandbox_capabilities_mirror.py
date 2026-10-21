"""Conformance: this repository's committed sandbox-capability mirror.

`dispatcher.sandbox_capabilities` in `.livespec.jsonc` is the committed
MIRROR of the capability set the sandbox image this repository's
dispatches run on publishes at `/etc/livespec/sandbox-capabilities`. A
host-side surface — the filing display, and the `dod_gate` preflight the
control host runs from this repository's root — cannot reach into a
sandbox, so the mirror is what it reads. With the key absent the
preflight refuses outright rather than grading its capability check.

The mirror is MEASURED, never guessed. The values asserted here were
probed inside the sandbox of this repository's own dispatch on
2026-10-21 (Ubuntu 24.04.5 LTS): the image published exactly `terminal`,
`tmux`, `headless_browser`, `herdr`, and each was exercised rather than
merely looked up — bash 5.2.21 as the shell, tmux 3.4 creating and
listing a detached session, Playwright 1.63.0 driving Chromium
153.0.8010.12 to render a page to a PNG, and herdr 0.9.3 printing its
usage. Declaration ORDER follows the published file, which the resolving
module preserves rather than sorts.

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
pass.
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

# The capabilities measured inside this repository's dispatch sandbox, in
# the order the image publishes them.
_MEASURED = ("terminal", "tmux", "headless_browser", "herdr")

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


def test_the_predicate_flags_names_that_are_not_lowercase_snake_case() -> None:
    # Positive control for the offender branch: the three shapes the
    # resolving module rejects are flagged, and the conforming names
    # beside them are not.
    synthetic = ["terminal", "headless-browser", "HeadlessBrowser", "", "x11_display", 7]
    assert _malformed(names=synthetic) == ("headless-browser", "HeadlessBrowser", "", 7)


def test_this_repository_commits_the_measured_sandbox_capability_mirror() -> None:
    dispatcher = _dispatcher_block()
    assert _MIRROR_KEY in dispatcher
    capabilities: Any = dispatcher[_MIRROR_KEY]
    assert isinstance(capabilities, list)
    assert tuple(capabilities) == _MEASURED
    assert _malformed(names=capabilities) == ()

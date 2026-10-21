"""Conformance: this repository's committed factory table names no machine.

`SPECIFICATION/constraints.md` section "Factory routing" (ratified at
v019) requires every entry this repository commits in `.livespec.jsonc`
under `dispatcher.factories` to be REGISTRY-BACKED — it declares
`"registry": true` and carries no `server` and no `docker_host` value —
so no committed factory entry names a machine. Which Fabro server
answers to a factory name is bound only in the fleet gitops inventory's
factory registry, which each dispatching host renders and a dispatch
resolves by name. The same section requires
`dispatcher.default_factory` to name `legacy`.

The surface under test is this repository's OWN committed
`.livespec.jsonc`, read from the checkout — the heading governs what
this repository commits, not what any shipped module computes, so the
committed file IS the realization. Reading it is tree-reading, never a
host read: the registry file the dispatching host renders is deliberately
NOT consulted here, and the post-merge dispatch that resolves `legacy`
through it is the separate host-captured proof.

Control-armed: `_hostname_bearing` is exercised against a synthetic table
carrying the pre-v019 shape (a `server`-bearing entry beside a
registry-backed one) and flags exactly the offender, so the clean verdict
on the committed table is a reading rather than a vacuous pass.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from livespec_orchestrator_git_jsonl.io._jsonc import loads

_REPO_ROOT = Path(__file__).resolve().parents[1]
_CONFIG_FILE = ".livespec.jsonc"
_IMPL_PLUGIN = "livespec-orchestrator-beads-fabro"
_MACHINE_NAMING_KEYS = ("server", "docker_host")


def _hostname_bearing(*, factories: dict[str, Any]) -> tuple[str, ...]:
    """Return the factory names that are not registry-backed, in table order.

    An entry is registry-backed iff it declares `"registry": true` and
    carries NEITHER a `server` NOR a `docker_host` value. Anything else
    binds a name to a machine in the committed tree, which is what the
    "Factory routing" section forbids.
    """
    return tuple(
        name
        for name, entry in factories.items()
        if entry.get("registry") is not True or any(key in entry for key in _MACHINE_NAMING_KEYS)
    )


def _dispatcher_block() -> dict[str, Any]:
    text = (_REPO_ROOT / _CONFIG_FILE).read_text(encoding="utf-8")
    config: dict[str, Any] = loads(text=text).unwrap()
    return config[_IMPL_PLUGIN]["dispatcher"]


def test_the_predicate_flags_a_hostname_bearing_factory_entry() -> None:
    # Positive control for the offender branch: the pre-v019 shape this
    # repository committed (a `server`-bearing `hp` beside a
    # registry-backed entry) is flagged, and only the offender is named.
    synthetic = {
        "hp": {"server": "https://factory.invalid:32276"},
        "legacy": {"registry": True},
    }
    assert _hostname_bearing(factories=synthetic) == ("hp",)


def test_this_repository_commits_only_registry_backed_factory_entries() -> None:
    factories: dict[str, Any] = _dispatcher_block()["factories"]
    assert tuple(factories) == ("legacy",)
    assert factories["legacy"]["registry"] is True
    assert _hostname_bearing(factories=factories) == ()


def test_the_committed_default_factory_names_legacy() -> None:
    assert _dispatcher_block()["default_factory"] == "legacy"

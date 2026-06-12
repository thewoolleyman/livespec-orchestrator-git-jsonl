"""`check-no-raw-store-read` store-integrity check.

Per SPECIFICATION/contracts.md §"Append-only store disciplines" →
"Store-integrity checks (orchestrator-private)" + "Read path only via
the query surface" (v008), this check fires fail when shipped code
opens a declared backing store path directly, bypassing the
reducer/query surface. Any consumer of store state MUST obtain it
through the published query CLIs/skills or through the single canonical
reducer they delegate to; the canonical store module
(`livespec_impl_git_jsonl/store.py`) IS that surface and is the one
exemption. This is the mechanical guard for the one-canonical-reducer
obligation — a private "latest wins" re-implementation would have to
read a backing store raw, which this check catches.

Realization: AST-scan every committed shipped `.py` under
`.claude-plugin/scripts/` and `dev-tooling/` (excluding `_vendor/` and
`__pycache__/`) for open-shaped calls (`open(...)`, `.open(...)`,
`.read_text(...)`, `.read_bytes(...)`) whose expression references a
declared backing store — the `work_items_path` / `memos_path`
store-config attributes (or parameters named after them) or a string
literal ending with a declared store basename. The declared basenames
are derived from the same `resolve_store_config` resolver the query
wrappers consume, not re-declared here.

Scope is committed shipped code only: the check cannot police ad-hoc
interactive shell reads — the record self-identification and
order-independent-reduction obligations defend that residual surface.

Wired into this repo's `just check` aggregate (NOT livespec's doctor —
the stores are orchestrator-private) as `check-no-raw-store-read`,
invoked through the `.claude-plugin/scripts/bin/check_no_raw_store_read.py`
wrapper.
"""

import argparse
import ast
import sys
from collections.abc import Iterator
from pathlib import Path

from livespec_impl_git_jsonl.commands._config import resolve_store_config

__all__: list[str] = ["main"]


_CHECK_NAME = "check-no-raw-store-read"

_SHIPPED_TREES = (
    Path(".claude-plugin") / "scripts",
    Path("dev-tooling"),
)
_EXEMPT_PATH_COMPONENTS = frozenset({"_vendor", "__pycache__"})
_CANONICAL_QUERY_SURFACE = (
    Path(".claude-plugin") / "scripts" / "livespec_impl_git_jsonl" / "store.py"
)
_OPEN_ATTRIBUTE_NAMES = frozenset({"open", "read_text", "read_bytes"})
_DECLARED_PATH_NAMES = frozenset({"work_items_path", "memos_path"})


def main(*, argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog=_CHECK_NAME)
    _ = parser.add_argument("--root", dest="root", default=".")
    args = parser.parse_args(argv)
    root = Path(args.root)
    store_basenames = _declared_store_basenames(root=root)
    findings = _find_raw_store_reads(root=root, store_basenames=store_basenames)
    for line in findings:
        _ = sys.stdout.write(line + "\n")
    if findings:
        _ = sys.stdout.write(f"{_CHECK_NAME}: FAIL — {len(findings)} finding(s)\n")
        return 1
    _ = sys.stdout.write(f"{_CHECK_NAME}: OK — no raw backing-store opens in shipped code\n")
    return 0


def _declared_store_basenames(*, root: Path) -> frozenset[str]:
    """Derive the declared backing-store basenames from the published resolver."""
    config = resolve_store_config(cwd=root, work_items_arg=None, memos_arg=None)
    return frozenset({config.work_items_path.name, config.memos_path.name})


def _find_raw_store_reads(*, root: Path, store_basenames: frozenset[str]) -> list[str]:
    findings: list[str] = []
    for path in _iter_shipped_py_files(root=root):
        relative = path.relative_to(root)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and _is_open_shaped(call=node)
                and _references_declared_store(call=node, store_basenames=store_basenames)
            ):
                offending_call = ast.unparse(node)
                prefix = f"{_CHECK_NAME}: {relative}:{node.lineno}:"
                detail = "opens a declared backing store directly, bypassing the reducer/query"
                findings.append(f"{prefix} {detail} surface: {offending_call}")
    return findings


def _iter_shipped_py_files(*, root: Path) -> Iterator[Path]:
    for tree in _SHIPPED_TREES:
        base = root / tree
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            relative = path.relative_to(root)
            if any(part in _EXEMPT_PATH_COMPONENTS for part in relative.parts):
                continue
            if relative == _CANONICAL_QUERY_SURFACE:
                continue
            yield path


def _is_open_shaped(*, call: ast.Call) -> bool:
    """True for `open(...)`, `.open(...)`, `.read_text(...)`, `.read_bytes(...)`."""
    func = call.func
    if isinstance(func, ast.Name):
        return func.id == "open"
    if isinstance(func, ast.Attribute):
        return func.attr in _OPEN_ATTRIBUTE_NAMES
    return False


def _references_declared_store(*, call: ast.Call, store_basenames: frozenset[str]) -> bool:
    """True when the call expression ties to a declared backing store.

    A tie is an attribute access or bare name matching the declared
    store-config path attributes (`work_items_path` / `memos_path`), or
    a string literal ending with a declared store basename. Receiver
    and arguments are both inspected (the whole call subtree).
    """
    for node in ast.walk(call):
        if isinstance(node, ast.Attribute) and node.attr in _DECLARED_PATH_NAMES:
            return True
        if isinstance(node, ast.Name) and node.id in _DECLARED_PATH_NAMES:
            return True
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and any(node.value.endswith(basename) for basename in store_basenames)
        ):
            return True
    return False

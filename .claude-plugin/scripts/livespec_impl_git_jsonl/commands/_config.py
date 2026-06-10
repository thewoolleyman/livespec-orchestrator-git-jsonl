"""Configuration helpers shared across the thin-transport command modules.

The full .livespec.jsonc reader is OUT-OF-SCOPE for v001; consumer projects
that need non-default store paths pass them as CLI flags. The defaults
match SPECIFICATION/contracts.md §"`compat` block": work-items.jsonl and
memos.jsonl at the consumer project root (i.e., the current working
directory).
"""

from pathlib import Path

from livespec_impl_git_jsonl.types import StoreConfig

_DEFAULT_WORK_ITEMS = "work-items.jsonl"
_DEFAULT_MEMOS = "memos.jsonl"


def resolve_store_config(
    *,
    cwd: Path,
    work_items_arg: str | None,
    memos_arg: str | None,
) -> StoreConfig:
    """Resolve the StoreConfig from CLI args and defaults relative to cwd."""
    work_items_relative = work_items_arg if work_items_arg is not None else _DEFAULT_WORK_ITEMS
    memos_relative = memos_arg if memos_arg is not None else _DEFAULT_MEMOS
    return StoreConfig(
        work_items_path=cwd / work_items_relative,
        memos_path=cwd / memos_relative,
    )

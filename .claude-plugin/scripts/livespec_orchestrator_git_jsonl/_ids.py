"""Stable-format ID generation for work-items.

Per SPECIFICATION/contracts.md, work-item IDs follow the upstream
`bd` convention `li-<6-char-base32-suffix>`.

The six-lowercase-base32-character suffix generator is the SHARED
`livespec_runtime.work_items.reduce.random_id_suffix` (this repo's
`_random_suffix`, lifted byte-faithfully into runtime by the W7
extraction). The backend-coupled `li-` minting stays LOCAL here:
randomness comes from `secrets.token_bytes` so collision probability is
negligible under the JSONL store's append-only discipline; if two skills
append records with identical IDs in the same git commit's pre-merge
state, git merge will surface the conflict and the user resolves it like
any other race.
"""

from livespec_runtime.work_items.reduce import random_id_suffix

__all__: list[str] = ["new_work_item_id"]


def new_work_item_id() -> str:
    """Return a fresh `li-XXXXXX` identifier."""
    return f"li-{random_id_suffix()}"

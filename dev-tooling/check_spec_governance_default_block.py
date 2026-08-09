"""Verify this repo's documented spec-governance defaults block."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

from livespec_runtime.spec_governance import verify_livespec_jsonc_default_block
from returns.result import Failure, Success

__all__: list[str] = []

_CONFIG_PATH = ".livespec.jsonc"
_DRIFT_EXIT = 2


def _configure_logger() -> logging.Logger:
    handler = logging.StreamHandler(stream=sys.stderr)
    handler.setFormatter(logging.Formatter("%(message)s"))
    log = logging.getLogger("spec_governance_default_block")
    log.handlers[:] = [handler]
    log.setLevel(logging.INFO)
    return log


def main() -> int:
    log = _configure_logger()
    result = verify_livespec_jsonc_default_block(path=Path.cwd() / _CONFIG_PATH)
    if isinstance(result, Success):
        log.info(json.dumps(result.unwrap(), sort_keys=True))
        return 0
    if isinstance(result, Failure):
        log.error(result.failure())
        return _DRIFT_EXIT
    return _DRIFT_EXIT


if __name__ == "__main__":
    raise SystemExit(main())

"""Per-wrapper coverage test for bin/check_no_raw_store_read.py."""

from collections.abc import Callable


def test_check_no_raw_store_read_wrapper_threads_exit_code(
    wrapper_runner: Callable[[str, str, int], None],
) -> None:
    wrapper_runner(
        "check_no_raw_store_read.py",
        "livespec_impl_git_jsonl.checks.no_raw_store_read",
        1,
    )

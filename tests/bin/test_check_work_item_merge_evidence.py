"""Per-wrapper coverage test for bin/check_work_item_merge_evidence.py."""

from collections.abc import Callable


def test_check_work_item_merge_evidence_wrapper_threads_exit_code(
    wrapper_runner: Callable[[str, str, int], None],
) -> None:
    wrapper_runner(
        "check_work_item_merge_evidence.py",
        "livespec_impl_git_jsonl.checks.work_item_merge_evidence",
        1,
    )

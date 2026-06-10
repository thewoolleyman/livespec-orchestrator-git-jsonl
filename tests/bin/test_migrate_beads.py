"""Per-wrapper coverage test for bin/migrate_beads.py."""

from collections.abc import Callable


def test_migrate_beads_wrapper_threads_exit_code(
    wrapper_runner: Callable[[str, str, int], None],
) -> None:
    wrapper_runner(
        "migrate_beads.py",
        "livespec_impl_git_jsonl.migration.beads_to_jsonl",
        0,
    )

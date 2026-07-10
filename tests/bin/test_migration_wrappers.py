"""Per-wrapper coverage tests for standalone migration entry points."""

from collections.abc import Callable


def test_depends_on_typed_form_wrapper_threads_exit_code(
    wrapper_runner: Callable[[str, str, int], None],
) -> None:
    wrapper_runner(
        "depends_on_typed_form.py",
        "livespec_orchestrator_git_jsonl.migration.depends_on_typed_form",
        0,
    )


def test_merge_evidence_backfill_wrapper_threads_exit_code(
    wrapper_runner: Callable[[str, str, int], None],
) -> None:
    wrapper_runner(
        "merge_evidence_backfill.py",
        "livespec_orchestrator_git_jsonl.migration.merge_evidence_backfill",
        0,
    )

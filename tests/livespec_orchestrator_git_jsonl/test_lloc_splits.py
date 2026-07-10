"""Regression guards for file-lloc module splits."""

from livespec_orchestrator_git_jsonl import store_schema
from livespec_orchestrator_git_jsonl.commands import spec_next_bridge
from livespec_orchestrator_git_jsonl.migration import (
    merge_evidence_backfill,
    merge_evidence_backfill_core,
)


def test_spec_next_bridge_declares_public_boundary() -> None:
    assert "SpecNextSeam" in spec_next_bridge.__all__
    assert "spec_next" in spec_next_bridge.__all__


def test_merge_evidence_backfill_reexports_core() -> None:
    assert merge_evidence_backfill.BackfillReport is merge_evidence_backfill_core.BackfillReport
    assert merge_evidence_backfill.backfill_file is merge_evidence_backfill_core.backfill_file


def test_store_schema_declares_public_boundary() -> None:
    assert "parse_work_item" in store_schema.__all__
    assert "validate_work_item_payload" in store_schema.__all__

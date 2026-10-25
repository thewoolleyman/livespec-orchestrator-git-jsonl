"""Regression guards for file-lloc module splits."""

from livespec_orchestrator_git_jsonl import _store_schema_fields, store_schema
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


def test_store_schema_fields_crosses_the_boundary_publicly() -> None:
    """The extracted field graders are a real interface, not borrowed privates.

    A `_`-prefixed name imported from another module is what pyright strict and
    `check-private-calls` both refuse, so the split is only legitimate while
    these three stay public AND `store_schema` holds none of them itself.
    """
    assert _store_schema_fields.__all__ == [
        "enum_membership_error",
        "optional_string_key_error",
        "required_keys_error",
    ]
    assert store_schema.required_keys_error is _store_schema_fields.required_keys_error
    assert not [name for name in vars(store_schema) if name.startswith("_check_")]

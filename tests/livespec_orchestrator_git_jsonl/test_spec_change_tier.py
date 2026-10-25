"""The `spec_change_tier` record key: serialization and the write path.

The work-items record schema in `SPECIFICATION/contracts.md` makes
`spec_change_tier` "object or `null`. OPTIONAL on the read path ...; always
written explicitly on append. When non-null it is the JSON serialization of the
vendored release's `livespec_runtime.spec_stated.SpecChangeTier`: one key per
dataclass field under the field's own name, a nested `SpecStatedVerdict`
serialized the same way (a tuple field as a JSON array), and `None` as `null`."

WHY THE KEY SET IS ASSERTED AGAINST THE DATACLASS AND NOT AGAINST A LITERAL. The
clause says "one key per dataclass field", which makes the DATACLASS the
authority on the key set — so a field the vendored release adds is a key this
store owes, and a serializer enumerating fields by hand would drop it silently.
Dropping it is worse than failing: the record still round-trips, still validates,
and still reads as a complete tier, so the loss surfaces only when somebody
compares two orchestrators' records of one judgement. The assertions below take
the expected key set from `dataclasses.fields`, so a runtime bump that adds a
field fails here rather than quietly truncating every record written afterwards.

WHY "ALWAYS WRITTEN EXPLICITLY ON APPEND" IS ITS OWN ASSERTION. The read path
treats an ABSENT key as `null`, which is what lets legacy records parse. That
tolerance is also what hides a write path that forgot the key: every record it
emits reads back exactly like a record authored before the field existed. So the
presence of the key on a record carrying no tier is asserted separately from the
tier's own serialization.
"""

import json
from dataclasses import fields
from pathlib import Path
from typing import Any

import pytest
from livespec_orchestrator_git_jsonl.spec_change_tier import spec_change_tier_to_dict
from livespec_orchestrator_git_jsonl.store import append_work_item, read_work_items
from livespec_orchestrator_git_jsonl.types import WorkItem
from livespec_runtime.spec_stated import SpecChangeTier, SpecStatedVerdict
from returns.io import IOSuccess
from returns.unsafe import unsafe_perform_io

_HEADING = "## The seven-skill surface"
_TOPIC = "spec-stated-judgement-consumer"
_JUDGED_AT = "2026-10-25T09:00:00Z"


def _item(*, id_: str = "li-tier01", type_: str = "feature") -> WorkItem:
    return WorkItem(
        id=id_,
        type=type_,  # type: ignore[arg-type]
        status="ready",  # type: ignore[arg-type]
        title="the skill files a feature the spec does not state",
        description="a behaviour no ratified clause states",
        origin="freeform",
        gap_id=None,
        rank="a1",
        assignee=None,
        depends_on=(),
        captured_at="2026-10-25T09:00:00Z",
        resolution=None,
        reason=None,
        audit=None,
        superseded_by=None,
    )


def _unstated_verdict() -> SpecStatedVerdict:
    return SpecStatedVerdict(
        kind="unstated",
        stated_by=(),
        generalization_target=_HEADING,
        rationale="no ratified clause states this filing behaviour",
    )


def _spec_change_tier() -> SpecChangeTier:
    return SpecChangeTier(
        tier="spec-change",
        linked_proposal_topic=_TOPIC,
        verdict=_unstated_verdict(),
        judged_at=_JUDGED_AT,
    )


def _appended_payload(
    *, path: Path, item: WorkItem, spec_change_tier: SpecChangeTier | None
) -> dict[str, Any]:
    result = append_work_item(path=path, item=item, spec_change_tier=spec_change_tier)
    # Asserted rather than unwrapped on a failure branch: the write path
    # validates its own payload, so a refusal here means the schema does not
    # admit the key — which every caller below would then report as a missing
    # value rather than as the refusal it is.
    assert isinstance(result, IOSuccess)
    return json.loads(path.read_text(encoding="utf-8").splitlines()[0])


def test_a_spec_change_tier_serializes_one_key_per_dataclass_field() -> None:
    """contracts.md record schema: one key per dataclass field, tuples as arrays.

    Control: the key sets come from `dataclasses.fields`, so a serializer that
    enumerates the fields by hand fails the moment the vendored release adds
    one — instead of silently truncating every record written afterwards.
    """
    serialized = spec_change_tier_to_dict(tier=_spec_change_tier())
    assert serialized is not None
    assert set(serialized) == {field.name for field in fields(SpecChangeTier)}
    verdict = serialized["verdict"]
    assert set(verdict) == {field.name for field in fields(SpecStatedVerdict)}
    assert serialized["tier"] == "spec-change"
    assert serialized["linked_proposal_topic"] == _TOPIC
    assert serialized["judged_at"] == _JUDGED_AT
    assert verdict["kind"] == "unstated"
    assert verdict["generalization_target"] == _HEADING
    # A tuple field lands as a JSON ARRAY, not a tuple: a tuple survives
    # `json.dumps` by accident and would make the in-memory payload disagree
    # with the bytes on disk.
    assert verdict["stated_by"] == []
    assert isinstance(verdict["stated_by"], list)


def test_an_absent_tier_and_an_absent_verdict_both_serialize_as_null() -> None:
    """contracts.md record schema: `None` as `null`, at both nesting levels.

    The two `None` cases are different facts — no judgement ran at all, versus a
    classification that ran and produced no verdict (`tier: none` on a `bug`) —
    and both must reach the record as `null` rather than as an omitted key.
    """
    assert spec_change_tier_to_dict(tier=None) is None
    classified_without_a_verdict = SpecChangeTier(
        tier="none",
        linked_proposal_topic=None,
        verdict=None,
        judged_at=_JUDGED_AT,
    )
    serialized = spec_change_tier_to_dict(tier=classified_without_a_verdict)
    assert serialized is not None
    assert serialized["verdict"] is None
    assert serialized["linked_proposal_topic"] is None


def test_every_appended_record_carries_the_key_even_with_no_tier(tmp_path: Path) -> None:
    """contracts.md record schema: `spec_change_tier` is always written explicitly.

    Control: the read path reads an ABSENT key as `null`, so a write path that
    forgot the key emits records indistinguishable from legacy ones. Asserting
    PRESENCE on a record carrying no tier is what catches that.
    """
    path = tmp_path / "work-items.jsonl"
    payload = _appended_payload(path=path, item=_item(), spec_change_tier=None)
    assert "spec_change_tier" in payload
    assert payload["spec_change_tier"] is None


def test_a_feature_at_spec_change_tier_is_written_with_its_linked_topic(
    tmp_path: Path,
) -> None:
    """contracts.md "capture-work-item": a `partial`/`unstated` feature is spec-change tier.

    The record carries `tier: spec-change`, the verdict it was derived from, and
    the canonical topic of the linked proposed change. Control: a write path
    that dropped the topic leaves a spec-change record nobody can trace to the
    proposal that would state the behaviour.
    """
    path = tmp_path / "work-items.jsonl"
    payload = _appended_payload(path=path, item=_item(), spec_change_tier=_spec_change_tier())
    tier = payload["spec_change_tier"]
    assert tier["tier"] == "spec-change"
    assert tier["linked_proposal_topic"] == _TOPIC
    assert tier["verdict"]["kind"] == "unstated"
    assert tier["verdict"]["generalization_target"] == _HEADING


def test_a_record_carrying_a_tier_still_reads_back_through_the_store(tmp_path: Path) -> None:
    """contracts.md record schema: the key is schema-allowed, so the record parses.

    The write path validates against the same schema the read path enforces, so
    a key the validator does not know makes `append_work_item` refuse its own
    output. Control: omitting the key from the allowed set fails here rather
    than at the first read of a real store.
    """
    path = tmp_path / "work-items.jsonl"
    _ = _appended_payload(path=path, item=_item(), spec_change_tier=_spec_change_tier())
    result = read_work_items(path=path)
    assert isinstance(result, IOSuccess)
    read_back = unsafe_perform_io(result.unwrap())
    assert [one.id for one in read_back] == ["li-tier01"]


def test_the_serializer_takes_the_tier_by_keyword_only() -> None:
    """constraints.md "Inherited from livespec": keyword-only arguments everywhere.

    Control: a positional call raises, which is what the repo-wide
    `keyword_only_args` check enforces statically and this pins behaviourally.
    """
    with pytest.raises(TypeError):
        _ = spec_change_tier_to_dict(None)  # type: ignore[misc]

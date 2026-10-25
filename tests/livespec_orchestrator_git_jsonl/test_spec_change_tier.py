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
from typing import Any, get_args, get_type_hints

import pytest
from livespec_orchestrator_git_jsonl.errors import SchemaViolationError
from livespec_orchestrator_git_jsonl.spec_change_tier import (
    SPEC_CHANGE_TIER_VALUES,
    SPEC_CHANGE_VERDICT_KINDS,
    parse_spec_change_tier,
    spec_change_tier_to_dict,
)
from livespec_orchestrator_git_jsonl.store import append_work_item, read_work_items
from livespec_orchestrator_git_jsonl.types import WorkItem
from livespec_runtime.spec_stated import SpecChangeTier, SpecStatedVerdict
from returns.io import IOSuccess
from returns.result import Failure, Result, Success
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


# -- the read path: `parse_spec_change_tier` ---------------------------------
#
# The parser is the ONE authority on the tier's shape: the write path validates
# through it too (`store_schema._spec_change_tier_error`), so every refusal
# below is simultaneously a refusal `append_work_item` makes. That is why the
# ill-shaped cases are exercised here as parses rather than as appends — a
# second account of the shape is exactly what would let the write path admit a
# record the read path then refuses, stranding the filing on disk as a line
# nobody can materialize.


def _parsed(*, tier: object) -> Result[SpecChangeTier | None, SchemaViolationError]:
    return parse_spec_change_tier(
        path=Path("work-items.jsonl"),
        line_number=1,
        parsed={"spec_change_tier": tier},
    )


def _refusal(*, tier: object) -> str:
    result = _parsed(tier=tier)
    assert isinstance(result, Failure)
    return result.failure().detail


def _tier_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "tier": "spec-change",
        "linked_proposal_topic": _TOPIC,
        "verdict": {
            "kind": "unstated",
            "stated_by": [],
            "generalization_target": _HEADING,
            "rationale": "no ratified clause states this filing behaviour",
        },
        "judged_at": _JUDGED_AT,
    }
    payload.update(overrides)
    return payload


def test_the_two_tier_values_are_the_ones_the_vendored_dataclass_annotates() -> None:
    """contracts.md record schema: the tier vocabulary is the dataclass's own.

    The vendored `SpecChangeTier` annotates `tier` with a bare inline
    `Literal`, so this module spells the pair rather than importing it. Control:
    a release that renames or widens the annotation fails here, where a human
    reads the diff — rather than in a parser that quietly refuses every record
    carrying the new value.
    """
    annotated = get_args(get_type_hints(SpecChangeTier)["tier"])
    assert set(SPEC_CHANGE_TIER_VALUES) == set(annotated)
    assert set(SPEC_CHANGE_VERDICT_KINDS) == {"partial", "unstated"}


def test_an_absent_key_and_an_explicit_null_both_read_as_no_tier() -> None:
    """contracts.md record schema: `spec_change_tier` is OPTIONAL on the read path.

    A legacy record authored before the field, and a record explicitly carrying
    `null`, are both "no classification ran". Control: refusing the absent key
    would make every pre-v022 line a schema violation.
    """
    absent = parse_spec_change_tier(path=Path("w.jsonl"), line_number=1, parsed={})
    assert isinstance(absent, Success)
    assert absent.unwrap() is None
    explicit = _parsed(tier=None)
    assert isinstance(explicit, Success)
    assert explicit.unwrap() is None


def test_a_well_formed_tier_round_trips_through_the_serializer() -> None:
    """The parse is the serializer's inverse, which is what makes the key durable.

    Control: a closing or amending record has to carry the chain head's tier
    forward, so a reader that could not reconstruct the value it read would
    lose it at the next append.
    """
    original = _spec_change_tier()
    result = _parsed(tier=spec_change_tier_to_dict(tier=original))
    assert isinstance(result, Success)
    assert result.unwrap() == original


def test_a_spec_change_tier_without_an_earning_verdict_is_refused() -> None:
    """contracts.md record schema: `spec-change` needs a `partial`/`unstated` verdict.

    Both ways of failing to earn it are refused — a null verdict, and a
    `stated` one. Control: downgrading either to `tier: none` would silently
    lose a filing the maintainer was told had a spec change owed, and admitting
    it would let the tier that routes work to a proposal be written by anyone.
    """
    assert "without a verdict" in _refusal(tier=_tier_payload(verdict=None))
    stated = {
        "kind": "stated",
        "stated_by": [_HEADING],
        "generalization_target": None,
        "rationale": "the ratified text already states this",
    }
    assert "without a verdict" in _refusal(tier=_tier_payload(verdict=stated))


def test_a_tier_of_none_may_carry_a_stated_verdict() -> None:
    """contracts.md "capture-work-item": a `feature` judged `stated` is tier `none`.

    The judgement ran and answered; recording the answer beside `tier: none` is
    what distinguishes it from a filing nobody judged. Control: refusing the
    pair would force the skill to discard a verdict it was required to obtain.
    """
    stated = {
        "kind": "stated",
        "stated_by": [_HEADING],
        "generalization_target": None,
        "rationale": "the ratified text already states this",
    }
    result = _parsed(tier=_tier_payload(tier="none", linked_proposal_topic=None, verdict=stated))
    assert isinstance(result, Success)
    parsed = result.unwrap()
    assert parsed is not None
    assert parsed.tier == "none"
    assert parsed.verdict is not None
    assert parsed.verdict.kind == "stated"
    assert parsed.verdict.stated_by == (_HEADING,)


def test_a_tier_that_is_not_an_object_is_refused() -> None:
    """contracts.md record schema: the key is "object or `null`" and nothing else."""
    assert "must be object or null" in _refusal(tier="spec-change")


def test_a_tier_missing_its_own_keys_names_every_one_of_them() -> None:
    """All four missing keys are named at once, not the first one.

    A tier object is authored by a skill prompt at one moment per filing, and
    each re-run costs a model call. Control: naming only the first would make
    the operator pay four.
    """
    detail = _refusal(tier={})
    for name in ("tier", "linked_proposal_topic", "verdict", "judged_at"):
        assert name in detail


def test_a_tier_value_outside_the_vocabulary_is_refused() -> None:
    """contracts.md record schema: the tier is one of the two enumerated values."""
    assert "not in allowed set" in _refusal(tier=_tier_payload(tier="maybe-spec-change"))


def test_a_verdict_that_is_not_an_object_is_refused() -> None:
    """The nested verdict is "object or null" on the same terms as the tier."""
    assert "verdict' must be object or null" in _refusal(tier=_tier_payload(verdict="unstated"))


def test_a_verdict_missing_its_own_keys_is_refused() -> None:
    """The nested object owes all four of the shared dataclass's fields."""
    detail = _refusal(tier=_tier_payload(verdict={"kind": "unstated"}))
    assert "verdict' missing required keys" in detail


@pytest.mark.parametrize(
    "overrides",
    [
        {"kind": "probably"},
        {"stated_by": "## not a list"},
        {"stated_by": [7]},
        {"generalization_target": 7},
        {"rationale": None},
    ],
)
def test_an_ill_shaped_verdict_field_is_refused(overrides: dict[str, object]) -> None:
    """Each of the four verdict fields is graded, and any one of them refuses.

    Control: a parser that checked only `kind` would accept a `stated_by`
    carrying integers, and the propose-change handoff would then name a heading
    that is not a string at all.
    """
    verdict: dict[str, object] = {
        "kind": "unstated",
        "stated_by": [],
        "generalization_target": _HEADING,
        "rationale": "r",
    }
    verdict.update(overrides)
    assert "needs a kind in" in _refusal(tier=_tier_payload(verdict=verdict))


@pytest.mark.parametrize(
    "overrides",
    [{"judged_at": None}, {"linked_proposal_topic": 7}],
)
def test_an_ill_shaped_timestamp_or_topic_is_refused(overrides: dict[str, object]) -> None:
    """`judged_at` is a string; `linked_proposal_topic` is a string or null.

    Control: a non-string topic reaches the propose-change handoff as a slug
    nobody can resolve, and a null `judged_at` loses which judgement the tier
    came from.
    """
    assert "needs a string 'judged_at'" in _refusal(tier=_tier_payload(**overrides))

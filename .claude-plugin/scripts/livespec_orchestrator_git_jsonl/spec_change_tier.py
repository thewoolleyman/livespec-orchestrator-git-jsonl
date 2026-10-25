"""The `spec_change_tier` record key — this realization's codec for it.

The work-items record schema in `SPECIFICATION/contracts.md` makes the key
"object or `null` ... always written explicitly on append", and defines a
non-null value as "the JSON serialization of the vendored release's
`livespec_runtime.spec_stated.SpecChangeTier`: one key per dataclass field under
the field's own name, a nested `SpecStatedVerdict` serialized the same way (a
tuple field as a JSON array), and `None` as `null`".

WHY THE TIER IS NOT A FIELD OF `WorkItem`. The work-item MODEL is the SHARED
surface `livespec_runtime.work_items.types` owns, and the shared dataclass
carries no `spec_change_tier`: the tier is persisted by the two ORCHESTRATOR
realizations, each in its own substrate — labels on the beads tenant, this key
in the JSONL record. So the value travels beside the item through this module's
functions rather than inside it, which is also why `append_work_item` takes it
as its own keyword argument.

WHY `None` AND `tier: "none"` ARE DIFFERENT ANSWERS, and must not be collapsed.
`None` means no classification ran at all — an `epic`, a gap-tied record filed
by `capture-impl-gaps`, a legacy record, or a judgement that could not run.
`tier: "none"` means the classification DID run and reported that no spec change
is owed. Reading the second as the first would make a judged `bug` look
unjudged, and re-judging it costs a model call per filing; reading the first as
the second would claim a judgement nobody made.

WHY THE KEY SET IS ASSERTED AGAINST THE DATACLASS IN THE TESTS RATHER THAN
DERIVED HERE. The serializers below name their fields explicitly, because a
`dataclasses.asdict` walk has to be re-typed field by field anyway to satisfy
strict typing and to turn tuples into JSON arrays — and the walk's generality is
not free: it would also serialize a field the vendored release adds for its OWN
use without this store ever deciding to persist it. The paired tests take the
expected key set from `dataclasses.fields`, so a release that adds a field fails
there, where a human reads the diff and decides, instead of silently widening
the record schema.
"""

from typing import Any

from livespec_runtime.spec_stated import SpecChangeTier, SpecStatedVerdict

__all__: list[str] = [
    "SPEC_CHANGE_TIER_KEY",
    "spec_change_tier_to_dict",
]

SPEC_CHANGE_TIER_KEY = "spec_change_tier"


def spec_change_tier_to_dict(*, tier: SpecChangeTier | None) -> dict[str, Any] | None:
    """One tier as the record carries it, or `None` when no classification ran."""
    if tier is None:
        return None
    return {
        "tier": tier.tier,
        "linked_proposal_topic": tier.linked_proposal_topic,
        "verdict": _verdict_to_dict(verdict=tier.verdict),
        "judged_at": tier.judged_at,
    }


def _verdict_to_dict(*, verdict: SpecStatedVerdict | None) -> dict[str, Any] | None:
    """One verdict as the record carries it, its tuple field as a JSON array.

    The tuple is converted EXPLICITLY rather than left to `json.dumps`, which
    happens to accept one: a tuple survives the dump, so the in-memory payload
    the write path validates would disagree with the dict a reader gets back
    from the bytes on disk, and an equality assertion over either would be
    comparing two different shapes.
    """
    if verdict is None:
        return None
    return {
        "kind": verdict.kind,
        "stated_by": list(verdict.stated_by),
        "generalization_target": verdict.generalization_target,
        "rationale": verdict.rationale,
    }

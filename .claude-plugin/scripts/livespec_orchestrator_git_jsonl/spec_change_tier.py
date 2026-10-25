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

from pathlib import Path
from typing import Any, get_args

from livespec_runtime.spec_stated import SpecChangeTier, SpecStatedVerdict, StatedKind
from returns.result import Failure, Result, Success

from livespec_orchestrator_git_jsonl.errors import SchemaViolationError

__all__: list[str] = [
    "SPEC_CHANGE_TIER_KEY",
    "SPEC_CHANGE_TIER_VALUES",
    "SPEC_CHANGE_VERDICT_KINDS",
    "parse_spec_change_tier",
    "spec_change_tier_to_dict",
]

SPEC_CHANGE_TIER_KEY = "spec_change_tier"

# The two tiers the contract enumerates. The vendored dataclass annotates its
# own `tier` field with a bare inline `Literal` rather than a named alias, so
# there is nothing to read them off; the paired tests pin this tuple against
# that annotation instead.
SPEC_CHANGE_TIER_VALUES: tuple[str, ...] = ("spec-change", "none")

# The verdict kinds that make a spec change owed. The contract: "A record whose
# `tier` is `spec-change` MUST carry a non-null verdict whose kind is `partial`
# or `unstated`." Derived by SUBTRACTION from the module's own `StatedKind`, so
# a kind the shared judgement adds later is treated as NOT spec-change until
# somebody decides otherwise — the fail-closed direction, because the
# alternative admits an unreviewed kind into the one tier that routes work to a
# proposed change.
SPEC_CHANGE_VERDICT_KINDS: tuple[str, ...] = tuple(
    kind for kind in get_args(StatedKind) if kind != "stated"
)

_VERDICT_FIELDS = ("kind", "stated_by", "generalization_target", "rationale")
_TIER_FIELDS = ("tier", "linked_proposal_topic", "verdict", "judged_at")


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


def parse_spec_change_tier(
    *, path: Path, line_number: int, parsed: dict[str, Any]
) -> Result[SpecChangeTier | None, SchemaViolationError]:
    """The tier one record carries, or `None`, or a refusal naming what is wrong.

    An ABSENT key and an explicit `null` both yield `Success(None)`: the key is
    optional on the read path so records authored before it parse, and a reader
    that distinguished the two could say nothing more about either.

    A tier of `spec-change` with no `partial`/`unstated` verdict is REFUSED
    rather than downgraded. The tier is what routes the item to a proposed
    change, so a record claiming it without the judgement that earned it is a
    claim no reader can check — and reading it as `none` instead would silently
    lose a filing the maintainer was told had a spec change owed.
    """
    value = parsed.get(SPEC_CHANGE_TIER_KEY)
    if value is None:
        return Success(None)
    if not isinstance(value, dict):
        return Failure(
            _violation(
                path=path,
                line_number=line_number,
                detail=(
                    f"field {SPEC_CHANGE_TIER_KEY!r} must be object or null, "
                    f"got {type(value).__name__}"
                ),
            )
        )
    payload: dict[str, Any] = value
    return _tier_from(path=path, line_number=line_number, payload=payload)


def _tier_from(
    *, path: Path, line_number: int, payload: dict[str, Any]
) -> Result[SpecChangeTier | None, SchemaViolationError]:
    """One tier out of an object already established to BE an object."""
    shape = _missing_fields_error(
        path=path,
        line_number=line_number,
        payload=payload,
        fields=_TIER_FIELDS,
        label=SPEC_CHANGE_TIER_KEY,
    )
    if shape is not None:
        return Failure(shape)
    tier = payload["tier"]
    if tier not in SPEC_CHANGE_TIER_VALUES:
        return Failure(
            _violation(
                path=path,
                line_number=line_number,
                detail=(
                    f"field 'spec_change_tier.tier' value {tier!r} not in allowed "
                    f"set {list(SPEC_CHANGE_TIER_VALUES)}"
                ),
            )
        )
    verdict_result = _verdict_from(path=path, line_number=line_number, payload=payload)
    if isinstance(verdict_result, Failure):
        return Failure(verdict_result.failure())
    return _assembled(
        path=path,
        line_number=line_number,
        payload=payload,
        verdict=verdict_result.unwrap(),
    )


def _assembled(
    *,
    path: Path,
    line_number: int,
    payload: dict[str, Any],
    verdict: SpecStatedVerdict | None,
) -> Result[SpecChangeTier | None, SchemaViolationError]:
    """The tier, once its verdict is the one its own `tier` value requires."""
    tier = payload["tier"]
    earned = verdict is not None and verdict.kind in SPEC_CHANGE_VERDICT_KINDS
    if tier == "spec-change" and not earned:
        return Failure(
            _violation(
                path=path,
                line_number=line_number,
                detail=(
                    "field 'spec_change_tier' carries tier 'spec-change' without a "
                    f"verdict whose kind is one of {list(SPEC_CHANGE_VERDICT_KINDS)}"
                ),
            )
        )
    topic = payload["linked_proposal_topic"]
    judged_at = payload["judged_at"]
    if not isinstance(judged_at, str) or (topic is not None and not isinstance(topic, str)):
        return Failure(
            _violation(
                path=path,
                line_number=line_number,
                detail=(
                    "field 'spec_change_tier' needs a string 'judged_at' and a string "
                    "or null 'linked_proposal_topic'"
                ),
            )
        )
    return Success(
        SpecChangeTier(
            tier=tier,
            linked_proposal_topic=topic,
            verdict=verdict,
            judged_at=judged_at,
        )
    )


def _verdict_from(
    *, path: Path, line_number: int, payload: dict[str, Any]
) -> Result[SpecStatedVerdict | None, SchemaViolationError]:
    """The verdict a tier object carries, or `None`, or a refusal."""
    value = payload["verdict"]
    if value is None:
        return Success(None)
    if not isinstance(value, dict):
        return Failure(
            _violation(
                path=path,
                line_number=line_number,
                detail=(
                    "field 'spec_change_tier.verdict' must be object or null, "
                    f"got {type(value).__name__}"
                ),
            )
        )
    verdict: dict[str, Any] = value
    shape = _missing_fields_error(
        path=path,
        line_number=line_number,
        payload=verdict,
        fields=_VERDICT_FIELDS,
        label="spec_change_tier.verdict",
    )
    if shape is not None:
        return Failure(shape)
    return _verdict_values(path=path, line_number=line_number, verdict=verdict)


def _verdict_values(
    *, path: Path, line_number: int, verdict: dict[str, Any]
) -> Result[SpecStatedVerdict | None, SchemaViolationError]:
    """One verdict's typed values, refused when any of the four is ill-shaped.

    The four are graded as ONE condition rather than one refusal each, because
    a tier object is authored by a skill prompt at exactly one moment per
    filing: an operator who has to re-run the filing once per ill-shaped field
    pays a model call each time.
    """
    kind = verdict["kind"]
    stated_by = verdict["stated_by"]
    target = verdict["generalization_target"]
    rationale = verdict["rationale"]
    headings: list[Any] = stated_by if isinstance(stated_by, list) else []
    well_shaped = (
        kind in get_args(StatedKind)
        and isinstance(stated_by, list)
        and all(isinstance(heading, str) for heading in headings)
        and (target is None or isinstance(target, str))
        and isinstance(rationale, str)
    )
    if not well_shaped:
        return Failure(
            _violation(
                path=path,
                line_number=line_number,
                detail=(
                    "field 'spec_change_tier.verdict' needs a kind in "
                    f"{list(get_args(StatedKind))}, a list of heading strings, a string "
                    "or null generalization_target, and a string rationale"
                ),
            )
        )
    return Success(
        SpecStatedVerdict(
            kind=kind,
            stated_by=tuple(str(heading) for heading in headings),
            generalization_target=target,
            rationale=rationale,
        )
    )


def _missing_fields_error(
    *,
    path: Path,
    line_number: int,
    payload: dict[str, Any],
    fields: tuple[str, ...],
    label: str,
) -> SchemaViolationError | None:
    """Refuse an object missing any of its own keys, naming EVERY one of them."""
    missing = [one for one in fields if one not in payload]
    if not missing:
        return None
    return _violation(
        path=path,
        line_number=line_number,
        detail=f"field {label!r} missing required keys: {missing}",
    )


def _violation(*, path: Path, line_number: int, detail: str) -> SchemaViolationError:
    return SchemaViolationError(path=path, line_number=line_number, detail=detail)


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

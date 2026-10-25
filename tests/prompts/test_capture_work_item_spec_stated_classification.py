"""`capture-work-item` classifies every filed item through the shared judgement.

The `capture-work-item` clause of `SPECIFICATION/contracts.md`: "Before
appending, the skill MUST classify the item as `feature`, `bug`, `chore` or
`non_functional` through the `classify` function of the same
`livespec_runtime.spec_stated` module, passing the supplied `type` as evidence
rather than as the answer". An `epic` is not classified, and a classification
that cannot run is reported to the user with the record appended carrying
`spec_change_tier: null`.

WHY "BEFORE APPENDING" IS ASSERTED AS AN ORDER AND NOT AS A SENTENCE. The whole
point of the clause is that the tier is decided while the record can still carry
it: a skill that appends and then classifies has produced a record whose
`spec_change_tier` nobody can set without appending a second, amending record —
and the materialized view would carry a filing with no tier at all. A prose
assertion that the skill "classifies before appending" is satisfied by a prompt
whose STEPS do the opposite, so the position of the classification step relative
to the append is what this module measures.

WHY THE FOUR CLASS NAMES ARE DERIVED FROM THE MODULE. `classify` refuses an
answer outside its own four-member vocabulary, so a prompt naming a fifth class,
or misspelling one of the four, yields a `Failure` at every invocation — a
failure mode that looks exactly like "no model available" and therefore reports
as an un-runnable judgement rather than as the typo it is. The names come from
`ItemClass` so the prompt is checked against the vocabulary the parser actually
enforces.

PROMPT PROSE IS HARD-WRAPPED, so every needle below is short enough to sit
WITHIN one physical line.
"""

from __future__ import annotations

from pathlib import Path
from typing import get_args

from livespec_runtime.spec_stated import CLASSIFY_PROMPT, ItemClass, classify

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SKILL = _REPO_ROOT / ".claude-plugin" / "skills" / "capture-work-item" / "SKILL.md"

_MODULE = "livespec_runtime.spec_stated"

# The append the classification must precede. The store's own write entry point,
# so the needle cannot match a loose mention of "append" in running prose.
_APPEND_CALL = "append_work_item("

# One physical line of the module's own classification prompt, so a prose copy
# of it carries this verbatim.
_PROMPT_FRAGMENT = "Classify ONE work item into exactly one class."

# The three classes the clause excludes from spec-change tier, derived from the
# module's own vocabulary rather than spelled out here — a hand-written triple
# keeps passing after `ItemClass` gains or renames a member, which is the one
# change that would make this test's scope wrong.
_NON_FEATURE_CLASSES = tuple(one for one in get_args(ItemClass) if one != "feature")

# The two values the clause requires a non-feature record to carry, in the
# ratified spelling of `SPECIFICATION/contracts.md` — "is recorded with
# `tier: none` and `verdict: null`".
_NO_TIER = "`tier: none`"
_NO_VERDICT = "`verdict: null`"

# Scenario 6 step 6: filing a `bug` "yields a record whose `spec_change_tier.tier`
# is `none` ... no proposal is offered". The absence of the handoff is an
# obligation of its own, so it carries its own needle.
_NO_PROPOSAL = "no proposal is offered"


def _skill_text() -> str:
    return _SKILL.read_text(encoding="utf-8")


def test_the_classification_names_the_shared_module_and_its_classify_function() -> None:
    """contracts.md "capture-work-item": classification goes through `classify`.

    Control: a skill classifying by its own reading of the title names neither
    the module nor `classify` and fails here.
    """
    text = _skill_text()
    assert _MODULE in text
    assert f"{classify.__name__}(" in text


def test_every_class_of_the_modules_own_vocabulary_is_named() -> None:
    """contracts.md "capture-work-item": the four classes are the module's four.

    Control: a prompt naming `non-functional` with a hyphen, or omitting
    `chore`, fails here — and would otherwise fail inside `classify`'s parser as
    an un-runnable judgement rather than as a typo.
    """
    text = _skill_text()
    assert set(get_args(ItemClass)) == {"feature", "bug", "chore", "non_functional"}
    for name in get_args(ItemClass):
        assert name in text


def test_the_supplied_type_is_passed_as_evidence_rather_than_as_the_answer() -> None:
    """contracts.md "capture-work-item": the stored type is evidence, not the answer.

    The user supplies a `type`; the clause makes it an INPUT to the judgement
    rather than its result, because the supplied type is routinely wrong and
    trusting it would skip the judgement for exactly the items that need it.
    Control: a skill treating the supplied type as the class carries neither
    needle.
    """
    text = _skill_text()
    assert "item_type=" in text
    assert "as evidence" in text


def test_the_classification_precedes_the_append() -> None:
    """contracts.md "capture-work-item": "Before appending, the skill MUST classify".

    Measured as a position, not as a promise — see the module docstring.
    Control: moving the classification step after the append step fails here
    while every needle-based assertion above still passes.
    """
    text = _skill_text()
    classify_at = text.find(f"{classify.__name__}(")
    append_at = text.find(_APPEND_CALL)
    assert classify_at >= 0
    assert append_at >= 0
    assert classify_at < append_at


def test_an_epic_is_not_classified() -> None:
    """contracts.md "capture-work-item": "An `epic` is not classified."

    An epic is a container for other items rather than a behaviour of its own,
    so there is nothing for the judgement to read. Control: a prompt that
    classifies every type regardless carries no epic carve-out.
    """
    text = _skill_text()
    assert "`epic` is not classified" in text


def test_a_judgement_that_cannot_run_is_reported_and_files_a_null_tier() -> None:
    """contracts.md "capture-work-item": an un-runnable judgement is said out loud.

    "the skill MUST say so to the user and append the record with
    `spec_change_tier: null`". Both halves matter: a silent null tier is
    indistinguishable from a legacy record, and a refusal to file at all loses
    the work-item the user asked for. Control: dropping either half fails here.
    """
    text = _skill_text()
    assert "`spec_change_tier: null`" in text
    assert "say so to the user" in text


def _between(*, text: str, start: str, end: str) -> str:
    """The text from the first `start` up to the first `end` after it, or "".

    The POSITIONAL scope the non-feature branch is asserted inside. A branch is
    only useful where the agent reads it — after it has a class in hand and
    before it files — so the region is bounded by the two calls that mark those
    moments rather than by a heading, which lets the prose be reorganized
    without rewriting this test.

    "" for either marker missing, so an absent landmark certifies nothing.
    """
    opened = text.find(start)
    if opened < 0:
        return ""
    closed = text.find(end, opened)
    if closed < 0:
        return ""
    return text[opened:closed]


def test_the_region_locator_spans_the_two_markers_and_nothing_else() -> None:
    # Positive + negative controls for the locator the assertion below rests
    # on, per this tree's convention: a locator that silently matches nothing
    # certifies prose it never read.
    document = "before\nSTART\ninside\nEND\nafter\n"
    found = _between(text=document, start="START", end="END")
    assert "inside" in found
    assert "before" not in found
    assert "after" not in found
    assert _between(text=document, start="ABSENT", end="END") == ""
    assert _between(text=document, start="START", end="ABSENT") == ""


def test_a_non_feature_class_is_filed_without_a_spec_change_tier() -> None:
    """contracts.md "capture-work-item": a non-feature carries no spec-change tier.

    "An item classified `bug`, `chore` or `non_functional` is not spec-change
    tier and is recorded with `tier: none` and `verdict: null`", and scenario 6
    step 6 adds that no proposal is offered for one.

    ASSERTED IN THE REGION BETWEEN CLASSIFYING AND FILING, because that is the
    only place the branch does any work. The three class names appear in the
    skill already — Step 2 lists the vocabulary `classify` returns — so a
    whole-file needle passes for a prompt that names the classes and then tells
    the agent nothing about what to do with three of them. Such a prompt leaves
    a `bug` falling through a step titled for features, reaching the append with
    no tier assembled at all; the record is then written without the field the
    clause requires, or with whatever the feature branch's snippet happened to
    leave bound. Control: moving these sentences above the classification, or
    below the append, fails here while every needle still exists in the file.
    """
    branch = _between(text=_skill_text(), start=f"{classify.__name__}(", end=_APPEND_CALL)
    for one in _NON_FEATURE_CLASSES:
        assert f"`{one}`" in branch
    assert _NO_TIER in branch
    assert _NO_VERDICT in branch
    assert _NO_PROPOSAL in branch


def test_the_skill_defines_no_classification_prompt_of_its_own() -> None:
    """contracts.md "capture-work-item": the model is reached through the module.

    Proved by absence: the module's own `CLASSIFY_PROMPT` must not be copied
    into the prose, because a copy is a second authority that drifts the moment
    the module is revised. Control: the fragment is read from `CLASSIFY_PROMPT`
    itself, so it stays the module's wording rather than this test's guess.
    """
    assert _PROMPT_FRAGMENT in CLASSIFY_PROMPT
    assert _PROMPT_FRAGMENT not in _skill_text()

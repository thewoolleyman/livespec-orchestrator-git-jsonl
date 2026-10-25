"""`capture-spec-drift` takes every verdict from the shared spec-stated judgement.

The `capture-spec-drift` clause of `SPECIFICATION/contracts.md` makes BOTH of the
skill's drift sources — the impl → spec heuristic and the ledger-intent scan — ask
one question through one authority: "each candidate is then judged by the
spec-stated judgement of the `livespec_runtime.spec_stated` module", obtained
"from the module's `judge` function", and the skill "MUST NOT define a
stated/unstated prompt, verdict schema or verdict parser of its own".

WHY THIS IS A PROMPT TEST. `capture-spec-drift` is one of the four HEAVYWEIGHT
AUTHORED skills, so its SKILL.md IS its implementation — the contract explicitly
reserves the thin-transport `bin/` shape for the other three. There is no Python
call site to unit-test, so the instruction the agent reads is the only artifact
that can carry the obligation, and this module is what stops it drifting away
from the module it is required to consume.

WHY BOTH SOURCES ARE ASSERTED SEPARATELY, and why locality matters. A skill that
named `judge` once, anywhere, would satisfy a whole-file needle while leaving one
of its two sources deciding drift by its own reading — which is the exact failure
the shared judgement exists to prevent, and it is SILENT: a finding a private
reading produced is well-formed and routes through the per-finding consent flow
exactly as a judged one does, costing the maintainer a proposal against a clause
that already states the behaviour. So each source's own section is located first
and the needles are asserted INSIDE it.

WHY THE PROHIBITION IS ASSERTED AS AN ABSENCE. "MUST NOT define a ... prompt,
verdict schema or verdict parser of its own" cannot be proved by anything the
skill says; it is proved by what the skill does not carry. The needles are taken
from the module's OWN `JUDGE_PROMPT`, so a prose copy of it fails here rather
than silently becoming a second authority on the same question.

PROMPT PROSE IS HARD-WRAPPED, so every needle below is short enough to sit
WITHIN one physical line. A needle straddling a line break can only fail
silently while the prose says exactly the thing.
"""

from __future__ import annotations

from pathlib import Path

from livespec_runtime.spec_stated import JUDGE_PROMPT, judge

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SKILL = _REPO_ROOT / ".claude-plugin" / "skills" / "capture-spec-drift" / "SKILL.md"

# The module the contract names, spelled as an import target so the needle
# cannot match a loose mention of "spec stated" in running prose.
_MODULE = "livespec_runtime.spec_stated"

# How each source's section is found. A SUBSTRING of the heading rather than the
# whole heading, so re-wording the heading around these two words stays passing
# while deleting the section itself fails.
_IMPL_SOURCE_MARKER = "impl candidate"
_LEDGER_SOURCE_MARKER = "Ledger-intent scan"

# The four work-item fields the ledger-intent scan reads, per the clause.
_INTENT_FIELDS = ("title", "description", "acceptance_criteria", "reason")

# Fragments of the module's own prompt. Each is one physical line of
# `JUDGE_PROMPT`, so a prose copy of the prompt carries it verbatim.
_PROMPT_FRAGMENTS = (
    "You are judging ONE behaviour statement against a RATIFIED specification.",
    '{{"kind": "stated" | "partial" | "unstated",',
)


def _skill_text() -> str:
    return _SKILL.read_text(encoding="utf-8")


def _section_containing(*, text: str, marker: str) -> str:
    """The `###` section whose heading carries `marker`, or `""` when absent.

    `""` rather than a raised lookup error: an absent section must fail on the
    needle assertion that names what the section owes, not on a traceback that
    names only the heading the test happened to look for.
    """
    collected: list[str] = []
    inside = False
    for line in text.splitlines():
        if line.startswith(("## ", "### ")):
            inside = line.startswith("### ") and marker in line
            if inside:
                collected.append(line)
            continue
        if inside:
            collected.append(line)
    return "\n".join(collected)


def test_the_section_locator_finds_a_marked_section_and_nothing_else() -> None:
    # Positive + negative control for the locator the three assertions below
    # rest on: a section whose heading carries the marker is returned with its
    # body and WITHOUT the following section's, and an absent marker yields "".
    document = "### Alpha thing\nbody a\n\n### Beta thing\nbody b\n"
    found = _section_containing(text=document, marker="Alpha")
    assert "body a" in found
    assert "body b" not in found
    assert _section_containing(text=document, marker="Gamma") == ""


def test_the_impl_drift_front_end_judges_each_candidate_through_the_shared_module() -> None:
    """contracts.md "capture-spec-drift": each impl candidate is judged by the module.

    The impl → spec heuristic extracts candidate behaviour statements and then
    obtains each one's verdict from the shared module's `judge` function.
    Control: a section deciding the verdict by its own reading — the retired
    "is this reflected in the Specification? (yes / no / partial)" self-question —
    names neither the module nor `judge` and fails here.
    """
    section = _section_containing(text=_skill_text(), marker=_IMPL_SOURCE_MARKER)
    assert _MODULE in section
    assert f"{judge.__name__}(" in section
    assert "generalization_target" in section


def test_the_ledger_intent_scan_judges_each_item_through_the_shared_module() -> None:
    """contracts.md "capture-spec-drift": the ledger-intent scan uses the same judgement.

    "Whether intent is reflected MUST be decided by the same spec-stated
    judgement, reading the four fields named above; an item's `type` is never a
    detection exclusion." Control: a scan absent from the skill, or one deciding
    reflectedness itself, carries neither the module nor the four fields.
    """
    section = _section_containing(text=_skill_text(), marker=_LEDGER_SOURCE_MARKER)
    assert _MODULE in section
    assert f"{judge.__name__}(" in section
    for field in _INTENT_FIELDS:
        assert field in section


def test_a_stated_verdict_produces_no_finding_in_either_source() -> None:
    """contracts.md "capture-spec-drift": a `stated` verdict is not drift.

    "A candidate the judgement reports `stated` MUST NOT become a finding", and
    the ledger scan "MUST NOT emit a finding for intent already reflected in the
    spec". Both sections must carry the filter, because a source that omits it
    costs the maintainer a proposal against a clause that already states the
    behaviour. Control: dropping the sentence from either section fails here.
    """
    text = _skill_text()
    for marker in (_IMPL_SOURCE_MARKER, _LEDGER_SOURCE_MARKER):
        assert "produces no finding" in _section_containing(text=text, marker=marker)


def test_the_skill_defines_no_judgement_prompt_or_verdict_schema_of_its_own() -> None:
    """contracts.md "capture-spec-drift": no private prompt, schema or parser.

    The prohibition is proved by absence: the module's own `JUDGE_PROMPT` lines
    must not appear in the skill, because a prose copy is a second authority on
    the same question that drifts the moment the module is revised. Control: the
    fragments are read from `JUDGE_PROMPT` itself, so they stay the module's
    wording rather than this test's guess at it.
    """
    text = _skill_text()
    for fragment in _PROMPT_FRAGMENTS:
        assert fragment in JUDGE_PROMPT
        assert fragment not in text

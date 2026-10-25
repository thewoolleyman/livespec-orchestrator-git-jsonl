# tests/prompts/

Prompt-conformance tests for the FOUR heavyweight authored skills
(`capture-impl-gaps`, `capture-spec-drift`, `capture-work-item`,
`implement`).

Why this tier exists. Those four skills have no `bin/` implementation:
`SPECIFICATION/contracts.md` reserves the thin-transport
SKILL.md-over-Python shape for the other three and makes the heavyweight
skills' SKILL.md their own implementation. So for them an obligation the
contract states has no Python call site to unit-test, and the only
artifact that can carry it is the instruction the agent reads. These
tests bind that prose, so a contract clause and the prompt realizing it
cannot drift apart silently.

Conventions:

- Needles come from the MODULE the prompt is required to consume
  (imported constants, `callable.__name__`) wherever one exists, never
  from a literal this test invented. A prompt asserted against a
  hand-copied constant passes while the module moves underneath it.
- Prompt prose is HARD-WRAPPED, so every needle must sit within one
  physical line. A needle straddling a line break fails silently while
  the prose says exactly the thing.
- Locality matters. When a clause binds two surfaces of one prompt,
  locate each surface's own section and assert inside it; a whole-file
  needle passes for a prompt where only one surface carries the rule.
- Obligations of the form "MUST NOT define its own X" are asserted as
  ABSENCES, with the needle taken from the authority's own X.
- This tree is OMITTED from coverage (`[tool.coverage.run].omit` carries
  `tests/prompts/*`), so a locator helper does not owe 100% branch
  coverage. Give each helper a positive AND negative control test
  anyway — a locator that silently matches nothing certifies prose it
  never read.

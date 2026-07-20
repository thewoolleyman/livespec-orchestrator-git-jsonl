---
proposal: retire-autonomous-mode.md
decision: accept
revised_at: 2026-07-20T19:40:00Z
author_human: thewoolleyman <chad@thewoolleyweb.com>
author_llm: claude-opus-4-8
---

## Decision and Rationale

Retiring this plugin's ratified-but-unimplemented Full autonomous mode surface —
the dangerous, default-off `--autonomous` flag on the four heavyweight skills
under which an LLM stands in for the user at each per-item consent gate.

The decision rests on a distinction verified directly rather than inherited: this
plugin's "Full autonomous mode" and the one `livespec-orchestrator-beads-fabro`
retired at its v034 are DIFFERENT SURFACES SHARING A NAME. The sibling retired a
Dispatcher drain mode (`--mode autonomous`) and replaced it with six
`dispatcher.*` policy settings governing admission, post-merge acceptance,
review fix-caps, and a WIP ceiling inside a Fabro factory. This plugin ships no
dispatcher, no factory, no PR flow, no review gate, and no WIP limit — its eight
skills are `capture-impl-gaps`, `capture-spec-drift`, `capture-work-item`,
`detect-impl-gaps`, `implement`, `list-work-items`, `needs-attention`, `next`.
"Re-steering this spec to the v034 policy-settings model" would therefore have
been a CATEGORY ERROR: none of the six settings have referents here.

Retirement rather than preservation, because a ratified, unimplemented,
explicitly DANGEROUS feature reads as sanctioned design intent and invites a
future implementer to build the precise paradigm the family has just spent a
release retiring — an LLM resolving a human consent gate, which the sibling
dropped as the riskiest part of its own autonomous mode. Retirement costs no
migration: verified zero non-vendor `*.py` matches, zero skill-body matches, and
all three removed headings carried `"test": "TODO"` in the coverage map.

What transfers from v034 is its PRINCIPLE — granular, independently-defaulted,
per-item-overridable consent policy with a hard needs-human floor — NOT its six
settings. If autonomy is ever wanted here it should be designed fresh against
that principle and this plugin's actual consent gates.

THREE JUDGMENT CALLS, all resolved toward minimal removal with producers
verified first:

1. **`decided_by` — REMOVED.** Its enum is `human | autonomous`; with the
   autonomous run mode gone it can only ever hold `human`, becoming a constant
   that discriminates nothing. Verified zero producers and zero consumers for
   EITHER value across all non-vendor code and schema. Keeping a husk whose only
   discriminating value was deleted is worse than removing it.
2. **`auto_resolvable` — REMOVED, but its surrounding rules PRESERVED.** The
   hint is defined purely as "whether a full-autonomous run could progress the
   item without a human", so it is undefined once that run mode is gone, and it
   had zero producers/consumers. The genuinely valuable neighbours were kept and
   generalized: impl-specific extra fields remain permitted, the
   no-`additionalProperties`-discipline rule survives, and the ranking-purity
   rule now binds ANY such advisory field rather than only `auto_resolvable`.
3. **`Unresolvable decision` / `Escalation` — RE-ANCHORED, NOT deleted.**
   Escalating instead of guessing is a general safety principle, not an
   autonomous-mode artifact. Both terms were rewritten free of the autonomous
   framing, and the removed section's one non-autonomous-specific clause (never
   guess a decision classified unresolvable) was preserved as a new
   §"Forbidden patterns" bullet so the safety floor survives the section that
   happened to house it.

A fourth call arose during application: Scenario 5 sits mid-sequence, so its
removal would leave a permanent hole in a six-item list. Scenario 6 was
RENUMBERED to 5. The numbering is positional rather than an identity — the
sibling reused numbers 33–37 wholesale for entirely new scenarios at its own
v034 — and exactly three places referenced it, all amended here.

The mandatory drift sweep caught an edit the original map MISSED: removing
`decided_by` left the schema preamble asserting "twenty keys" over an
enumeration of nineteen, plus a dangling `decided_by` mention in the
optional-on-read list. Repaired as change L, count verified by enumeration
(14 + `rank` + 4 = 19). Recorded rather than quietly fixed, because it is the
argument for sweeping before declaring done.

Final sweep: `grep -rn "utonomous" SPECIFICATION/*.md` returns ZERO hits, as do
`decided_by`, `auto_resolvable`, and the stale `twenty`.

Three `## ` (H2) headings were removed and one renamed, so
`../tests/heading-coverage.json` is co-edited in this same change: 29 entries to
26, with the surviving scenario entry's heading renamed and its `test`/`reason`
preserved.

No work-item is owed. This proposal removes specification surface and creates no
implementation commitment; the ledger item that tracked BUILDING this feature
(`bd-gj-rb3`, "Implement full autonomous mode (consent-gate scope)") dies
as-written and is closed with this disposition recorded on it.

## Resulting Changes

- spec.md
- constraints.md
- contracts.md
- scenarios.md
- ../tests/heading-coverage.json

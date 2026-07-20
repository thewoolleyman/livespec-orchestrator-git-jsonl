---
topic: retire-autonomous-mode
author: claude-opus-4-8
created_at: 2026-07-20T19:20:00Z
---

## Proposal: Retire the ratified-but-unimplemented Full autonomous mode surface

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/constraints.md
- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md
- ../tests/heading-coverage.json

### Summary

Retire this plugin's **Full autonomous mode** surface — the dangerous,
default-off `--autonomous` flag on the four heavyweight skills, under which an
LLM stands in for the user at each per-item consent gate. It is ratified across
four spec files and implemented NOWHERE, so retirement costs no migration.

Three `## ` (H2) headings are removed (`spec.md` §"Autonomous mode",
`constraints.md` §"Autonomous mode constraints", `scenarios.md` §"Scenario 5 —
Full autonomous fix cycle"), so `tests/heading-coverage.json` is co-edited in
this same change.

The **`Unresolvable decision`** and **`Escalation`** concepts are RE-ANCHORED,
not deleted: escalating instead of guessing is a general safety principle, not
an autonomous-mode artifact.

### Motivation

**This is NOT a translation of the sibling's v034 retirement, and attempting one
would be a category error.** That distinction is the whole basis of this
proposal, and it was verified directly rather than assumed.

`livespec-orchestrator-beads-fabro` retired a **Dispatcher drain mode**
(`--mode autonomous`) and replaced it with six `dispatcher.*` policy settings
governing admission, post-merge acceptance, review fix-caps, and a WIP ceiling
inside a Fabro factory.

**This plugin's Full autonomous mode is a different surface that merely shares
the name**: a `--autonomous` flag on four HEAVYWEIGHT SKILLS where an LLM
substitutes for the user at per-item CONSENT GATES (which detected gap-ids to
file; which drift findings to hand off; a freeform title/description/type; the
work-item selection plus closure narration).

This plugin ships **no dispatcher, no factory, no PR flow, no review gate, and
no WIP limit**. Its eight skills are `capture-impl-gaps`, `capture-spec-drift`,
`capture-work-item`, `detect-impl-gaps`, `implement`, `list-work-items`,
`needs-attention`, and `next`. There is therefore nothing for
`auto_approve_ready`, `merge_on_review_cap`, `acceptance_mode`,
`review_fix_cap`, `acceptance_rework_cap`, or `wip_cap` to attach to. Adopting
those settings here would import vocabulary with no referents.

**Why retire rather than keep it ratified-but-unimplemented.** A ratified,
unimplemented, explicitly DANGEROUS feature is a standing liability: it reads as
sanctioned design intent and invites a future implementer to build precisely the
paradigm the family has just spent a release retiring. The specific clause at
issue — an LLM resolving a human consent gate — is exactly what the sibling
dropped as the RISKIEST part of its own autonomous mode.

**What transfers from v034 is its PRINCIPLE, not its settings**: granular,
independently-defaulted, per-item-overridable consent policy with a hard
needs-human floor. If autonomy is ever wanted in this plugin, it should be
designed fresh against that principle and against this plugin's actual consent
gates — not inherited from a spec written for a factory this plugin does not
have.

**Evidence of non-implementation** (verified at `origin/master`): zero
non-vendor `*.py` matches for `autonomous`; zero matches in any skill body; and
all three of the removed headings carry `"test": "TODO"` in
`tests/heading-coverage.json`, two with the reason "real test id populated when
the behavior's acceptance test lands" — an acceptance test that can never land
for behavior that was never built.

### Proposed Changes

All target text below is quoted verbatim from the live `SPECIFICATION/` files at
`origin/master` (`b9081aa`).

**A. Remove the `Autonomous mode` terminology entry and RE-ANCHOR the two
concepts that outlive it — `SPECIFICATION/spec.md` §"Terminology".** REPLACE
this verbatim block:

> **Autonomous mode** — An opt-in, dangerous, default-off run mode in which
> an LLM stands in for the user at each per-item consent gate this plugin
> owns and auto-supplies closure narration, instead of prompting the user
> per item. Contrast the default **interactive** mode. Defined in
> §"Autonomous mode".
>
> **Unresolvable decision** — A decision the autonomous engine cannot make
> with sufficient confidence, or that requires information the plugin cannot
> obtain. It is the residual class that autonomous mode still surfaces to a
> human rather than guessing.
>
> **Escalation** — Surfacing an unresolvable decision to the human instead
> of resolving it. Under autonomous mode, escalation replaces a guess.

WITH:

> **Unresolvable decision** — A decision this plugin cannot make with
> sufficient confidence, or that requires information it cannot obtain. It is
> the residual class that MUST be surfaced to a human rather than guessed.
>
> **Escalation** — Surfacing an unresolvable decision to the human instead
> of resolving it. Escalation always replaces a guess.

**B. Remove the `Autonomous mode` section entirely — `SPECIFICATION/spec.md`.**
DELETE the whole `## Autonomous mode` H2 section, from the heading through the
paragraph ending "not here.", i.e. this verbatim span:

> ## Autonomous mode
>
> The plugin MUST support two run modes for its human-decision surface:
>
> - **Interactive** (the default) — every per-item consent gate this plugin
>   owns is presented to the user, per item, exactly as today.
> - **Full autonomous mode** — an opt-in, **dangerous**, **default-off** mode
>   in which an LLM stands in for the user at each of those consent gates and
>   auto-supplies closure narration. It MUST be labelled "dangerous / use
>   with caution" wherever it is offered, and MUST be an explicit
>   per-invocation opt-in (never a default, never inferred).
>
> The human-decision surface this plugin actually owns is the per-item
> consent gates of its four heavyweight skills (`capture-impl-gaps`,
> `capture-spec-drift`, `capture-work-item`, `implement`); autonomous mode's
> reach is exactly those gates plus the closure `reason` / `resolution`
> narration. The wire form is in `contracts.md` §"Heavyweight authored
> skills (4)"; its safety rules are in `constraints.md` §"Autonomous mode
> constraints".
>
> Full autonomous mode MUST still **escalate** any **unresolvable decision**
> to a human rather than guess. It MUST NOT cross into the
> admission/acceptance orchestration this plugin does not run: the `manual`
> admission valve and the `ai-then-human` acceptance valve are owned by the
> orchestrator Dispatcher (the sibling `livespec-orchestrator-beads-fabro`,
> and upstream `livespec`), whose autonomous resolution is specified there,
> not here.

The surviving escalation duty is carried by the re-anchored terminology in
change A and by the constraint added in change D.

**C. Remove the `Autonomous mode constraints` section —
`SPECIFICATION/constraints.md`.** DELETE the whole `## Autonomous mode
constraints` H2 section, this verbatim span:

> ## Autonomous mode constraints
>
> - Autonomous mode MUST default off. It MUST be an explicit per-invocation
>   opt-in (the `--autonomous` flag on a heavyweight skill); its absence MUST
>   mean interactive, per-item-consent behavior.
> - Enabling autonomous mode MUST require an explicit dangerous-mode
>   acknowledgement; it MUST NOT be inferred from context and MUST NOT
>   persist across invocations.
> - Every autonomously-resolved decision MUST be recorded in the append-only
>   JSONL via `decided_by: autonomous` (`contracts.md` §"Work-items JSONL
>   record schema"); it MUST NOT be recorded in any sidecar (reinforcing
>   §"Forbidden patterns" — "No off-substrate persistence").
> - The engine MUST NOT auto-resolve a decision it classifies as
>   unresolvable; it MUST block and surface such a decision to a human
>   (mirroring Scenario 3's "no silent skips").

**D. Preserve the escalation floor as a general constraint —
`SPECIFICATION/constraints.md` §"Forbidden patterns".** The final bullet of
change C is the only clause in the removed section that is NOT
autonomous-specific: a decision classified unresolvable must never be guessed.
ADD this bullet to the END of the existing `## Forbidden patterns` section:

> - No guessing an unresolvable decision. Where this plugin cannot decide with
>   sufficient confidence, or lacks information it cannot obtain, it MUST NOT
>   substitute a guess — it MUST block and surface the decision to a human
>   (mirroring Scenario 3's "no silent skips").

**E. Drop the retired-flag carve-out from the query-only rule —
`SPECIFICATION/constraints.md` §"Forbidden patterns".** REPLACE this verbatim
bullet:

> - No mutating CLI flags on `list-*` or `next` skills. These are
>   query-only by contract; adding `--update` / `--write` / similar
>   flags is a contract violation. The dangerous `--autonomous` flag
>   (`spec.md` §"Autonomous mode") MUST NOT be added to the thin-transport
>   skills (`list-work-items`, `next`, `detect-impl-gaps`) either — it is
>   confined to the four heavyweight skills that own consent gates.

WITH:

> - No mutating CLI flags on `list-*` or `next` skills. These are
>   query-only by contract; adding `--update` / `--write` / similar
>   flags is a contract violation.

**F. Remove the `--autonomous` contract paragraph —
`SPECIFICATION/contracts.md` §"Heavyweight authored skills (4)".** DELETE this
verbatim span:

> **Full autonomous mode (`--autonomous`).** Each of the four heavyweight
> skills below MUST accept a dangerous, default-off `--autonomous` opt-in
> flag (per `spec.md` §"Autonomous mode"). When set, the skill MUST resolve
> its per-item consent gate(s) with an LLM decision instead of prompting the
> user, MUST record every autonomously-resolved decision on the append-only
> JSONL via the `decided_by: autonomous` field (§"Work-items JSONL record
> schema"), and MUST NOT guess an unresolvable decision — it MUST escalate
> such a decision to the user, and when no user is present to resolve it,
> MUST block and surface it. What each skill auto-resolves:
>
> - `capture-impl-gaps` — which detected gap-ids to file.
> - `capture-spec-drift` — which drift findings to hand off to
>   `/livespec:propose-change`.
> - `capture-work-item` — the freeform title, description, and type.
> - `implement` — the work-item selection and the closure `--reason` and
>   `resolution`.
>
> The three thin-transport skills (`list-work-items`, `next`,
> `detect-impl-gaps`) MUST NOT accept `--autonomous`; they are query-only
> (per `constraints.md` §"Forbidden patterns").

**G. Generalize the advisory-field rule off the retired example —
`SPECIFICATION/contracts.md` §"`next`".** The `auto_resolvable` hint is defined
purely in terms of "a full-autonomous run" and has no meaning once that run mode
is retired; it has zero producers and zero consumers. The surrounding rules —
that impl-specific extra fields are permitted, that no
`additionalProperties` discipline is prescribed, and that no such field may
perturb ranking — are independently valuable and MUST survive. REPLACE this
verbatim span:

> Each candidate
>   MAY include additional impl-git-jsonl-specific fields the
>   wrapper emits (e.g., `rank`, `origin`, or an advisory
>   `auto_resolvable` boolean hinting whether a full-autonomous run
>   could progress the item without a human); the cross-plugin
>   contract MUST NOT prescribe `additionalProperties` discipline
>   per upstream. Any such `auto_resolvable` hint MUST remain
>   advisory and MUST NOT change the ranking (a pure function of
>   `rank`).

WITH:

> Each candidate
>   MAY include additional impl-git-jsonl-specific fields the
>   wrapper emits (e.g., `rank` or `origin`); the cross-plugin
>   contract MUST NOT prescribe `additionalProperties` discipline
>   per upstream. Any such additional field MUST remain
>   advisory and MUST NOT change the ranking (a pure function of
>   `rank`).

**H. Remove the `decided_by` record field — `SPECIFICATION/contracts.md`
§"Work-items JSONL record schema".** The field's enum is `human | autonomous`;
with the autonomous run mode retired it can only ever hold `human`, so it
becomes a constant that discriminates nothing. It has zero producers and zero
consumers (verified: no non-vendor `*.py` or schema match anywhere in this
repo, for EITHER value). DELETE this verbatim bullet:

> - `decided_by` — string, one of `human` | `autonomous`. OPTIONAL on the
>   read path (records authored before this field's introduction read back
>   as `null`); always written explicitly on append. Records whether the
>   record's decision was made by a human (the default, interactive mode) or
>   by the autonomous engine (`spec.md` §"Autonomous mode"). A record
>   appended by a skill run under `--autonomous` MUST carry
>   `decided_by: autonomous`; every autonomously-resolved decision is thus
>   attributable on the append-only JSONL itself.

**I. Remove Scenario 5 and renumber Scenario 6 —
`SPECIFICATION/scenarios.md`.** DELETE the entire `## Scenario 5 — Full
autonomous fix cycle` H2 section (from its heading through the paragraph ending
"...orchestration this plugin does not run."), then RENAME the following
heading:

> ## Scenario 6 — Ledger-intent drift surfaces missing spec behavior

TO:

> ## Scenario 5 — Ledger-intent drift surfaces missing spec behavior

Renumbering rather than leaving a gap is deliberate: this file carries only six
scenarios, the numbering is positional rather than an identity (the sibling
`livespec-orchestrator-beads-fabro` reused numbers 33–37 wholesale for entirely
new scenarios at its own v034 retirement), and a permanent hole at 5 in a
six-item list invites a future reader to ask what was lost. Exactly three places
reference the number, all amended by this proposal: the heading itself, its
`tests/heading-coverage.json` entry, and one cross-reference (change J).

**J. Repoint the Scenario-6 cross-reference — `SPECIFICATION/contracts.md`.**
REPLACE this verbatim fragment:

> per `scenarios.md` Scenario 6's empty-queue handoff

WITH:

> per `scenarios.md` Scenario 5's empty-queue handoff

**K. Co-edit the heading-coverage map — `../tests/heading-coverage.json`.**
REMOVE the two entries whose headings are deleted outright:

- `{"heading": "## Autonomous mode", "spec_file": "spec.md", ...}`
- `{"heading": "## Autonomous mode constraints", "spec_file": "constraints.md", ...}`

REMOVE the entry for the deleted scenario:

- `{"heading": "## Scenario 5 — Full autonomous fix cycle", "spec_file": "scenarios.md", ...}`

And RENAME the surviving scenario entry's `heading` field from
`"## Scenario 6 — Ledger-intent drift surfaces missing spec behavior"` to
`"## Scenario 5 — Ledger-intent drift surfaces missing spec behavior"`,
preserving its existing `test` and `reason` values unchanged.

Net effect: 29 entries become 26.

**L. Repair the schema preamble that change H invalidates —
`SPECIFICATION/contracts.md` §"Work-items JSONL record schema".** Removing
`decided_by` leaves the section's own prose describing a schema that no longer
exists. **This change was NOT in the original edit map; the mandatory drift
sweep caught it**, which is the argument for running that sweep before
declaring the work done rather than after.

Three repairs, all in the schema preamble:

REPLACE `twenty keys enumerated below are the canonical schema. Fourteen`
WITH `nineteen keys enumerated below are the canonical schema. Fourteen`.

REPLACE this verbatim fragment:

> `spec_commitment_hint`, `supersedes`, `acceptance_criteria`,
> `notes`, and `decided_by` are required-on-write but optional-on-read

WITH:

> `spec_commitment_hint`, `supersedes`, `acceptance_criteria`, and
> `notes` are required-on-write but optional-on-read

REPLACE `Additional keys beyond this twenty are forbidden`
WITH `Additional keys beyond this nineteen are forbidden`.

The new count is verified by enumeration, not assumed: 14 required-on-write-AND-
read + `rank` + 4 required-on-write-but-optional-on-read (`spec_commitment_hint`,
`supersedes`, `acceptance_criteria`, `notes`) = **19**. Before this proposal the
same arithmetic gave 20, `decided_by` being the fifth optional-on-read key.

Leaving this unrepaired would have shipped a section whose stated key count
contradicted its own enumeration — precisely the "a list titled N must contain
N" defect this fleet's authoring conventions forbid, and precisely the class of
stale artifact this whole programme has been retiring.

### Drift sweep

After applying, `grep -rn "utonomous" SPECIFICATION/*.md` MUST return only
intentional survivors. The expected survivor set is EMPTY: every live
occurrence enumerated at `origin/master` is addressed by changes A–J. Any
residual hit is a defect in this proposal, not an acceptable remainder.

`SPECIFICATION/history/` is excluded from the sweep by design — prior revisions
are immutable and correctly retain the retired text.

# scenarios.md — livespec-orchestrator-git-jsonl

End-to-end behavioral narratives illustrating the plugin's
intended use across the workflow loops defined in
`livespec/SPECIFICATION/`. These are not test cases (those
live under `tests/`); they are reader-facing journeys an agent
or contributor follows.

## Scenario 1 — Gap-tied fix cycle

A consumer project has a fresh `livespec` revision (vNNN+1)
that introduced a new MUST clause not yet honored in the impl.

1. The user invokes
   `/livespec-orchestrator-git-jsonl:capture-impl-gaps`. The skill loads
   the rule set via the Spec Reader, walks each rule against the
   impl, and surfaces uncaptured gaps one at a time.
2. For each gap the user consents to file, the skill appends a
   work-item JSONL record with `origin: gap-tied`,
   `gap_id: <stable-id>`, `status: open`, and the user-confirmed
   title / description.
3. The user invokes `/livespec-orchestrator-git-jsonl:next`. The ranker
   surfaces the newly-filed gap-tied item as the recommendation
   (gap-tied beats freeform at equal priority).
4. The user invokes `/livespec-orchestrator-git-jsonl:implement` for that
   work-item. The skill walks Red → Green → closure.
5. At closure, the skill re-runs `capture-impl-gaps` in dry-run
   mode and confirms the `gap_id` is no longer detected. On
   success, it appends a closing record with `status: closed`,
   `resolution: completed`, and the audit object
   (`verification_timestamp`, `commits`, `files_changed`,
   `merge_sha`, optional `pr_number`).

## Scenario 2 — Freeform bug fix

The user spots a bug unrelated to any open gap.

1. The user invokes
   `/livespec-orchestrator-git-jsonl:capture-work-item` and supplies title,
   description, `type: bug`, `priority: 2`. The skill appends a
   work-item record with `origin: freeform`, `gap_id: null`.
2. The user invokes `/livespec-orchestrator-git-jsonl:implement` for that
   item. Red → Green proceeds normally.
3. At closure, the skill takes the freeform path: append a closing
   record with `status: closed`, `resolution: completed`, and the
   user-supplied `--reason`. No `gap_id` re-detection runs.

## Scenario 3 — Doctor cross-boundary read

The user invokes `/livespec:doctor` in a consumer project.

1. Doctor's static phase reads `<spec-root>/` directly.
2. Doctor's cross-boundary phase invokes the active impl-plugin's
   thin-transport query skills:
   - `/livespec-orchestrator-git-jsonl:list-work-items --json` for the
     work-item structural invariants.
3. Each invocation MUST complete deterministically with the
   contract-mandated JSON schema. A missing or malformed plugin
   surface fires a `fail` finding (no silent skips).

## Scenario 4 — Cross-repo Layer 3 loop driver (livespec-resident)

Cross-reference: cross-side composition of impl-side `next` with
spec-side `/livespec:next` is a Layer 3 (project-local
orchestration) concern per `livespec/SPECIFICATION/spec.md`. This
scenario describes the
Layer 3 driver's behavior; this plugin's `next` skill itself
ranks impl-side state only and MUST NOT bake a cross-side
weighting in.

livespec's `.claude/skills/loop/SKILL.md` is the
livespec-resident cross-repo orchestration driver. At the top of each iteration:

1. The driver invokes `/livespec:next --json` to get a
   spec-side recommendation.
2. The driver invokes `/livespec-orchestrator-git-jsonl:next --json` to
   get an impl-side recommendation.
3. The driver composes the two outputs into a per-iteration
   action plan per the orchestration-layer rules defined in
   `livespec/SPECIFICATION/`.
4. **Empty-queue handoff.** When both `/livespec:next` and
   `/livespec-orchestrator-git-jsonl:next` emit empty `candidates: []`
   arrays (the no-work signal on both sides), the Layer 3
   driver SHOULD offer the user a hygiene fallback — at
   minimum, a `/livespec:doctor` pass and a
   `/livespec:critique` pass — and MAY also offer
   `/livespec:prune-history` if `next.prune_history_threshold`
   would otherwise have suppressed it. The hygiene fallback
   is a Layer 3 productivity heuristic per the upstream
   `Durable-pending` doctrine; it is NEVER baked into the
   Layer 2 `next` emission itself.

Gap-detection and drift-detection invocations
(`/livespec-orchestrator-git-jsonl:capture-impl-gaps`,
`/livespec-orchestrator-git-jsonl:capture-spec-drift`) are likewise
Layer 3 driver-side concerns that the driver invokes outside
of `next`'s ranking — `next` ranks work-items JSONL state
only.

This plugin is responsible only for step 2's output schema and
behavior; the composition rules and empty-queue handoff policy
are entirely in scope for `livespec` and the project-local
driver, not for this spec.

## Scenario 5 — Ledger-intent drift surfaces missing spec behavior

A maintainer runs `/livespec-orchestrator-git-jsonl:capture-spec-drift`
to reconcile the spec against the work-items store, optionally scoping
the ledger scan with `--since-version <vN>`.

1. Alongside its impl → spec heuristic, the skill runs a **read-only
   ledger-intent scan** over recent work-items, reading the store through
   the append-only materialized-view reduction.
2. It finds a recent work-item whose `description` encodes a behavior
   that the shared spec-stated judgement reports `partial` or `unstated`, and surfaces it as a ledger-intent
   drift finding with a recommended action.
3. On the maintainer's consent, the skill hands the finding off to
   `/livespec:propose-change`; it never mutates the work-item and never
   writes spec-side state directly.
4. Intent the judgement reports `stated` produces no finding, so the scan
   raises no spurious propose-changes.

## Scenario 6 — A feature the spec does not state is filed at spec-change tier

The user files a feature whose asked-for behaviour no ratified clause
states.

1. The user invokes
   `/livespec-orchestrator-git-jsonl:capture-work-item` with title,
   description and `type: feature`.
2. The skill classifies the item through
   `livespec_runtime.spec_stated.classify` as `feature`, then judges
   its asked-for behaviour through `judge`; the verdict is `unstated`
   and names an existing heading as its `generalization_target`.
3. The skill offers the linked proposed change; on consent it hands
   off to `/livespec:propose-change`, naming that heading as the one
   to amend.
4. The appended record carries `spec_change_tier` with `tier:
   spec-change`, the proposal's canonical topic as
   `linked_proposal_topic`, the verdict, and `judged_at`.
5. Had the user declined the linked proposal, the record would
   still carry `tier: spec-change` and the verdict, with
   `linked_proposal_topic: null`.
6. Filing an item the judgement classifies `bug` instead yields a
   record whose `spec_change_tier.tier` is `none` and whose
   `linked_proposal_topic` and `verdict` are `null`; no proposal is
   offered.

## Scenario: a delegating host's push gates on the remote executor and refuses on no verdict

Given this repository's version-controlled configuration opts it in to delegating its pre-push gate

And the pushing host holds the credential to submit to the remote executor

When a git push of a new tree runs the pre-push gate

Then the pre-push path MUST run the delegation client instead of running `just check` on the pushing host

And the push MUST complete only on a passing verdict from the executor

And the push MUST be refused when the executor returns no verdict

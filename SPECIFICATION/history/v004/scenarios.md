# scenarios.md — livespec-impl-plaintext

End-to-end behavioral narratives illustrating the plugin's
intended use across the workflow loops defined in
`livespec/SPECIFICATION/`. These are not test cases (those
live under `tests/`); they are reader-facing journeys an agent
or contributor follows.

## Scenario 1 — Gap-tied fix cycle

A consumer project has a fresh `livespec` revision (vNNN+1)
that introduced a new MUST clause not yet honored in the impl.

1. The user invokes
   `/livespec-impl-plaintext:capture-impl-gaps`. The skill loads
   the rule set via the Spec Reader, walks each rule against the
   impl, and surfaces uncaptured gaps one at a time.
2. For each gap the user consents to file, the skill appends a
   work-item JSONL record with `origin: gap-tied`,
   `gap_id: <stable-id>`, `status: open`, and the user-confirmed
   title / description.
3. The user invokes `/livespec-impl-plaintext:next`. The ranker
   surfaces the newly-filed gap-tied item as the recommendation
   (gap-tied beats freeform at equal priority).
4. The user invokes `/livespec-impl-plaintext:implement` for that
   work-item. The skill walks Red → Green → closure.
5. At closure, the skill re-runs `capture-impl-gaps` in dry-run
   mode and confirms the `gap_id` is no longer detected. On
   success, it appends a closing record with `status: closed`,
   `resolution: fix`, and the audit object
   (`verification_timestamp`, `commits`, `files_changed`).

## Scenario 2 — Memo → spec-bound disposition

The user notices something during impl work that doesn't fit the
current work-item but is intent-bearing.

1. The user invokes
   `/livespec-impl-plaintext:capture-memo` and types a one-paragraph
   observation. The skill appends a memo record with
   `state: untriaged` and a fresh `id`.
2. Later, the user invokes
   `/livespec-impl-plaintext:process-memos`. The skill iterates over
   untriaged memos and asks for a disposition per memo.
3. For this memo, the user picks `spec-bound`. The skill hands
   off to `/livespec:propose-change` with the memo content
   as the proposed-change source; a new file lands under the
   consumer's `<spec-root>/proposed_changes/`.
4. The skill appends a closing memo record with
   `state: dispositioned`, `disposition: spec-bound`, and the
   resulting proposed-change topic for cross-reference.
5. The next `/livespec:doctor` pass sees one fewer untriaged
   memo; if memo backlog was driving a memo-hygiene `warn`, the
   warning clears.

## Scenario 3 — Memo → persistent-knowledge graduation

The user has been re-discovering the same workflow gotcha across
sessions. A memo describing the gotcha exists.

1. The user invokes `/livespec-impl-plaintext:process-memos`.
2. For this memo, the user picks `persistent-knowledge`. The skill
   asks for a topic name (e.g., `mise-exec-for-git-hooks`).
3. The skill writes the memo content to
   `.ai/mise-exec-for-git-hooks.md` (creating the file if absent).
4. The skill verifies `CLAUDE.md` (and/or `AGENTS.md`) references
   that file via a bullet; if not, it adds the reference.
5. The skill appends a closing memo record with
   `state: dispositioned`, `disposition: persistent-knowledge`,
   and `knowledge_file: ".ai/mise-exec-for-git-hooks.md"`.
6. Future sessions load that knowledge file on demand via the
   harness's `CLAUDE.md` / `AGENTS.md` reference traversal.

## Scenario 4 — Freeform bug fix

The user spots a bug unrelated to any open gap.

1. The user invokes
   `/livespec-impl-plaintext:capture-work-item` and supplies title,
   description, `type: bug`, `priority: 2`. The skill appends a
   work-item record with `origin: freeform`, `gap_id: null`.
2. The user invokes `/livespec-impl-plaintext:implement` for that
   item. Red → Green proceeds normally.
3. At closure, the skill takes the freeform path: append a closing
   record with `status: closed`, `resolution: fix`, and the
   user-supplied `--reason`. No `gap_id` re-detection runs.

## Scenario 5 — Doctor cross-boundary read

The user invokes `/livespec:doctor` in a consumer project.

1. Doctor's static phase reads `<spec-root>/` directly.
2. Doctor's cross-boundary phase invokes the active impl-plugin's
   thin-transport query skills:
   - `/livespec-impl-plaintext:list-memos --filter=untriaged
     --json` for the memo-hygiene invariant.
   - `/livespec-impl-plaintext:list-work-items --json` for the
     four work-item structural invariants.
3. Each invocation MUST complete deterministically with the
   contract-mandated JSON schema. A missing or malformed plugin
   surface fires a `fail` finding (no silent skips).

## Scenario 6 — Project-local Layer 3 loop driver

The consumer project's `.claude/skills/loop/SKILL.md` is the
hand-tuned orchestration driver. At the top of each iteration:

1. The driver invokes `/livespec:next --json` to get a
   spec-side recommendation.
2. The driver invokes `/livespec-impl-plaintext:next --json` to
   get an impl-side recommendation.
3. The driver composes the two outputs into a per-iteration
   action plan per the orchestration-layer rules defined in
   `livespec/SPECIFICATION/`.

This plugin is responsible only for step 2's output schema and
behavior; the composition rules are entirely in scope for
`livespec` and the project-local driver, not for this spec.

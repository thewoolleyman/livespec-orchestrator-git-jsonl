---
proposal: default-factory-petri.md
decision: accept
revised_at: 2026-10-22T22:28:53Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: claude-opus-5-5
---

## Decision and Rationale

Accepted per maintainer direction relayed by coordinator session gitops-fleet-capacity-monitoring: ruling R668 moves this repository's dispatch default from the `legacy` Fabro factory to `petri` (the current Fabro server), and ruling R672 approves this spec revise as a delegated decision (work-item bd-ib-iud52v). Only the default-factory sentence of `## Factory routing` changes; the registry-backed and no-machine requirements are unchanged, `legacy` stays a declared registry-backed entry, and no heading is added, renamed or removed. The committed `.livespec.jsonc` in the same change declares a registry-backed `petri` entry (no server, no docker_host) and sets `dispatcher.default_factory` to `petri`; the dispatching host's rendered registry `/etc/livespec/fabro-factories.json` resolves `petri` to the current Fabro server, environment livespec-ci. Independent read-only ratification reviews of the exact resulting bytes: the configured designated reviewer fable (auto-spawn), round 1, NO BLOCKERS (recorded below); and, at the coordinator's request, Codex gpt-6-astra (read-only), round 1, NO BLOCKERS (2026-10-22T22:22:08Z).

## Resulting Changes

- constraints.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: fable
reviewer_identity: fable
separate_reviewer: True
read_only: True
reviewed_at: 2026-10-22T22:28:00Z
verdict: NO BLOCKERS
proposal_stem: default-factory-petri
content_digest: cfe03baaafb5f784c386248770a702c4249c830351a04a9bbd22c6eef5145ae1

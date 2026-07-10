# Changelog

## [0.5.3](https://github.com/thewoolleyman/livespec-orchestrator-git-jsonl/compare/v0.5.2...v0.5.3) (2026-07-10)


### Bug Fixes

* restore honest writes; stop no_write_direct .buffer.write dodge ([5e44bf1](https://github.com/thewoolleyman/livespec-orchestrator-git-jsonl/commit/5e44bf18dba60a45982f6da344ebeecda70cfb6b))

## [0.5.2](https://github.com/thewoolleyman/livespec-orchestrator-git-jsonl/compare/v0.5.1...v0.5.2) (2026-07-10)


### Bug Fixes

* add migration entry wrappers ([e09232f](https://github.com/thewoolleyman/livespec-orchestrator-git-jsonl/commit/e09232f8488576cc641d1e7734693bb534a55e27))

## [0.5.1](https://github.com/thewoolleyman/livespec-orchestrator-git-jsonl/compare/v0.5.0...v0.5.1) (2026-07-08)


### Bug Fixes

* **needs-attention:** inline spec-next candidates ([d25e525](https://github.com/thewoolleyman/livespec-orchestrator-git-jsonl/commit/d25e525d03d187e74219c539b38d25de1c787575))

## [0.5.0](https://github.com/thewoolleyman/livespec-orchestrator-git-jsonl/compare/v0.4.0...v0.5.0) (2026-07-07)


### Features

* add needs-attention binding coverage ([58fb942](https://github.com/thewoolleyman/livespec-orchestrator-git-jsonl/commit/58fb942f1a867aa56211195b15755989b2090762))

## [0.4.0](https://github.com/thewoolleyman/livespec-orchestrator-git-jsonl/compare/v0.3.0...v0.4.0) (2026-07-03)


### Features

* self-heal credentials at the bin bootstrap chokepoint ([2044c3b](https://github.com/thewoolleyman/livespec-orchestrator-git-jsonl/commit/2044c3bb3d526968139edd03a58e422c443e4926))


### Bug Fixes

* carry acceptance_criteria + notes in the git-jsonl work-item schema ([9d50738](https://github.com/thewoolleyman/livespec-orchestrator-git-jsonl/commit/9d50738df9375e45e8202440de27158d8634be8c))
* remove BEADS_DOLT_PASSWORD self-heal from git-jsonl bin bootstrap ([5f9c255](https://github.com/thewoolleyman/livespec-orchestrator-git-jsonl/commit/5f9c255ae97562c25e864700c4fb99eaca3ca3bb))

## [0.3.0](https://github.com/thewoolleyman/livespec-orchestrator-git-jsonl/compare/v0.2.0...v0.3.0) (2026-06-29)


### Features

* migrate JSONL realization to the v013 lifecycle schema ([4f911c5](https://github.com/thewoolleyman/livespec-orchestrator-git-jsonl/commit/4f911c58625f42def1ca7a466eeee1a1ffda1283))

## [0.2.0](https://github.com/thewoolleyman/livespec-orchestrator-git-jsonl/compare/v0.1.0...v0.2.0) (2026-06-24)


### Features

* add git-jsonl acceptance harness ([19c9c09](https://github.com/thewoolleyman/livespec-orchestrator-git-jsonl/commit/19c9c09142480f657b633e637b0ebcfedd1a57d5))
* **checks:** no-divergent-heads store-integrity check via the canonical reducer ([aa81219](https://github.com/thewoolleyman/livespec-orchestrator-git-jsonl/commit/aa81219220b035fa4a4b2dc900c07089abad5843))
* **checks:** no-raw-store-read store-integrity check (read path only via the query surface) ([3938c56](https://github.com/thewoolleyman/livespec-orchestrator-git-jsonl/commit/3938c566b8ab10c2e0d1630b5c0494a7f79c5fba))
* **checks:** work_item_merge_evidence static check (li-tenpup) ([c26bff9](https://github.com/thewoolleyman/livespec-orchestrator-git-jsonl/commit/c26bff923a1b7a7b25aa7ff2558c8148b6114fb0))
* consume livespec-dev-tooling@v0.1.0; fix bootstrap bug ([e46f11f](https://github.com/thewoolleyman/livespec-orchestrator-git-jsonl/commit/e46f11fd83000bedaf67e2d044f4fa910f3b6323))
* **io:** introduce io/ boundary layer for file I/O and expected-error handling ([90e1ef5](https://github.com/thewoolleyman/livespec-orchestrator-git-jsonl/commit/90e1ef596c389085eb0bef51764ec488c9087446))
* **migration:** beads → JSONL migration utility (D.9) ([#8](https://github.com/thewoolleyman/livespec-orchestrator-git-jsonl/issues/8)) ([b5d9776](https://github.com/thewoolleyman/livespec-orchestrator-git-jsonl/commit/b5d9776b0fb27d8b12e0841c06e2eac694e124b6))
* **migration:** merge-evidence backfill with --grandfather fallback (li-tenpup) ([8bd7dff](https://github.com/thewoolleyman/livespec-orchestrator-git-jsonl/commit/8bd7dffe70fb5b3ece55abca0657db7b7dd88df3))
* **next:** emit {candidates[], pagination} envelope (li-qz3hn4) ([083182b](https://github.com/thewoolleyman/livespec-orchestrator-git-jsonl/commit/083182b2329135e8396ac5e82ff683da41ea0182))
* **store:** record merge-evidence (merge_sha + pr_number) in audit schema (li-tenpup) ([b745741](https://github.com/thewoolleyman/livespec-orchestrator-git-jsonl/commit/b7457415f59926b3a3bc331ff66b125aad8b52d0))
* **store:** supersedes field + order-independent supersession reduction (livespec-impl-plaintext-lhq) ([10ef3e7](https://github.com/thewoolleyman/livespec-orchestrator-git-jsonl/commit/10ef3e782703e043bab41e3f17123f46f7895973))


### Bug Fixes

* **migration:** merge_evidence_backfill is invocable as a script (li-tenpup) ([aaa7212](https://github.com/thewoolleyman/livespec-orchestrator-git-jsonl/commit/aaa7212cfd86da3043f113378eacdb53f3f5effc))


### Refactoring

* consume shared livespec_runtime.work_items surface (livespec-5g4i) ([f19d932](https://github.com/thewoolleyman/livespec-orchestrator-git-jsonl/commit/f19d9324a32b526804df058154fb908235a4cb57))
* flip git-jsonl _PLUGIN_BLOCK config key to livespec-orchestrator-git-jsonl ([786e204](https://github.com/thewoolleyman/livespec-orchestrator-git-jsonl/commit/786e2047f07b46f17f9a94fd913fac586db2b94b))
* rename git-jsonl plugin/repo name + skill namespace to livespec-orchestrator-git-jsonl ([90e028b](https://github.com/thewoolleyman/livespec-orchestrator-git-jsonl/commit/90e028b7cab4b00dad2a394e06b982483cafd9a9))
* rename livespec-impl-plaintext to livespec-impl-git-jsonl ([3c16d6f](https://github.com/thewoolleyman/livespec-orchestrator-git-jsonl/commit/3c16d6f494410d40d3c9cd315fa8c2ba5d72fbf3))
* rename Python package livespec_impl_git_jsonl -&gt; livespec_orchestrator_git_jsonl ([3793d1e](https://github.com/thewoolleyman/livespec-orchestrator-git-jsonl/commit/3793d1eed82238d596dd4c8196e46e99d033ddf6))

## Changelog

All notable changes to this plugin are recorded here. This file is
auto-maintained by release-please; do not edit it by hand.

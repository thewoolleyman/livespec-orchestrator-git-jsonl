# justfile — livespec-orchestrator-git-jsonl dev-tooling task runner.
#
# Generated from livespec/templates/impl-plugin/justfile.jinja at
# copier-copy time; re-sync via `copier update --vcs-ref=master` when livespec
# publishes a new release.
#
# Authority: livespec/SPECIFICATION/non-functional-requirements.md
#   §"Enforcement-suite invocation" — `just` is the canonical entry
#   point for every dev-tooling invocation. Lefthook and CI MUST
#   delegate to `just <target>`; direct tool invocations are banned
#   (enforced by livespec_dev_tooling.checks.no_direct_tool_invocation).
#
# Authority: livespec/SPECIFICATION/contracts.md
#   §"Pre-commit step ordering" — the gates wired here mirror the
#   spec-required ordering: 00-lint-autofix-staged, 01-commit-pairs-
#   source-and-test, 02-check-pre-commit at pre-commit;
#   no-commit-on-master + red-green-replay at commit-msg; full
#   aggregate (with zero-py subsetting) at pre-push.
#
# Authority: livespec/SPECIFICATION/contracts.md
#   §"Shared code sync — livespec-dev-tooling" (v094 wiring-
#   completeness invariant) — every canonical slug emitted by
#   `livespec_dev_tooling.canonical_checks` MUST be wired in this
#   `check:` aggregate in alphabetical order; livespec-orchestrator-git-jsonl-
#   private extras MAY follow after the canonical block. The in-repo
#   gate `check-aggregate-completeness` enforces this on every run.

# `skip` — space-separated list of `check:` targets to omit from a single run.
# Default empty (full aggregate). Overridden on the command line by the Red-mode
# pre-commit hook (see check-pre-commit). When empty, the green token is written
# after a full green aggregate pass for the pre-push short-circuit.
skip := ""

# Default to listing targets when no recipe is invoked.
default:
    @just --list

# Golden-master acceptance harness. Kept outside `just check` so the
# fast aggregate remains the local/pre-push safety net while CI can
# expose this as a separate merge-gate status.
acceptance:
    uv run pytest acceptance -q

# ---------------------------------------------------------------
# Worktree-discipline recipes (the Worktree Discipline Pack).
#
# These four recipes drive the worktree lifecycle through `just` — the
# mandated runner — by calling the portable, ecosystem-neutral worktree core
# (dev-tooling/worktree-lib.sh) DIRECTLY. The CORE is the single source of
# truth for the lifecycle (create / hydrate / land / reap) and the
# primary-vs-linked detection; these recipes carry NO logic of their own —
# they only forward arguments. `just` and `lefthook` are mandated
# non-functionally across the fleet + adopters (the Conformance Pattern:
# Installer = a `just` recipe; commit gate wired via `lefthook → just check`);
# they never enter livespec core's public functional surface or the
# /livespec:* skills. Where this repo's ecosystem (python) has a
# native tool, expose it as a STRICT PASS-THROUGH wrapper onto these recipes —
# never an alternative runner: e.g. rust `cargo xtask worktree create` →
# `just worktree-create`; javascript package.json
# `"wt:create": "just worktree-create"`. Keeping the logic in the core — not
# in any wrapper — is what stops ecosystems from drifting; the drift workflow
# + `copier update` exist to catch any divergence.
#
# Hydration is the python-profile specialization in
# dev-tooling/worktree-hydrate.sh, which the core's `create`/`hydrate` verbs
# invoke automatically.
# ---------------------------------------------------------------

# Branch a fresh isolated worktree from the default branch under
# ~/.worktrees/livespec-orchestrator-git-jsonl/{{branch}} and hydrate it (python profile).
worktree-create branch base_ref="":
    ./dev-tooling/worktree-lib.sh create {{branch}} {{base_ref}}

# Run the python-profile hydrate hook in the current worktree.
worktree-hydrate:
    ./dev-tooling/worktree-lib.sh hydrate

# Rebase the current worktree branch onto the latest base, then report the
# next landing step (land_mode=pr; the core never auto-pushes).
worktree-land base_ref="":
    ./dev-tooling/worktree-lib.sh land {{base_ref}}

# Report (dry-run) or remove (--execute) stale/orphaned worktrees. Pass
# extra args through, e.g. `just worktree-reap --execute`.
worktree-reap *args:
    ./dev-tooling/worktree-lib.sh reap {{args}}

# ---------------------------------------------------------------
# Server-side worktree discipline: GitHub branch protection.
#
# The local commit-refuse hook (the structural canonical body installed at
# .git/hooks from the shared livespec-dev-tooling package) blocks commits on the
# primary checkout, but it is LOCALLY BYPASSABLE (`--no-verify`, or simply never
# installed). Branch protection is
# the server-enforced backstop: the default branch advances only via PR/merge;
# direct + force pushes are rejected by GitHub itself. Both recipes delegate to
# the portable, ecosystem-neutral dev-tooling/branch-protection.sh (the single
# source of truth) — `just` is the mandated runner and the recipes carry no
# logic of their own, exactly like the worktree-* recipes above.
#
# `protect-default-branch` (the INSTALLER) establishes baseline protection on a
# fresh repo (requires an admin-scoped gh token); it is idempotent and
# non-weakening — it leaves an existing, possibly richer, protection untouched
# unless FORCE=1. `check-branch-protection` (the VERIFIER / "tripwire") asserts
# protection is present and is fail-closed, but capability-aware: it SKIPs with
# a NAMED notice when it cannot read protection (no gh / no admin token /
# non-GitHub origin) so it never makes `just check` flaky, and honours the
# LIVESPEC_BRANCH_PROTECTION_CHECK severity lever (fail [default] | warn | skip).
# The authoritative bite belongs to the Fleet-time conformance/orchestrator
# tier, where an admin token exists.
# ---------------------------------------------------------------

# Establish baseline GitHub branch protection on the default branch (requires an
# admin-scoped gh token). Idempotent + non-weakening; FORCE=1 resets to baseline.
protect-default-branch:
    ./dev-tooling/branch-protection.sh apply

# Verify the default branch is protected (the server-side tripwire). Fail-closed
# but capability-aware; tune via LIVESPEC_BRANCH_PROTECTION_CHECK=fail|warn|skip.
check-branch-protection:
    ./dev-tooling/branch-protection.sh check

# ---------------------------------------------------------------
# First-time setup.
# ---------------------------------------------------------------

# Install the canonical livespec commit-refuse hook by REUSING the shared
# livespec-dev-tooling installer module (the SINGLE source of the structural
# hook body; pinned in pyproject.toml). NOT a repo-vendored copy — the prior
# `cp dev-tooling/git-hook-wrapper.sh` x3 + chmod block is retired so there is
# exactly ZERO drift-prone hook-body copy in this repo. This is the Installer
# slot of the Worktree-discipline concern (the Conformance Pattern: Installer =
# a `just` recipe; commit gate wired via lefthook → just check) that `bootstrap`
# delegates to. The installed body refuses commits/pushes STRUCTURALLY: it
# exits 1 when `git rev-parse --git-dir` equals `git rev-parse --git-common-dir`
# (a real primary checkout; a secondary worktree's git-dir is
# `.git/worktrees/<name>` and so differs) UNLESS `git config
# livespec.sandboxExempt` is `true`. There is therefore NO arming step and so no
# fail-open window — the hook is armed the moment it is installed. At worktrees
# (and in declared-exempt Fabro sandboxes) the body delegates to mise-managed
# lefthook so the per-hook gates fire. The installer resolves the shared hooks
# dir via git-common-dir so the install lands correctly whether invoked from the
# primary checkout or a secondary worktree. Idempotent; worktree-safe.
install-commit-refuse-hooks:
    uv run python -m livespec_dev_tooling.install_commit_refuse_hooks

# Install the canonical worktree-discipline PACK (worktree-lib.sh +
# branch-protection.sh) by REUSING the shared livespec-dev-tooling installer
# module (the SINGLE source of both bodies; pinned in pyproject.toml). NOT a
# repo-vendored copy — the prior tracked `dev-tooling/worktree-lib.sh` +
# `dev-tooling/branch-protection.sh` copies are retired so there is exactly
# ZERO drift-prone pack copy in this repo. This is the Installer slot for the
# pack facet of the Worktree-discipline concern, mirroring
# `install-commit-refuse-hooks` exactly: `bootstrap` delegates to it, and CI
# runs it before the `check-primary-checkout-commit-refuse-hook-installed`
# verifier so the verifier VALIDATES the installed pack (byte-identical to the
# package source) rather than skipping it. The installer writes both scripts
# into `dev-tooling/` and sets the executable bit; the scripts are gitignored
# (installed, not tracked), exactly as the commit-refuse hooks are installed
# into the untracked `.git/hooks/` dir. Idempotent.
install-worktree-pack:
    uv run python -m livespec_dev_tooling.install_worktree_pack

bootstrap:
    #!/usr/bin/env bash
    # Shebang recipe: the whole body runs in ONE bash process, so the indented
    # `if` block below is valid. A plain (non-shebang) recipe runs each line as
    # its own command and `just` REJECTS the extra-indented `if`-body lines
    # ("Recipe line has extra leading whitespace") — which made the rendered
    # justfile fail to parse, breaking every `just` command for a freshly
    # scaffolded or `copier update`-d consumer. Matches the other multi-line
    # recipes (check, check-pre-commit, ensure-codex-plugins).
    set -euo pipefail
    # Install the structural commit-refuse hook body as the pre-commit,
    # pre-push, and commit-msg hooks via the shared install recipe — the
    # single Installer slot of the Worktree-discipline concern. The body
    # refuses commits/pushes on the primary checkout (armed on install;
    # no arming step), honours `livespec.sandboxExempt`, and otherwise
    # delegates to mise-managed lefthook so commit-msg argv[1] reaches the
    # red-green-replay stage regardless of the user's shell config.
    just install-commit-refuse-hooks
    # Install the worktree-discipline PACK (worktree-lib.sh +
    # branch-protection.sh) from the shared livespec-dev-tooling package —
    # the single canonical source — into `dev-tooling/`. The installer
    # writes both scripts executable; they are gitignored (installed, not
    # tracked), so a fresh clone materializes them here on first bootstrap
    # exactly as the commit-refuse hooks are installed above.
    just install-worktree-pack
    # Ensure the remaining per-ecosystem worktree helper stays executable.
    # worktree-hydrate.sh is the one TRACKED dev-tooling shell script (the
    # ecosystem-specific hydration stub); the pack scripts above are written
    # +chmod'd by `install-worktree-pack`. copier preserves the executable
    # bit on a fresh `copier copy`, but a `copier update` 3-way merge can
    # re-checkout this file without it, and the worktree-hydrate recipe
    # invokes it directly (./…) — a non-executable helper would silently
    # no-op. This chmod is idempotent.
    chmod +x dev-tooling/worktree-hydrate.sh
    # Harden the beads tenant-pointer dir to owner-only on first-touch (bd
    # recommends 0700; only the owning user's bd reads it — the Dolt server
    # connects over TCP and never reads this dir). Guarded: repos with no beads
    # tenant have no .beads.
    [ -d "$(dirname "$(git rev-parse --git-common-dir)")/.beads" ] && chmod 700 "$(dirname "$(git rev-parse --git-common-dir)")/.beads" || true
    # Idempotent worktree-root + mise-trust setup. Every git worktree in
    # the fleet lives under a single per-user root, ~/.worktrees/<repo>/
    # <branch> (per livespec/SPECIFICATION/non-functional-requirements.md
    # §"Worktree root and mise trust"). Registering that root as one of
    # mise's trusted_config_paths makes each freshly created worktree's
    # .mise.toml auto-trusted, so the first `mise exec` inside it never
    # stops on the "config not trusted" prompt — the failure that
    # otherwise wastes a tool round-trip on every new worktree. The grep
    # guard keeps the global ~/.config/mise/config.toml entry single on
    # repeated bootstraps; the value is the absolute $HOME-rooted path so
    # it resolves identically from any invocation site.
    mkdir -p "${HOME}/.worktrees"
    mise settings get trusted_config_paths 2>/dev/null | grep -qF "${HOME}/.worktrees" || mise settings add trusted_config_paths "${HOME}/.worktrees"
    just ensure-plugins
    just ensure-codex-plugins

# Idempotent: `claude plugin marketplace add` and `claude plugin install`
# both exit 0 when the target is already present. livespec@livespec is
# the core artifact carrier (prose + reference CLIs);
# livespec@livespec-driver-claude is the Claude Code Driver that
# exposes the /livespec:* commands — both are required for the
# spec-side surface.
ensure-plugins:
    claude plugin marketplace add --scope project thewoolleyman/livespec
    claude plugin marketplace add --scope project thewoolleyman/livespec-driver-claude
    claude plugin marketplace add --scope project thewoolleyman/livespec-orchestrator-git-jsonl
    claude plugin install -s project livespec@livespec
    claude plugin install -s project livespec@livespec-driver-claude
    claude plugin install -s project livespec-orchestrator-git-jsonl@livespec-orchestrator-git-jsonl

# Idempotent host-wide Codex plugin provisioning. Codex does not support
# project-scoped plugin enablement, so these registrations intentionally land in
# the user's default CODEX_HOME and are visible to every repo on the host. Codex
# is an optional dogfooding runtime; bootstrap skips this target when the CLI is
# absent but fails on real install errors when Codex is present.
ensure-codex-plugins:
    #!/usr/bin/env bash
    set -euo pipefail
    if ! command -v codex >/dev/null 2>&1; then
        echo "codex CLI not found; skipping host-wide Codex plugin install." >&2
        exit 0
    fi
    codex plugin marketplace add thewoolleyman/livespec
    codex plugin marketplace add thewoolleyman/livespec-driver-codex
    codex plugin marketplace add thewoolleyman/livespec-orchestrator-git-jsonl
    codex plugin marketplace upgrade livespec
    codex plugin marketplace upgrade livespec-driver-codex
    codex plugin marketplace upgrade livespec-orchestrator-git-jsonl
    codex plugin add livespec@livespec
    codex plugin add livespec@livespec-driver-codex
    codex plugin add livespec-orchestrator-git-jsonl@livespec-orchestrator-git-jsonl

# ---------------------------------------------------------------
# Aggregate check — canonical full-set stamped at copier-copy time.
#
# The `targets=(...)` array below is Jinja-rendered from the committed
# copier-template DATA file `canonical-slugs.yml`, which is a
# release-time projection of
# `livespec_dev_tooling.canonical_checks.canonical_check_slugs()` (the
# single source of truth) regenerated in livespec via
# `just stamp-canonical-slugs`. The block is Jinja-included from that
# data file and line-parsed below — import-free, so it renders
# correctly on BOTH the smoke-check flow AND the consumer
# `copier update` flow (copier clones the template to an ephemeral
# checkout with no PYTHONPATH injection, where a render-time copier
# jinja-extension importing the dev-tooling module cannot resolve).
# Per livespec/SPECIFICATION/contracts.md
# §"Shared code sync — livespec-dev-tooling" → Template gate, every
# newly-generated `livespec-impl-*` sibling inherits the full canonical
# aggregate from inception; existing siblings see canonical-set growth
# as a real reviewable diff on `copier update` (3-way merge surfaces
# canonical drift).
#
# The data file resolves at the Jinja loader root, which differs
# between the two flows (smoke-check flow: loader root is
# templates/impl-plugin/; consumer flow: loader root is the repo/clone
# root, with _subdirectory routing). A Jinja list-include tries
# "canonical-slugs.yml" then "templates/impl-plugin/canonical-slugs.yml"
# and uses the first that exists, so one physical data file serves both
# flows import-free.
#
# Slugs are stamped in alphabetical order (sorted at the source). DO
# NOT hand-edit this list — extend the canonical set by adding
# `livespec_dev_tooling/checks/<name>.py` in the dev-tooling sibling
# repo, re-run `just stamp-canonical-slugs` in livespec, cut a template
# release, then re-run `copier update --vcs-ref=master` here.
# ---------------------------------------------------------------

check:
    #!/usr/bin/env bash
    set -uo pipefail
    # Sync the environment ONCE per aggregate pass, then run every
    # target with UV_NO_SYNC=1 so the per-target `uv run`
    # invocations skip their redundant per-invocation re-sync
    # (work-item livespec-7dro). The single up-front sync
    # keeps the freshness guarantee — a stale lockfile/venv still
    # fails here, loudly, before any target runs. This also caps the
    # cost of a corrupted-venv re-sync loop (e.g. an orphaned
    # dist-info missing its RECORD file, which a sync can never
    # uninstall and therefore retries on EVERY invocation) at one
    # sync attempt per pass instead of one per target, and shrinks
    # the concurrent-sync race window that produces that corruption
    # in the first place. Standalone `just check-<x>` invocations
    # keep uv's default sync-on-run behavior; CI's per-target matrix
    # jobs each sync their own fresh runner and are unaffected.
    if ! uv sync --all-groups; then
        echo "ERROR: up-front 'uv sync --all-groups' failed; aborting the check aggregate" >&2
        exit 1
    fi
    export UV_NO_SYNC=1
    read -ra skip_targets <<< "{{skip}}"
    targets=(
        # ---- Canonical block (41 slugs, alphabetical) ----
        check-agents-ai-references-resolve
        check-aggregate-completeness
        check-all-declared
        check-assert-never-exhaustiveness
        check-branch-protection-alignment
        check-check-coverage-incremental
        check-check-mutation
        check-check-tools
        check-claude-md-coverage
        check-comment-line-anchors
        check-commit-pairs-source-and-test
        check-file-lloc
        check-global-writes
        check-heading-coverage
        check-keyword-only-args
        check-main-guard
        check-master-ci-green
        check-match-keyword-only
        check-newtype-domain-primitives
        check-no-direct-destructive-cli
        check-no-direct-tool-invocation
        check-no-except-outside-io
        check-no-inheritance
        check-no-lloc-soft-warnings
        check-no-raise-outside-io
        check-no-todo-registry
        check-no-write-direct
        check-pbt-coverage-pure-modules
        check-per-file-coverage
        check-plugin-resolution
        check-primary-checkout-commit-refuse-hook-installed
        check-private-calls
        check-public-api-result-typed
        check-red-green-replay
        check-rop-pipeline-shape
        check-skill-invocation-paths
        check-supervisor-discipline
        check-tests-mirror-pairing
        check-tests-no-subprocess-spawn
        check-tool-backed-check-completeness
        check-vendor-manifest
        check-wrapper-shape
        # ---- livespec-orchestrator-git-jsonl-private block ----
        # Tool-backed checks (ruff lint, ruff format, pyright types,
        # aggregate coverage) — helper recipes, NOT canonical slugs
        # (not under livespec_dev_tooling/checks/), so check-aggregate-
        # completeness does not enforce them. They are wired here as
        # LITERAL members so the local `just check` aggregate gives full
        # lint / format / types / coverage feedback and matches the CI
        # check-python matrix; the check-tool-backed-check-completeness
        # meta-check (canonical block above, dev-tooling v0.8.0)
        # enforces that both-surfaces wiring (epic li-pyright-gate,
        # work-item li-pyright-gate-wi3, LITERAL-membership design).
        # check-coverage gates the aggregate `fail_under = 100` off the
        # SINGLE pytest run that the canonical check-per-file-coverage
        # already performed (it reads the existing `.coverage`), so
        # wiring it here adds NO duplicate suite run. In Red-mode
        # pre-commit, check-coverage + check-per-file-coverage are
        # omitted by `check-pre-commit` via `just skip="..."` — a
        # self-contained just variable, no ambient env var (epic
        # li-cvaudit, cvredmd).
        check-format
        check-lint
        check-types
        check-coverage
        # Orchestrator-private store-integrity checks, per
        # SPECIFICATION/contracts.md "Append-only store disciplines" ->
        # "Store-integrity checks (orchestrator-private)" (v008): wired
        # into THIS repo's `just check` aggregate (NOT livespec's
        # doctor — the work-items store is orchestrator-private under
        # the re-steered contract).
        check-no-divergent-heads
        check-no-raw-store-read
        # Plugin-private merge-evidence static check, per
        # SPECIFICATION/contracts.md "Work-items JSONL record schema"
        # -> "work_item_merge_evidence static check" (li-tenpup):
        # closed work-items with merge-implying resolutions must carry
        # an audit merge_sha reachable from origin/<canonical_branch>.
        check-work-item-merge-evidence
        # livespec core's doctor STATIC phase — wired LAST (after the
        # tool-backed slugs and the store-integrity checks) so the
        # aggregate_completeness meta-check, which enforces ordering only
        # on the canonical block, is unaffected (livespec epic livespec-6jfq).
        check-doctor-static
    )
    failed=()
    ran=0
    for t in "${targets[@]}"; do
        skip_this=0
        for s in "${skip_targets[@]:-}"; do
            if [[ "$t" == "$s" ]]; then
                skip_this=1
                break
            fi
        done
        if [[ "$skip_this" -eq 1 ]]; then
            printf '\n::: just %s (skipped)\n' "$t"
            continue
        fi
        ran=$((ran + 1))
        printf '\n::: just %s\n' "$t"
        if ! just "$t"; then
            failed+=("$t")
        fi
    done
    # Worktree Discipline Pack — server-side branch-protection tripwire. Run as
    # a direct step rather than a canonical-slug target because it reads
    # external GitHub state, not the source tree. Capability-aware: it SKIPs
    # with a named notice when it cannot read protection (no gh / no admin
    # token / non-GitHub origin), so it never makes `just check` flaky; it is
    # fail-closed where it CAN read (honouring LIVESPEC_BRANCH_PROTECTION_CHECK).
    printf '\n::: branch-protection (server-side worktree-discipline tripwire)\n'
    if ! ./dev-tooling/branch-protection.sh check; then
        failed+=("branch-protection")
    fi
    if [[ ${#failed[@]} -gt 0 ]]; then
        printf '\nFailed targets (%d):\n' "${#failed[@]}"
        printf '  - %s\n' "${failed[@]}"
        exit 1
    fi
    printf '\nAll %d targets passed.\n' "${#targets[@]}"
    if [[ -z "{{skip}}" ]]; then uv run python -m livespec_dev_tooling.green_token write || true; fi

# ---------------------------------------------------------------
# Tool-backed checks (livespec-orchestrator-git-jsonl-private).
# ---------------------------------------------------------------

check-lint:
    uv run ruff check .

check-format:
    uv run ruff format --check .

check-types:
    uv run pyright

# Aggregate (total) coverage gate at `fail_under = 100` (pyproject.toml
# [tool.coverage.report]). Wired as a LITERAL member of the `check:`
# targets array (private block) AND the CI check-python matrix; the
# check-tool-backed-check-completeness meta-check (dev-tooling v0.8.0)
# enforces that both-surfaces wiring. To avoid a DUPLICATE full pytest
# run when invoked inside `just check`, this recipe gates off the
# EXISTING `.coverage` data file when present — the canonical
# check-per-file-coverage slug runs `pytest --cov` upfront and sorts
# alphabetically BEFORE this private extra, so `.coverage` already
# exists by the time this runs locally. When `.coverage` is ABSENT —
# the CI check-python matrix runs check-coverage as a standalone job in
# its own runner with no prior pytest — the recipe runs the suite
# itself so the aggregate gate still fires there. In Red-mode pre-commit
# this target is omitted by `check-pre-commit` via the `just skip=...`
# argument (coverage is verified at the Green amend), so no ambient
# env-var read is needed here (epic li-cvaudit, cvredmd). Mirrors
# dev-tooling's coverage-reuse recipe.
check-coverage:
    #!/usr/bin/env bash
    set -uo pipefail
    if [[ -f .coverage ]]; then
        echo ":: check-coverage: reading existing .coverage (produced by check-per-file-coverage); no duplicate suite run"
        uv run coverage report --fail-under=100
    else
        echo ":: check-coverage: no .coverage data file (CI standalone job); running the suite"
        uv run pytest -n auto --cov --cov-branch --cov-config=pyproject.toml --cov-report=term-missing
    fi

# ---------------------------------------------------------------
# Orchestrator-private store-integrity checks (livespec-impl-git-
# jsonl-private; v008 SPECIFICATION/contracts.md "Append-only store
# disciplines"). Both consume the canonical reducer / query surface
# in livespec_orchestrator_git_jsonl.store — never a private re-derivation
# of "latest wins" (the one-canonical-reducer obligation).
# ---------------------------------------------------------------

# Fails when any entity id in the declared backing store (work-items)
# resolves to more than one un-superseded head, naming the offending
# entity id and the conflicting record identities. An absent store
# file is skipped; a malformed/schema-violating store fails.
check-no-divergent-heads:
    uv run python3 .claude-plugin/scripts/bin/check_no_divergent_heads.py

# Fails when shipped code (committed .py under .claude-plugin/scripts/
# and dev-tooling/, _vendor/ excluded) opens a declared backing store
# path directly, bypassing the reducer/query surface. The canonical
# store module is the one exemption. Scope is committed code only —
# ad-hoc interactive shell reads are defended by the record
# self-identification + order-independent-reduction obligations.
check-no-raw-store-read:
    uv run python3 .claude-plugin/scripts/bin/check_no_raw_store_read.py

# Plugin-private merge-evidence static check (li-tenpup;
# SPECIFICATION/contracts.md "Work-items JSONL record schema" ->
# "work_item_merge_evidence static check"). Walks the materialized
# work-items view: closed work-items with merge-implying resolutions
# (completed, spec-revised, resolved-out-of-band) must carry an audit
# merge_sha that exists locally and is reachable from
# origin/<canonical_branch> (local git cat-file/merge-base only —
# network-free); administratively closed items must NOT carry
# merge-evidence; closed epics instead require every local depends_on
# child closed. The backfill grandfather sentinel is exempt from the
# reachability test. An absent store file is a pass (noted, skipped).
check-work-item-merge-evidence:
    uv run python3 .claude-plugin/scripts/bin/check_work_item_merge_evidence.py

# livespec core's doctor STATIC phase (reference-discipline + out-of-band
# invariants) against THIS repo's SPECIFICATION/ tree, wired fleet-wide per
# livespec epic livespec-6jfq. core ships the checker: doctor_static.py is
# self-contained (vendored deps + bare python3), so it runs under plain
# python3 and NEVER `uv run`. Resolve core's plugin root via
# LIVESPEC_CORE_PLUGIN_ROOT (CI sets it to a livespec checkout at this repo's
# .livespec.jsonc compat.pinned tag) → else the installed livespec@livespec
# plugin cache (local dev). The two reference-discipline checks
# (no-cross-spec-reference, no-spec-section-citation-in-code) are pure reads;
# doctor-out-of-band-edits is self-healing — on a drifted tree it writes a
# history backfill into the worktree and fails, and committing that backfill
# heals the track; on a clean tree it never fires.
check-doctor-static:
    #!/usr/bin/env bash
    set -euo pipefail
    core_root="${LIVESPEC_CORE_PLUGIN_ROOT:-}"
    if [ -z "$core_root" ]; then
      core_root="$(python3 -c 'import json, pathlib; print(json.loads((pathlib.Path.home() / ".claude" / "plugins" / "installed_plugins.json").read_text(encoding="utf-8"))["plugins"]["livespec@livespec"][0]["installPath"])' 2>/dev/null || true)"
    fi
    if [ -z "$core_root" ] || [ ! -f "$core_root/scripts/bin/doctor_static.py" ]; then
      echo "livespec core not found. Set LIVESPEC_CORE_PLUGIN_ROOT to a livespec checkout's .claude-plugin, or install the livespec@livespec plugin (claude plugin install livespec@livespec)." >&2
      exit 1
    fi
    python3 "$core_root/scripts/bin/doctor_static.py" --project-root .

# ---------------------------------------------------------------
# Canonical structural checks (shared from livespec-dev-tooling).
# Wired in alphabetical order to match the aggregate above.
# ---------------------------------------------------------------

# AGENTS.md `.ai/<topic>.md` reference-resolution static check
# (livespec core §"Fleet agent-instruction core"): every `.ai/`
# reference in AGENTS.md must resolve to an existing file. Canonical
# since livespec-dev-tooling v0.21; wired here at the v0.21.2 bump.
check-agents-ai-references-resolve:
    uv run python -m livespec_dev_tooling.checks.agents_ai_references_resolve

# In-repo gate for the wiring-completeness invariant
# (SPECIFICATION/contracts.md v094 §"Shared code sync —
# livespec-dev-tooling"). Parses the local `justfile`'s `check:`
# recipe and verifies every canonical slug emitted by
# `livespec_dev_tooling.canonical_checks` is wired in alphabetical
# order, with private extras appearing only after the canonical
# block. Self-bootstrapping: the slug `check-aggregate-completeness`
# is itself canonical, so dropping it would fail this check on the
# next run.
check-aggregate-completeness:
    uv run python -m livespec_dev_tooling.checks.aggregate_completeness

check-all-declared:
    uv run python -m livespec_dev_tooling.checks.all_declared

check-assert-never-exhaustiveness:
    uv run python -m livespec_dev_tooling.checks.assert_never_exhaustiveness

# Layer 1 mechanical check: shells out to `gh api` to read remote
# GitHub state; exits 0 with a structured warning when `gh` is
# unavailable or unauthenticated locally so per-commit pre-commit
# runs are not blocked. CI with GH_TOKEN exercises the full
# enforcement path.
check-branch-protection-alignment:
    uv run python -m livespec_dev_tooling.checks.branch_protection_alignment

# Path-scoped fast-feedback variant of check-coverage. With explicit
# `--paths <impl_path> [<impl_path>...]` (repo-root-relative) it scopes
# the per-file 100% gate to those paths. With NO args (the canonical
# aggregate / `just check` invocation) the check DERIVES the changed
# impl-`.py` set from `git diff --name-only origin/master...HEAD` and
# gates those — no longer a no-op (epic li-cvaudit, cvnoarg). The
# interactive developer use case still passes `--paths` explicitly:
# `just check-check-coverage-incremental --paths .claude-plugin/scripts/bin/foo.py`.
check-check-coverage-incremental *args:
    uv run python -m livespec_dev_tooling.checks.check_coverage_incremental {{args}}

# `check-static` — fastest-first fail-fast helper for fast agent/dev
# feedback (work-item livespec-dev-tooling-7us.8). Runs ONLY the cheap
# static checks — `ruff format --check .`, `ruff check .`, `pyright`
# (i.e. check-format, check-lint, check-types) — as a fail-fast
# sequence: it STOPS at the first failing check and exits non-zero, so
# a sub-2s ruff/pyright failure surfaces immediately instead of after
# `just check`'s slow pytest+coverage tail. This is a developer/agent
# convenience like the helper recipes above; it is deliberately NOT a
# member of the `check:` aggregate `targets=(...)` array, NOT a
# canonical slug (no livespec_dev_tooling/checks/ module), and NOT in
# the CI matrix. The authoritative full gate remains `just check`
# (still run at pre-push and in CI) — `check-static` is a fast
# pre-flight, never a replacement for it.
check-static:
    #!/usr/bin/env bash
    set -euo pipefail
    uv run ruff format --check .
    uv run ruff check .
    uv run pyright

# `changed-files` — print the changed `.py` set this branch touches,
# repo-root-relative, one path per line, sorted + de-duplicated
# (work-item livespec-dev-tooling-7us.9). The set is the UNION of two
# git views, so an agent gets the live working set whether or not it has
# committed yet:
#   - `git diff --name-only origin/master...HEAD` — every `.py` this
#     branch's commits changed vs the merge-base with origin/master;
#   - `git diff --cached --name-only --diff-filter=AM` — added/modified
#     `.py` currently staged but not yet committed.
# This is the exact set `check-changed` consumes for its scoped gate.
# Helper recipe (like `check-static`): NOT a member of the `check:`
# aggregate `targets=(...)` array, NOT a canonical slug, NOT in the CI
# matrix.
changed-files:
    #!/usr/bin/env bash
    set -uo pipefail
    # `grep` exits 1 on zero matches; an empty changed set is normal (a
    # clean branch), so swallow that into exit 0 via `|| true` — the
    # consuming `check-changed` treats empty as "nothing to gate".
    { git diff --name-only origin/master...HEAD;
      git diff --cached --name-only --diff-filter=AM; } \
        | { grep -E '\.py$' || true; } | sort -u

# `check-changed` — modified-files INNER-LOOP gate for fast scoped
# feedback during iteration (work-item livespec-dev-tooling-7us.9). Feeds
# the `changed-files` set into `check-check-coverage-incremental --paths
# <set>`, which already (a) resolves each changed impl `.py` to its
# mirror-paired test and runs that pytest SUBSET, and (b) applies the
# path-scoped per-file coverage gate — i.e. it composes the existing
# scoping plumbing rather than re-deriving it. An empty changed set is a
# no-op (exit 0): nothing changed, nothing to gate.
#
# SCOPE — INNER-LOOP SPEEDUP ONLY, NOT a replacement for the final gate.
# It runs only the test subset + path-scopable checks for the files this
# branch touched, so an agent gets sub-suite feedback while iterating. The
# AUTHORITATIVE gate remains `just check`, which runs the FULL suite + the
# full AST scans + the aggregate 100% coverage gate at pre-push and in CI.
# Like `check-static`, this is a developer/agent convenience: NOT a member
# of the `check:` aggregate `targets=(...)` array, NOT a canonical slug,
# and NOT in the CI matrix.
check-changed:
    #!/usr/bin/env bash
    set -uo pipefail
    mapfile -t changed < <(just changed-files)
    if [[ "${#changed[@]}" -eq 0 ]]; then
        echo ":: check-changed: no changed .py vs origin/master (and none staged); nothing to gate"
        echo ":: the authoritative full gate remains 'just check' (run at pre-push + CI)"
        exit 0
    fi
    echo ":: check-changed: scoping the test subset + per-file coverage gate to ${#changed[@]} changed .py:"
    printf '   %s\n' "${changed[@]}"
    echo ":: INNER-LOOP ONLY — 'just check' runs the FULL suite/AST scans at pre-push + CI"
    just check-check-coverage-incremental --paths "${changed[@]}"

# Always invoked plainly; the module self-manages its RUN/SKIP lever
# (epic li-cvaudit, cvtodo). `LIVESPEC_RUN_MUTATION` unset → the check
# logs "skipped" and exits 0; set to a non-empty value (CI sets it to
# `true`) → the mutmut suite runs. No external gate, no silent skip.
check-check-mutation:
    uv run python -m livespec_dev_tooling.checks.check_mutation

check-check-tools:
    uv run python -m livespec_dev_tooling.checks.check_tools

check-claude-md-coverage:
    uv run python -m livespec_dev_tooling.checks.claude_md_coverage

check-comment-line-anchors:
    uv run python -m livespec_dev_tooling.checks.comment_line_anchors

# Commit-pair gate: every commit touching source files also touches
# tests. Lefthook pre-commit only is the load-bearing per-commit
# invocation; wired into the aggregate per the wiring-completeness
# invariant.
check-commit-pairs-source-and-test:
    uv run python -m livespec_dev_tooling.checks.commit_pairs_source_and_test

check-file-lloc:
    uv run python -m livespec_dev_tooling.checks.file_lloc

check-global-writes:
    uv run python -m livespec_dev_tooling.checks.global_writes

check-heading-coverage:
    uv run python -m livespec_dev_tooling.checks.heading_coverage

check-keyword-only-args:
    uv run python -m livespec_dev_tooling.checks.keyword_only_args

check-main-guard:
    uv run python -m livespec_dev_tooling.checks.main_guard

# Layer 1 mechanical check: shells out to `gh api` to read remote
# GitHub state; exits 0 with a structured warning when `gh` is
# unavailable or unauthenticated locally so per-commit pre-commit
# runs are not blocked. CI with GH_TOKEN exercises the full
# enforcement path.
check-master-ci-green:
    uv run python -m livespec_dev_tooling.checks.master_ci_green

check-match-keyword-only:
    uv run python -m livespec_dev_tooling.checks.match_keyword_only

check-newtype-domain-primitives:
    uv run python -m livespec_dev_tooling.checks.newtype_domain_primitives

# Destructive-default CLI wrapping gate (livespec/SPECIFICATION/
# non-functional-requirements.md §"Destructive-default CLI wrapping"):
# greps the agent-facing trees (dev-tooling/, .claude-plugin/,
# .claude/plugins/) for direct invocations of known-destructive-default
# CLIs (bd init, git push --force/-f, git reset --hard, gh repo delete)
# outside the explicit `[tool.livespec_dev_tooling].
# destructive_cli_allowlist` path-prefix allowlist.
check-no-direct-destructive-cli:
    uv run python -m livespec_dev_tooling.checks.no_direct_destructive_cli

check-no-direct-tool-invocation:
    uv run python -m livespec_dev_tooling.checks.no_direct_tool_invocation

check-no-except-outside-io:
    uv run python -m livespec_dev_tooling.checks.no_except_outside_io

check-no-inheritance:
    uv run python -m livespec_dev_tooling.checks.no_inheritance

# Always invoked plainly; the module self-manages its severity lever
# (epic li-cvaudit, cvtodo). The 201-250 LLOC soft-band scan ALWAYS
# runs; `LIVESPEC_FAIL_IF_LLOC_SOFT_WARNINGS_EXIST` unset → soft-band
# offenders warn + exit 0; set (CI sets it to `true`) → they fail.
check-no-lloc-soft-warnings:
    uv run python -m livespec_dev_tooling.checks.no_lloc_soft_warnings

check-no-raise-outside-io:
    uv run python -m livespec_dev_tooling.checks.no_raise_outside_io

# Always invoked plainly; the module self-manages its severity lever
# (epic li-cvaudit, cvtodo). The heading-coverage.json TODO scan ALWAYS
# runs; `LIVESPEC_FAIL_IF_HEADING_COVERAGE_TODOS_EXIST` unset → TODO
# offenders warn + exit 0 (authoring placeholders surface without
# blocking per-commit `just check`); set (CI sets it to `true`) → they
# fail. Replaces the prior LIVESPEC_RELEASE_GATE skip carve-out, which
# silently skipped the scan entirely when the gate was unset.
check-no-todo-registry:
    uv run python -m livespec_dev_tooling.checks.no_todo_registry

check-no-write-direct:
    uv run python -m livespec_dev_tooling.checks.no_write_direct

check-pbt-coverage-pure-modules:
    uv run python -m livespec_dev_tooling.checks.pbt_coverage_pure_modules

# Full per-file 100% line+branch coverage gate. Canonical-slug
# alias for the shared per_file_coverage check. In Red-mode pre-commit
# this target is omitted by `check-pre-commit` via the `just skip=...`
# argument (coverage is verified at the Green amend), so no ambient
# env-var read is needed here (epic li-cvaudit, cvredmd).
check-per-file-coverage:
    #!/usr/bin/env bash
    set -uo pipefail
    # pytest-cov defaults `--cov-config` to `.coveragerc`, which
    # bypasses pyproject.toml's `[tool.coverage.run]` (including
    # the `omit = [...]` carve-outs). Pass the config path
    # explicitly so the vendored-tree exclusion takes effect.
    uv run pytest -n auto --cov --cov-branch --cov-config=pyproject.toml --cov-report=term-missing
    uv run python -m livespec_dev_tooling.checks.per_file_coverage

# Shared baseline plugin-resolution Verifier (Conformance-Pattern,
# livespec-zs22.7.7 M6). The check is shipped by livespec-dev-tooling;
# this recipe is the project-root-scoped CI/just-check adoption.
check-plugin-resolution:
    uv run python -m livespec_dev_tooling.checks.plugin_resolution

# Family-wide commit-refuse hook invariant per livespec/SPECIFICATION/
# non-functional-requirements.md §"Primary-checkout commit-refuse hook"
# (v095). Supersedes the v091-v094 bare-flag mechanism, which caused
# stale-on-disk-read failures at primaries. The check is shipped by
# livespec-dev-tooling (>=v0.5.0); this recipe is the project-root-
# scoped CI/just-check adoption that the spec mandates for every
# consumer repo.
check-primary-checkout-commit-refuse-hook-installed:
    uv run python -m livespec_dev_tooling.checks.primary_checkout_commit_refuse_hook_installed

check-private-calls:
    uv run python -m livespec_dev_tooling.checks.private_calls

check-public-api-result-typed:
    uv run python -m livespec_dev_tooling.checks.public_api_result_typed

# Trailer-based Red→Green replay verification (hard gate). Invoked by
# lefthook commit-msg stage with the commit-message file path as argv[1]
# (the load-bearing per-commit verifier). The canonical aggregate /
# `just check` invokes this with NO msg_path; the module then DERIVES
# the message from `git log -1 --format=%B` (HEAD) and validates it —
# no longer a no-op (epic li-cvaudit, cvnoarg).
check-red-green-replay *args:
    uv run python -m livespec_dev_tooling.checks.red_green_replay {{args}}

check-rop-pipeline-shape:
    uv run python -m livespec_dev_tooling.checks.rop_pipeline_shape

check-skill-invocation-paths:
    uv run python -m livespec_dev_tooling.checks.skill_invocation_paths

check-supervisor-discipline:
    uv run python -m livespec_dev_tooling.checks.supervisor_discipline

check-tests-mirror-pairing:
    uv run python -m livespec_dev_tooling.checks.tests_mirror_pairing

# Forbid test-spawned Python subprocesses (`subprocess.run([sys.executable, ...])`)
# in tests/ — they self-instrument under `pytest --cov` and race concurrent
# coverage runs; prefer the in-process `main()` pattern. Canonical check added
# in livespec-dev-tooling v0.14.1 (4i5). In `just check` aggregate.
check-tests-no-subprocess-spawn:
    uv run python -m livespec_dev_tooling.checks.tests_no_subprocess_spawn

# Tool-backed-check completeness meta-check (epic li-pyright-gate,
# work-item li-pyright-gate-wi3; shared from livespec-dev-tooling
# v0.8.0). Asserts each tool-backed check (check-lint / check-format /
# check-types / check-coverage) is a LITERAL member of BOTH this
# justfile's `check:` targets=(...) array AND the CI check-python
# matrix. Self-passes because the targets array (private block) + CI
# matrix wire all four literally.
check-tool-backed-check-completeness:
    uv run python -m livespec_dev_tooling.checks.tool_backed_check_completeness

check-vendor-manifest:
    uv run python -m livespec_dev_tooling.checks.vendor_manifest

check-wrapper-shape:
    uv run python -m livespec_dev_tooling.checks.wrapper_shape

# ---------------------------------------------------------------
# CLI end-to-end harness (top-of-pyramid, user-surface tier).
# ---------------------------------------------------------------

# Run the CLI end-to-end harness against this plugin's own per-skill
# fixtures (per livespec/SPECIFICATION/contracts.md §"CLI end-to-end
# harness contract"). The harness ships from livespec-dev-tooling
# (v0.8.0) and is consumed via the imported test_workflow_full_round_
# trip entry point wired in tests/e2e-cli/. Defaults to the MOCK tier
# (LIVESPEC_E2E_HARNESS=mock — the one mocked boundary is the
# `claude -p` subprocess; real install-shape setup, real structural
# skill discovery, the real fail-closed time-bomb coverage gate, and
# the real per-skill orchestration loop all run). The fail-closed
# coverage gate raises CoverageGateError when a `/livespec-impl-
# git-jsonl:*` skill lacks a fixture, failing this target. The CI
# `e2e-cli` job delegates here (no direct tool invocation in the
# workflow). The mock-tier test ALSO runs as part of the normal suite
# under check-per-file-coverage; this target is the dedicated,
# explicitly-named tier entry point CI reports as its own status.
check-e2e-cli:
    uv run pytest tests/e2e-cli -v

# ---------------------------------------------------------------
# Pre-commit aggregate — Red-mode-aware. Classifies the staged
# tree shape; in Red mode it passes `skip="check-coverage
# check-per-file-coverage"` to `just check` so the coverage gates
# are omitted (the commit-msg replay hook is the verifier; coverage
# is checked at the Green amend). This is a self-contained recipe
# argument — there is NO ambient env var (epic li-cvaudit, cvredmd).
# Pre-push and CI keep invoking `just check` directly.
# ---------------------------------------------------------------

check-pre-commit:
    #!/usr/bin/env bash
    set -uo pipefail
    staged=$(git diff --cached --name-only --diff-filter=AM)
    py_staged=$(echo "$staged" | grep -E '\.py$' || true)
    test_staged=$(echo "$staged" | grep -E '^tests/.*\.py$' || true)
    impl_staged=$(echo "$staged" | grep -E '^(\.claude-plugin/scripts/|dev-tooling/checks/).*\.py$' || true)
    test_count=0
    impl_count=0
    [[ -n "$test_staged" ]] && test_count=$(echo "$test_staged" | wc -l)
    [[ -n "$impl_staged" ]] && impl_count=$(echo "$impl_staged" | wc -l)
    if [[ -z "$py_staged" ]]; then
        echo ":: doc-only mode detected (zero .py files staged): running just check-pre-commit-doc-only"
        echo ":: pre-push + CI keep the full aggregate as the load-bearing safety net"
        just check-pre-commit-doc-only
        exit $?
    fi
    if [[ "$test_count" -eq 1 ]] && [[ "$impl_count" -eq 0 ]]; then
        echo ":: Red-mode shape detected: $test_staged"
        echo ":: skipping coverage gates (commit-msg replay hook is the verifier; coverage runs at Green amend)"
        just skip="check-coverage check-per-file-coverage" check
        exit $?
    fi
    # Green-amend shape: impl staged while HEAD still carries Red-only
    # trailers (the Green amend has not yet written its TDD-Green-*
    # trailers — the commit-msg `check-red-green-replay {1}` hook writes
    # AND verifies them immediately after this pre-commit pass). The
    # no-arg `check-red-green-replay` aggregate variant validates HEAD,
    # which during a Green amend is the in-progress Red commit; it would
    # otherwise reject a perfectly valid Green amend. Skip the aggregate
    # variant here (the commit-msg hook is the load-bearing per-commit
    # verifier); pre-push + CI re-run the full no-arg aggregate against
    # the completed Red->Green HEAD as the safety net.
    head_msg=$(git log -1 --format=%B 2>/dev/null || true)
    if [[ "$impl_count" -ge 1 ]] \
        && grep -q 'TDD-Red-Test-File-Checksum:' <<< "$head_msg" \
        && ! grep -q 'TDD-Green-Verified-At:' <<< "$head_msg"; then
        echo ":: Green-amend shape detected (impl staged; HEAD carries Red-only trailers)"
        echo ":: skipping no-arg check-red-green-replay (commit-msg replay hook verifies the Green amend)"
        just skip="check-red-green-replay" check
        exit $?
    fi
    just check

# When zero `.py` files are staged, `check-pre-commit` delegates here.
# Pre-push delegates here via `check-pre-push` for zero-py changesets.
# check-claude-md-coverage and check-heading-coverage are intentionally
# absent here: backlog work-items li-bb5suo (CLAUDE.md backfill) and
# li-4liaxt (heading-coverage backfill) close the gap; until those land
# they would force every doc-only commit to fail the pre-commit gate.
# They remain wired in the full `just check` aggregate (and surface in
# pre-push) as the load-bearing canonical contract.
check-pre-commit-doc-only:
    #!/usr/bin/env bash
    set -uo pipefail
    targets=(
        check-vendor-manifest
        check-no-direct-tool-invocation
        check-check-tools
    )
    failed=()
    for t in "${targets[@]}"; do
        printf '\n::: just %s\n' "$t"
        if ! just "$t"; then
            failed+=("$t")
        fi
    done
    if [[ ${#failed[@]} -gt 0 ]]; then
        printf '\nFailed targets (%d):\n' "${#failed[@]}"
        printf '  - %s\n' "${failed[@]}"
        exit 1
    fi
    printf '\nAll %d doc-only targets passed.\n' "${#targets[@]}"

# Skip the Python-code check subset when the pushed commits contain
# zero `.py` changes; those checks are deterministic functions of
# the source tree and would pass-or-fail identically against the
# merge-base. Falls back to `origin/master` when no upstream branch
# is configured locally.
check-pre-push:
    #!/usr/bin/env bash
    set -uo pipefail
    upstream=$(git rev-parse --abbrev-ref --symbolic-full-name @{upstream} 2>/dev/null || echo "origin/master")
    changeset=$(git diff --name-only "${upstream}..HEAD")
    py_changed=$(echo "$changeset" | grep -E '\.py$' || true)
    if [[ -z "$py_changed" ]]; then
        echo ":: doc-only push detected (zero .py changes vs ${upstream}): running check-pre-commit-doc-only"
        just check-pre-commit-doc-only
        exit $?
    fi
    if uv run python -m livespec_dev_tooling.green_token check 2>&1; then
        echo ":: pre-push: green token matched — tree byte-identical to last green check; skipping full aggregate (CI is authoritative)"
        exit 0
    fi
    just check

# ---------------------------------------------------------------
# Pre-commit auxiliary gates.
# ---------------------------------------------------------------

# Ruff fix + format on staged .py files BEFORE the rest of the
# pre-commit gate runs. Non-blocking — unfixable issues fall through
# to check-lint / check-format inside `just check` later. Re-stages
# post-autofix bytes.
lint-autofix-staged:
    #!/usr/bin/env bash
    set -uo pipefail
    staged=$(git diff --cached --name-only --diff-filter=AM | grep -E '\.py$' || true)
    if [[ -z "$staged" ]]; then
        exit 0
    fi
    echo "$staged" | xargs uv run ruff check --fix --exit-zero
    echo "$staged" | xargs uv run ruff format
    echo "$staged" | xargs git add

# ---------------------------------------------------------------
# Mutating targets (opt-in; not run in CI).
# ---------------------------------------------------------------

fmt:
    uv run ruff format .

lint-fix:
    uv run ruff check --fix .

# Re-vendor an upstream-sourced library into .claude-plugin/scripts/_vendor/
# from the upstream ref recorded in .vendor.jsonc (the only blessed
# mutation path per livespec/SPECIFICATION/constraints.md §"Vendoring
# procedure"). Maintainer-only; NOT run in CI. The family's
# release->bump-pin automation invokes this so cross-repo auto-bump can
# re-vendor. Shim entries (shim: true) are NOT re-vendored.
vendor-update lib:
    uv run python -m livespec_dev_tooling.vendor_update {{lib}}

# ---------------------------------------------------------------
# One-shot migration utilities.
# ---------------------------------------------------------------

# Translate a beads .beads/issues.jsonl export into work-items.jsonl
# records. One-shot — re-running on the same input produces duplicates.
# Use during the Phase D.10 cutover only.
migrate-beads beads_jsonl out_jsonl:
    uv run python3 .claude-plugin/scripts/bin/migrate_beads.py \
        --beads-jsonl {{beads_jsonl}} \
        --work-items-out {{out_jsonl}}

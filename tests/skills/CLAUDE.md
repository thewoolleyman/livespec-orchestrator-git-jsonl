# tests/skills/

Tests that validate the plugin's SKILL.md files (under
`.claude-plugin/skills/`) rather than a Python source module — so this
directory does NOT mirror a `.claude-plugin/scripts/` source tree (the
`tests_mirror_pairing` check enforces source→test only, so a
source-less test directory is allowed here).

- `test_skill_invocation_paths.py` — guards that every SKILL.md
  `## Invocation` fenced run command uses the
  `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/bin/<name>.py"` form (never
  `uv run`, never a bare `.claude-plugin/scripts/...` literal) and that
  the referenced path resolves to a real file once
  `${CLAUDE_PLUGIN_ROOT}/` maps to `.claude-plugin/`. This is the CI
  guard for li-m4q4h5: it fails if a SKILL.md quotes an invocation that
  would break in the flattened installed plugin cache.

Rules: keep these tests purely structural — they parse SKILL.md text
and assert on path tokens, never invoke the wrappers. Coverage is
exercised by parametrizing over every discovered invocation command.

"""Plugin-manifest and skill-surface conformance.

SPECIFICATION/contracts.md fixes the plugin namespace in
`.claude-plugin/plugin.json` and enumerates the required seven-skill
surface. These pin both against the shipped plugin tree.
"""

import json
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]

# The seven REQUIRED skills contracts.md enumerates under "The
# seven-skill surface" (four heavyweight authored + three
# thin-transport). `needs-attention` is an additional read/awareness
# binding documented under the `next` section, not part of this seven.
_CONTRACT_SKILLS = (
    "capture-impl-gaps",
    "capture-spec-drift",
    "capture-work-item",
    "implement",
    "list-work-items",
    "next",
    "detect-impl-gaps",
)


def test_the_plugin_namespace_is_fixed_by_the_manifest() -> None:
    """contracts.md "Plugin namespace": the manifest fixes the namespace.

    The slash-command namespace `/livespec-orchestrator-git-jsonl:` is
    fixed by `.claude-plugin/plugin.json`. Control: a renamed manifest
    would break the cross-boundary invocation prefix and this assertion.
    """
    manifest = json.loads(
        (_REPO_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    assert manifest["name"] == "livespec-orchestrator-git-jsonl"


def test_every_contract_named_skill_ships_a_skill_md() -> None:
    """contracts.md "The seven-skill surface": each required skill ships.

    Every one of the seven contract skills MUST ship a SKILL.md under
    `.claude-plugin/skills/<name>/`. Control: a dropped skill directory
    fails here.
    """
    skills_root = _REPO_ROOT / ".claude-plugin" / "skills"
    for name in _CONTRACT_SKILLS:
        assert (skills_root / name / "SKILL.md").is_file()

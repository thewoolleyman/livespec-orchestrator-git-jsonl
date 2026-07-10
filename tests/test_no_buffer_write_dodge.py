"""Guard: no first-party `.py` may dodge `no_write_direct` via `.buffer.write`.

PR #223 (commit e09232f8) "resolved" `no_write_direct` warnings by rewriting
banned `sys.stdout.write` / `sys.stderr.write` calls into
`sys.stdout.buffer.write(...)` / `sys.stderr.buffer.write(...)`. The shared
check's matcher is an exact-AST set
(`_BANNED_CALL_TARGETS = {"sys.stdout.write", "sys.stderr.write"}`), so the
`.buffer.write` form is invisible to it — the violation was made undetectable
rather than genuinely resolved. That is detection-evasion, not a fix.

This guard asserts the dodge stays gone across the ENTIRE first-party `.py`
universe (the same git-index-derived set `no_write_direct` itself scans, via
`iter_first_party_py_files`): honest writes must route through the check's
sanctioned exemption surface (`supervisor_entry_files`) instead of hiding
behind `.buffer.write`.
"""

from __future__ import annotations

from pathlib import Path

from livespec_dev_tooling.config import iter_first_party_py_files

_REPO_ROOT = Path(__file__).resolve().parents[1]
_BANNED_FRAGMENTS = ("sys.stdout.buffer.write", "sys.stderr.buffer.write")


def _buffer_write_offenders(*, sources: list[tuple[str, str]]) -> list[str]:
    offenders: list[str] = []
    for label, text in sources:
        for lineno, line in enumerate(text.splitlines(), start=1):
            if any(fragment in line for fragment in _BANNED_FRAGMENTS):
                offenders.append(f"{label}:{lineno}")
    return offenders


def test_scanner_flags_a_buffer_write_dodge() -> None:
    # Positive control exercising the offender-detection branch: a synthetic
    # source carrying the dodge is flagged at its exact line.
    synthetic = "import sys\n_ = sys.stderr.buffer.write(b'x')\n"
    assert _buffer_write_offenders(sources=[("synthetic.py", synthetic)]) == ["synthetic.py:2"]


def test_no_first_party_buffer_write_dodge() -> None:
    sources = [
        (rel.as_posix(), (_REPO_ROOT / rel).read_text(encoding="utf-8"))
        for rel in iter_first_party_py_files(repo_root=_REPO_ROOT)
    ]
    offenders = _buffer_write_offenders(sources=sources)
    assert offenders == [], (
        "first-party code must not use `sys.stdout.buffer.write` / "
        "`sys.stderr.buffer.write` to dodge the no_write_direct check; route "
        f"honest writes through the sanctioned exemption surface. Offenders: {offenders}"
    )

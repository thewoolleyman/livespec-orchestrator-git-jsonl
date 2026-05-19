"""livespec_impl_plaintext — JSONL-backed implementation plugin for livespec.

Public package layout:

- `livespec_impl_plaintext.types` — work-item and memo dataclasses, plus the
  Spec Reader snapshot / diff dataclasses.
- `livespec_impl_plaintext.store` — JSONL store primitives (append + read +
  materialize + filter) for work-items and memos files.
- `livespec_impl_plaintext.spec_reader` — Spec Reader adapter implementing
  the four required capabilities defined in
  livespec/SPECIFICATION/contracts.md
  §"Spec Reader required-capability surface".
- `livespec_impl_plaintext.errors` — exception types for the expected-error
  surface (missing file, malformed line, schema violation, version not
  found).

The store and spec_reader modules are consumed by every heavyweight skill;
the types module is consumed by every skill plus the thin-transport CLIs.
"""

# Changelog

## v0.1.1 (2026-10-22)

- README: Arabic examples written as escape sequences; the example prints with `ascii()`.
- Code style fixes from ruff. No behavior change.
- Add a CI workflow for ruff and tests.

## v0.1.0 (2026-10-21)

First tagged release. Restore logical reading order for Arabic text extracted from PDFs.

- Add logicaline, logical order for Arabic PDF glyphs.
- Keep glyphs intact when reversing Arabic runs, speed up line grouping, add OS setup steps

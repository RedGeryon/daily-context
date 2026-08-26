# Agent entry point

This repository builds and distributes Daily Context. It does not contain a user's work record.

## If the user wants to use Daily Context

1. Read `README.md` for installation and the privacy boundary.
2. Install with `./install.sh`, or use the native Codex/Claude plugin manifest.
3. Initialize a work record with `daily-context init ./daily_context --workspace .`.
4. Use the `daily-context` skill for judgment-heavy updates and weekly synthesis.
5. Enable automatic private session capture only when requested: `daily-context auto enable --host <codex|claude> --workspace .`.

Auto capture is evidence collection, not verification. Never promote an automatically captured statement to a verified fact without checking its source.

## If the user wants to contribute

- Keep the core CLI dependency-free.
- Preserve append-only raw evidence and record ledgers.
- Treat registries, indexes, `CONTEXT.md`, and summaries as generated or derived views.
- Run `./scripts/test.sh` before handing off changes.
- Do not add real transcripts, credentials, personal data, or customer information to fixtures.

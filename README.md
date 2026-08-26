# Daily Context

Daily Context gives a person and their AI agents one durable record of what happened, why decisions were made, what remains open, and where the evidence lives.

It keeps the current handoff small while preserving the full history. Raw sources, facts, decisions, tasks, work products, daily summaries, and weekly plans remain distinct and traceable.

Requirements: Python 3.10 or newer. The CLI has no third-party runtime dependencies.

## Quick start

```sh
# From a downloaded or cloned copy of this repository:
cd daily-context
./install.sh

daily-context init ./daily_context \
  --workspace . \
  --profile general \
  --workstream "Product launch" \
  --goal "Describe the outcome I am working toward"
```

Then tell Codex or Claude:

> Update daily context from this work.

or invoke the installed skill directly:

- Codex: `$daily-context`
- Claude Code: `/daily-context`

## Automatic updates

Automatic mode captures each completed AI session as private source material:

```sh
daily-context auto enable --host codex --workspace .
daily-context auto enable --host claude --workspace .
```

Run the command once for each host you use in that workspace. Existing hook settings are preserved and backed up before the first change.
The generated hook uses the CLI's resolved absolute path, so session capture does not depend on a host application's shell `PATH`.

Auto mode deliberately does **not** declare the session's statements true. It stores a session receipt and an available transcript under the Git-ignored `raw/` directory, marks the source pending, and refreshes the indexes. The next agent update reviews that evidence and promotes only supported facts, tasks, decisions, and artifacts.

Disable it with:

```sh
daily-context auto disable --host codex --workspace .
```

Disabling stops capture through configuration. It leaves the hook in place so re-enabling does not need another settings change; the hook exits without writing when the mode is off.

## Daily workflow

```sh
# Register source evidence. Copies are private and Git-ignored by default.
daily-context add-source meeting-notes.md --kind meeting --title "Product review"

# Record one sourced claim or action.
daily-context record fact "The launch date moved to Friday" \
  --status reported \
  --sources SRC-2026-08-26-001 \
  --owner alex

daily-context record task "Confirm the launch date with operations" \
  --status open \
  --sources SRC-2026-08-26-001 \
  --owner alex

# Lifecycle changes are appended; the original record stays intact.
daily-context set-status TASK-2026-08-26-001 done --owner alex

daily-context rebuild
daily-context validate
```

For judgment-heavy work, ask the installed skill to do this rather than entering each command manually.

## Weekly workflow

```sh
daily-context weekly
```

This freezes the week's source IDs and creates:

- `synthesis.md` for outcomes, decisions, learning, and reflection;
- `next-week.md` for reconciled tasks and ordered priorities;
- `source-manifest.json` showing exactly what the review used.

Ask the agent to “generate weekly synthesis” to complete those files from the evidence.

## How the record is organized

```text
daily_context/
├── CONTEXT.md                    # bounded current handoff; generated
├── context.config.json
├── registry/                     # generated current tasks, goals, decisions, sources
├── decisions/                    # durable decision records
├── days/YYYY/MM/YYYY-MM-DD/
│   ├── INDEX.md                  # generated day map
│   ├── manifest.json             # source and artifact inventory
│   ├── records.ndjson            # append-only atomic record ledger
│   ├── raw/                      # private originals; Git-ignored
│   ├── derived/summary.md        # source-linked daily synthesis
│   └── work/                     # retained work products
└── weeks/YYYY-Www/
    ├── INDEX.md
    ├── synthesis.md
    ├── next-week.md
    └── source-manifest.json
```

Start at `CONTEXT.md`, then follow the linked day index or a stable record ID. Use `daily-context trace <ID>` to walk a conclusion back to its sources. Search is a fallback, not the entry point.

The `general`, `engineering`, `research`, and `operations` profiles change the suggested review focus, not the underlying evidence model. Edit `PROFILE.md` after initialization to match the user's work, vocabulary, workstreams, and success signals.

## Privacy

- Raw captures are private and ignored by Git by default.
- A public repository should contain derived, redacted records—not private transcripts.
- Do not store credentials, customer secrets, personal data, or restricted production data.
- Use `--reference-only` when evidence must remain in an external controlled location.
- Exact local source locations are kept in ignored `.source-locations.local.json`; tracked manifests contain only safe filenames or relative paths.
- Auto capture has a configurable size limit and records sources as pending review.

See [docs/concepts.md](docs/concepts.md) for the evidence model and [docs/installation.md](docs/installation.md) for native plugin installation.

For another AI editor or agent, use the host-neutral session-end contract in [docs/other-ai-tools.md](docs/other-ai-tools.md).

## Command reference

Run `daily-context --help`. The stable commands are:

- `init`, `status`, `config`
- `add-source`, `record`, `set-status`, `trace`
- `rebuild`, `validate`
- `weekly`
- `auto enable|disable`, `capture-session`

## Project status

This is an initial public-ready implementation. The on-disk schema is versioned as `1`; backward-compatible migrations will be required before changing it.

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

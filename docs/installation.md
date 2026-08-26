# Installation

## Portable installer

From a cloned checkout:

```sh
./install.sh
```

The installer places the dependency-free CLI under the user's local data directory, links `daily-context` into `~/.local/bin`, and installs the shared skill for both Codex and Claude Code. It does not enable hooks or modify a work repository.

Use `./install.sh --codex` or `./install.sh --claude` to install only one skill adapter. Ensure `~/.local/bin` is on `PATH`.

For a nonstandard home location, set `DAILY_CONTEXT_INSTALL_HOME`. The installer also respects `CODEX_HOME` and `CLAUDE_CONFIG_DIR`, so work-specific profiles receive the skill in the profile that is actually active.

## Codex plugin

The repository contains `.codex-plugin/plugin.json` and a root `skills/` directory. A marketplace can reference the repository or a local clone as a Codex plugin.

Codex also discovers a directly installed personal skill under `~/.agents/skills/daily-context`, which is what `install.sh` configures.

## Claude Code plugin

The repository contains `.claude-plugin/plugin.json` and a root `skills/` directory. Test a clone with:

```sh
claude --plugin-dir /absolute/path/to/daily-context
```

The portable installer also copies the skill to `~/.claude/skills/daily-context` for direct use.

## Connect a work repository

From the work repository:

```sh
daily-context init ./daily_context --workspace . --profile general
```

The `--workspace` option writes `.daily-context.json`, a small relative pointer that allows agents and lifecycle hooks to find the record without searching.

## Enable automatic capture

```sh
daily-context auto enable --host codex --workspace .
daily-context auto enable --host claude --workspace .
```

These commands merge a `SessionEnd` hook into `.codex/hooks.json` or `.claude/settings.json`. Existing settings are preserved; an existing file receives a `.bak` backup before modification. Review and trust new hooks through the host's normal trust interface.

For other AI tools, see [other-ai-tools.md](other-ai-tools.md).

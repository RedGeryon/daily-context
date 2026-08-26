#!/bin/sh
set -eu

INSTALL_CODEX=1
INSTALL_CLAUDE=1

if [ "${1:-}" = "--codex" ]; then
  INSTALL_CLAUDE=0
elif [ "${1:-}" = "--claude" ]; then
  INSTALL_CODEX=0
elif [ "${1:-}" != "" ] && [ "${1:-}" != "--all" ]; then
  echo "Usage: ./install.sh [--all|--codex|--claude]" >&2
  exit 2
fi

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
USER_HOME=${DAILY_CONTEXT_INSTALL_HOME:-"${HOME:?HOME is required}"}
USER_DATA_ROOT=${XDG_DATA_HOME:-"$USER_HOME/.local/share"}
INSTALL_ROOT="$USER_DATA_ROOT/daily-context"
BIN_ROOT=${XDG_BIN_HOME:-"$USER_HOME/.local/bin"}

mkdir -p "$INSTALL_ROOT/src" "$INSTALL_ROOT/bin" "$BIN_ROOT"
cp "$SCRIPT_DIR/src/daily_context.py" "$INSTALL_ROOT/src/daily_context.py"
cp "$SCRIPT_DIR/src/daily_context.py" "$INSTALL_ROOT/bin/daily-context"
chmod +x "$INSTALL_ROOT/bin/daily-context"
ln -sf "$INSTALL_ROOT/bin/daily-context" "$BIN_ROOT/daily-context"

if [ "$INSTALL_CODEX" -eq 1 ]; then
  CODEX_SKILL_ROOT="$USER_HOME/.agents/skills"
  mkdir -p "$CODEX_SKILL_ROOT"
  rm -rf "$CODEX_SKILL_ROOT/daily-context"
  cp -R "$SCRIPT_DIR/skills/daily-context" "$CODEX_SKILL_ROOT/daily-context"
fi

if [ "$INSTALL_CLAUDE" -eq 1 ]; then
  CLAUDE_SKILL_ROOT="$USER_HOME/.claude/skills"
  mkdir -p "$CLAUDE_SKILL_ROOT"
  rm -rf "$CLAUDE_SKILL_ROOT/daily-context"
  cp -R "$SCRIPT_DIR/skills/daily-context" "$CLAUDE_SKILL_ROOT/daily-context"
fi

echo "Installed Daily Context $($INSTALL_ROOT/bin/daily-context --version)"
echo "CLI: $BIN_ROOT/daily-context"
if [ "$INSTALL_CODEX" -eq 1 ]; then echo "Codex skill: $USER_HOME/.agents/skills/daily-context"; fi
if [ "$INSTALL_CLAUDE" -eq 1 ]; then echo "Claude skill: $USER_HOME/.claude/skills/daily-context"; fi
echo "Next: daily-context init ./daily_context --workspace ."

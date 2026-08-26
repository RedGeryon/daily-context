#!/bin/sh
set -eu
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)

python3 -m unittest discover -s "$REPO_ROOT/tests" -p 'test_*.py' -v
python3 -m py_compile "$REPO_ROOT/src/daily_context.py"
python3 -m json.tool "$REPO_ROOT/.codex-plugin/plugin.json" >/dev/null
python3 -m json.tool "$REPO_ROOT/.claude-plugin/plugin.json" >/dev/null
python3 -m json.tool "$REPO_ROOT/schemas/config.schema.json" >/dev/null
python3 -m json.tool "$REPO_ROOT/schemas/record.schema.json" >/dev/null

INSTALL_TEST_ROOT=$(mktemp -d "${TMPDIR:-/tmp}/daily-context-install.XXXXXX")
trap 'rm -rf "$INSTALL_TEST_ROOT"' EXIT INT TERM
DAILY_CONTEXT_INSTALL_HOME="$INSTALL_TEST_ROOT" "$REPO_ROOT/install.sh" --all >/dev/null
"$INSTALL_TEST_ROOT/.local/bin/daily-context" --version >/dev/null
test -f "$INSTALL_TEST_ROOT/.agents/skills/daily-context/SKILL.md"
test -f "$INSTALL_TEST_ROOT/.claude/skills/daily-context/SKILL.md"

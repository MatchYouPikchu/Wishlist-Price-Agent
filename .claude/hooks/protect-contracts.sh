#!/bin/bash
# PreToolUse guard: the contracts spine is frozen.
#
# CLAUDE.md says changes to src/agent/contracts.py must be proposed in plan mode
# and reviewed field-by-field — never silently edited. This turns that
# convention from prose into enforcement: any Edit/Write/NotebookEdit targeting
# the contracts file is surfaced for explicit human confirmation ("ask") rather
# than applied silently.
set -euo pipefail

input="$(cat)"

# Pull the target path out of the tool input (Edit/Write use file_path,
# NotebookEdit uses notebook_path). No jq dependency — grep the raw JSON.
path="$(printf '%s' "$input" | grep -oE '"(file_path|notebook_path)"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed -E 's/.*:[[:space:]]*"([^"]*)"/\1/')"

case "$path" in
  */src/agent/contracts.py|src/agent/contracts.py)
    cat <<'JSON'
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "ask",
    "permissionDecisionReason": "src/agent/contracts.py is the FROZEN contracts spine. Per CLAUDE.md, propose the change in plan mode and get it reviewed field-by-field before editing. Confirm only if this edit has been reviewed."
  }
}
JSON
    ;;
  *)
    # Not the contracts file — stay out of the way.
    exit 0
    ;;
esac

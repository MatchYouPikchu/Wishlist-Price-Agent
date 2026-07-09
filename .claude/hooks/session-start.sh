#!/bin/bash
# SessionStart hook: make the project runnable in a fresh (web) session.
#
# Claude Code on the web clones the repo into an empty container, so tests and
# linters do not work until dependencies are installed. This installs them once
# per container (the state is cached after the hook completes). Idempotent and
# non-interactive.
set -euo pipefail

# Only needed in the remote (web) environment; local dev already has a venv.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-.}"

# Installs runtime + dev deps (pytest, ruff) into the project venv.
uv sync --extra dev

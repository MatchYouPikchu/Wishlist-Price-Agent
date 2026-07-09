# CLAUDE.md — agent brief

**What this is.** Wishlist Price Agent: watches a wishlist and alerts when an
item becomes a *genuinely good deal*, not just when a price crosses a number.
Rationale lives in `DESIGN.md`; the ordered roadmap in `PLAN.md`. This file is
the stable brief — keep it ≤50 lines.

## Layout map
- `src/agent/contracts.py` — **frozen** pydantic spine. All cross-component models.
- `src/agent/config.py` — model names, thresholds, budgets (data, no logic).
- `src/agent/pipeline.py` — fetch → match → risk → judge → notify (stub).
- `src/agent/fetchers/` — `allegro.py` (Tier 1 API), `shop_url.py` (Tier 2 URLs).
- `src/agent/llm/` — matcher, risk, judge, composer, extractor; `client.py` wraps
  all calls; `prompts/` holds one versioned `.md` per prompt.
- `src/agent/wishlist.py` — parse `wishlist.yaml` → `WishlistItem` (friendly errors).
- `src/agent/storage.py` — SQLite (v1); interface stays stable for DynamoDB (v2).
- `src/agent/notify/email.py` — SMTP (v1) → SES (v2).
- `src/agent/costs.py` — per-component cost ledger + budget assertion.
- `evals/` — mirrors the LLM component list; the eval IS the test suite.
- `tests/` — plain unit tests for the boring code.
- `docs/plans/` — reviewed per-WP execution plans; `.claude/agents/` — subagents.

## Commands
- `uv sync --extra dev` — install.
- `uv run pytest` — tests.
- `uv run ruff check .` / `uv run ruff format .` — lint / format.
- Evals (once they exist): `uv run python -m evals.run_matcher`, etc.

## Conventions
- **Contracts in `contracts.py` are frozen.** Propose changes in plan mode and
  get them reviewed field-by-field. Never silently edit.
- Structured outputs only — LLM components return validated pydantic models.
- No orchestration frameworks. Plain Python.
- **No new dependencies without asking.**
- Prompts are versioned markdown under `llm/prompts/` so every change is a diff.
- Eval-driven for LLM work: write/extend the golden dataset before the prompt;
  "done" means the eval passes, not that the code looks right.
- One work package per session (see `PLAN.md`). Each ends with a `DECISIONS.md`
  entry and a commit tagged with the WP number.
- Before merging a WP PR, run the `plan-guardian` subagent
  (`.claude/agents/plan-guardian.md`) on the diff; fix BLOCKING findings.
- Human-only tasks (🧑 in `PLAN.md`) — credentials, labeling, budget/threshold
  calls — are not delegated.

## Durable facts learned in sessions
_(append below as they come up; keep short)_
- Python ≥3.11 (uses `enum.StrEnum`, `datetime.UTC`).

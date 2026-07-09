# Wishlist Price Agent

An agent that watches a wishlist and tells you when something on it becomes a
**genuinely good deal** — not just when a price crosses a threshold.

> **Status:** foundation only. WP-0 (scaffold) and WP-1 (contracts) are done.
> The walking skeleton, the LLM brain, and AWS productionization follow — see
> [`PLAN.md`](PLAN.md) for the ordered roadmap and [`DESIGN.md`](DESIGN.md) for
> the what and why. This README is rewritten as a product page last (WP-15).

## What's here today

- **`src/agent/contracts.py`** — the frozen pydantic spine: `WishlistItem`,
  `RawListing`, `MatchVerdict`, `RiskVerdict`, `DealVerdict`,
  `PriceObservation`, `Alert`, `CostEntry`, `RunReport`. Every component is
  built against these.
- **`wishlist.yaml`** — editing this file is the UI.
- The module tree (`fetchers/`, `llm/`, `notify/`, `storage`, `pipeline`,
  `costs`) as documented stubs, each pointing at the work package that fills it.

## Develop

**Working on this repo with a coding agent? Start at
[`docs/WORKFLOW.md`](docs/WORKFLOW.md)** — the five-step loop, copy-paste
prompts, and who decides what.

Uses [uv](https://docs.astral.sh/uv/).

```bash
uv sync --extra dev      # install
uv run pytest            # tests (contracts round-trip suite)
uv run ruff check .      # lint
uv run ruff format .     # format
```

## Layout

See [`PLAN.md` §2](PLAN.md) for the full repository map. In short: contracts are
frozen in one file, prompts will live as versioned markdown, and `evals/`
mirrors the LLM component list one-to-one.

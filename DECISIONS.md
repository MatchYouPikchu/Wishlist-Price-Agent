# Decisions

Running log. One entry per work package: what was decided, what was rejected,
why. The agent drafts; the human edits.

---

## WP-0 · Scaffold

**Decided.** `uv`-managed project (`pyproject.toml`, hatchling build), `src/`
layout with the package at `src/agent`, `pytest` + `ruff` (lint select
`E,F,I,UP,B`, line length 100) as the dev toolchain. CI (`.github/workflows/ci.yml`)
runs lint, format-check, and tests on every push/PR. The full module tree from
PLAN.md §2 is created as documented stubs so imports resolve and each file
points at the work package that fills it.

**Rejected.** A flat (non-`src/`) layout — `src/` prevents accidentally
importing the working tree instead of the installed package during tests. Poetry
— the plan mandates `uv`. Pre-committing a placeholder SQLite DB — deferred to
WP-2 where storage actually exists.

**Why.** WP-0's definition of done is "CI green" with a runnable placeholder
test; everything here serves that while reserving the exact repository shape the
later WPs expect.

---

## WP-1 · Contracts ⭐

**Decided.** All cross-component models live in the single file
`src/agent/contracts.py` and are **frozen** (`model_config` = `frozen=True`,
`extra="forbid"`). Models: `WishlistItem`, `RawListing`, `MatchVerdict`,
`RiskVerdict`, `DealVerdict`, `PriceObservation`, `Alert`, `RunReport`, plus a
supporting `CostEntry` (a ledger line inside `RunReport`) and four `StrEnum`s
(`Condition`, `VerdictSource`, `RiskLevel`, `AlertKind`).

Key field-level choices worth a human review:
- **Money is `Decimal` + explicit `currency` string**, never `float`. A
  precision round-trip test guards this.
- **Listings are referenced by `(listing_source, listing_source_id)`** in every
  verdict rather than by a synthetic listing UUID — the source's own id is the
  natural key and avoids a minting step in the fetchers.
- **Verdicts carry provenance**: `MatchVerdict.source` (`rule` vs `llm`) and an
  optional `model` id, so the confidence cascade (WP-10) and cost ledger (WP-7)
  have the data they need without a schema change later.
- **`RawListing.total_price`** and **`RunReport.total_cost_usd`** are computed
  properties, not stored fields — derived data stays out of the serialized
  contract.
- Timestamps are timezone-aware UTC `datetime`.

**Definition of done met.** `tests/test_contracts.py` proves every exported
model JSON- and Python-round-trips, is immutable, forbids extra fields, and
enforces its bounds; a guard test fails if a model is added to `__all__` without
a sample. Frozen status is documented in `CLAUDE.md`.

**Rejected.** A shared `Money` value-object model (overkill for v1 — a `Decimal`
+ `currency` pair on each model is enough); `use_enum_values=True` (keeping enum
members in Python space makes component code clearer; the string still goes on
the wire); splitting contracts across per-component files (the single-file spine
is deliberately impossible to miss).

**Open for 🧑 review.** Field names and the deal-breaker/must-have vocabulary on
`WishlistItem` are the product's PM surface — confirm they match how you'd
actually describe a wishlist item before they harden.

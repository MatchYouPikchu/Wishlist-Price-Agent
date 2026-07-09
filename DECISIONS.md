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

---

## WP-2 · Storage + wishlist loader

**Decided.** `src/agent/storage.py` (`Storage` class over stdlib `sqlite3`) and
`src/agent/wishlist.py` (`load_wishlist` + `WishlistError`). Five choices, all
pre-agreed in `docs/plans/WP-2.md`:

- **D1 — JSON payload + query columns.** Every row stores the full contract
  model as `model_dump_json()` and is rehydrated with `model_validate_json()`;
  typed columns exist only for what we filter/order on. Storage never re-models
  the domain, so the DynamoDB port (WP-12) is a backend swap, not a re-design.
- **D2 — money as TEXT.** The `price` column stores the exact `Decimal` string,
  never SQLite `REAL`. A round-trip test asserts `Decimal("19.99")` survives.
- **D3 — CI dry-run only initializes a throwaway DB.** PLAN.md's "DB file
  committed back by CI dry-run" is **deferred to WP-5**: committing state from
  PR CI is a footgun, and the cron in `run.yml` is what actually accumulates
  history. `*.db` stays gitignored until then.
- **D4 — feedback uses primitives.** `record_feedback(alert_id, verdict,
  created_at)` with `verdict in {up, down}`; **no `Feedback` contract added** —
  WP-13 defines that when it knows what the endpoint needs.
- **D5 — timestamps as ISO-8601 UTC TEXT** in query columns; payload JSON is the
  source of truth.

Interface discipline for the v2 port: no SQL types/cursors in signatures,
lookups keyed by `item_id` / `(source, source_id)` / `alert_id`, no joins.
Alerts are idempotent on `Alert.id` (`record_alert` returns `False` on a repeat).

**Definition of done met.** `tests/test_storage.py` and `tests/test_wishlist.py`
(48 tests total, all green) cover round-trips, Decimal precision, newest-first
ordering + limit, `latest_observation`, alert idempotency, `mark_alert_sent`,
feedback validation, and every wishlist error path (missing file, missing
`items`, duplicate ids, invalid entry named by id-or-position, empty list).
CI gains a storage schema dry-run step; `wishlist.py` added to the CLAUDE.md map.

**Rejected.** Storing prices as `REAL` (loses cents); an ORM or a `Feedback`
contract (both premature); committing the DB from PR CI (D3); raising raw
`ValidationError`/`YAMLError` from the loader (the wishlist is hand-edited, so
errors must name the offending entry).

**Contracts untouched** — `contracts.py` was sufficient as frozen.

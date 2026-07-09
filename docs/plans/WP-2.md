# WP-2 execution plan — Storage + wishlist loader

Session-ready plan for the executing agent. Reviewed by 🧑 before execution;
deviations require a note in the session summary and, if they touch design,
a DECISIONS.md line. Contracts in `src/agent/contracts.py` are frozen and
sufficient for this WP — **no contract changes are needed or permitted here**.

## Goal

Two boring-but-load-bearing pieces of the walking skeleton:

1. `src/agent/storage.py` — SQLite persistence for observations, alerts, and
   feedback, behind an interface that survives the DynamoDB port (WP-12).
2. `src/agent/wishlist.py` — parse `wishlist.yaml` into `list[WishlistItem]`
   with human-friendly validation errors. (New module; add one line to the
   CLAUDE.md layout map.)

## Out of scope

- Fetchers, notifier, pipeline wiring (WP-3/4/5).
- DynamoDB implementation (WP-12) — only interface discipline for it.
- Feedback HTTP endpoint (WP-13) — only the table exists now.
- Committing a DB file back from CI — deferred to WP-5 (see decision D3).
- Any LLM code, any new dependencies (`sqlite3` is stdlib; `pyyaml` is
  already a dependency).

## Design decisions (pre-made; flag in DECISIONS.md)

- **D1 — JSON payload + query columns.** Each row stores the full contract
  model as JSON (`model_dump_json`, round-trip guaranteed by WP-1 tests) plus
  typed columns only for what we query on. Rehydrate via
  `Model.model_validate_json`. Storage never re-models the domain.
- **D2 — Money as TEXT.** The `price` query column stores the `Decimal` as its
  exact string. Never REAL. Comparisons happen in Python after rehydration;
  v1 volumes make this a non-issue.
- **D3 — CI dry-run only proves schema init.** PLAN.md's "DB file committed
  back by CI dry-run" is deferred: committing from PR CI is a footgun, and the
  thing that genuinely accumulates history is WP-5's cron (`run.yml`), which
  is where commit-back lands. WP-2's CI step just initializes a throwaway DB.
  (`.gitignore` keeps ignoring `*.db` until WP-5 carves out `data/`.)
- **D4 — Feedback rows use primitives.** No `Feedback` contract exists and
  WP-13 will define what it needs; until then `record_feedback(alert_id,
  verdict, created_at)` with `verdict in {"up", "down"}` is enough. Do NOT add
  a model to contracts.py.
- **D5 — Timestamps as ISO-8601 UTC TEXT** in query columns; the payload JSON
  remains the source of truth.

## Deliverable 1 — `src/agent/storage.py`

```python
class Storage:
    """SQLite persistence. Interface is the stable part (DynamoDB in v2)."""

    def __init__(self, path: str | Path) -> None: ...   # opens + init_schema
    def close(self) -> None: ...
    def __enter__(self) / __exit__(...)                  # context manager

    # observations
    def record_observation(self, obs: PriceObservation) -> None: ...
    def observations_for(self, item_id: str, *, limit: int | None = None)
        -> list[PriceObservation]: ...                   # newest first
    def latest_observation(self, item_id: str, source: str, source_id: str)
        -> PriceObservation | None: ...

    # alerts (Alert.id is the idempotency key)
    def record_alert(self, alert: Alert) -> bool: ...    # False if id exists
    def alert_exists(self, alert_id: str) -> bool: ...
    def alerts_for(self, item_id: str) -> list[Alert]: ...
    def mark_alert_sent(self, alert_id: str, sent_at: datetime) -> None:
        ...  # rehydrate, model_copy(update={"sent_at": ...}), rewrite row

    # feedback (D4)
    def record_feedback(self, alert_id: str, verdict: str,
                        created_at: datetime) -> None: ...
```

Interface rules for the DynamoDB port: no SQL types or cursors in signatures;
lookups keyed by `item_id` / `(source, source_id)` / `alert_id`; no joins.

Schema (idempotent `CREATE TABLE IF NOT EXISTS`, executed in `__init__`):

```sql
CREATE TABLE IF NOT EXISTS observations (
  rowid_pk    INTEGER PRIMARY KEY AUTOINCREMENT,
  item_id     TEXT NOT NULL,
  listing_source    TEXT NOT NULL,
  listing_source_id TEXT NOT NULL,
  price       TEXT NOT NULL,          -- exact Decimal string (D2)
  currency    TEXT NOT NULL,
  available   INTEGER NOT NULL,
  observed_at TEXT NOT NULL,          -- ISO-8601 UTC (D5)
  payload     TEXT NOT NULL           -- full PriceObservation JSON (D1)
);
CREATE INDEX IF NOT EXISTS idx_obs_item
  ON observations(item_id, observed_at);
CREATE INDEX IF NOT EXISTS idx_obs_listing
  ON observations(item_id, listing_source, listing_source_id, observed_at);

CREATE TABLE IF NOT EXISTS alerts (
  id         TEXT PRIMARY KEY,        -- Alert.id (idempotency)
  kind       TEXT NOT NULL,
  item_id    TEXT NOT NULL,
  created_at TEXT NOT NULL,
  sent_at    TEXT,
  payload    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_alerts_item ON alerts(item_id, created_at);

CREATE TABLE IF NOT EXISTS feedback (
  rowid_pk   INTEGER PRIMARY KEY AUTOINCREMENT,
  alert_id   TEXT NOT NULL,
  verdict    TEXT NOT NULL CHECK (verdict IN ('up', 'down')),
  created_at TEXT NOT NULL
);
```

Also add to `config.py`: `DB_PATH: str = "data/wishlist.db"` (data, no logic).

## Deliverable 2 — `src/agent/wishlist.py`

```python
class WishlistError(Exception):
    """Raised when wishlist.yaml is missing, malformed, or inconsistent."""

def load_wishlist(path: str | Path) -> list[WishlistItem]: ...
```

Behaviour:
- File shape: top-level `items:` list (matches the committed `wishlist.yaml`).
- Missing file / unparseable YAML / missing `items` key → `WishlistError`
  with the path in the message.
- A pydantic `ValidationError` on item N is re-raised as `WishlistError`
  naming the item's `id` (or index if `id` itself is missing) plus the
  underlying field errors — the user edits YAML by hand; errors must say
  *which entry* is wrong.
- Duplicate `id`s → `WishlistError` listing the duplicates.
- Empty `items: []` is valid (returns `[]`) — an emptied wishlist is not an
  error.

## Tests (definition of done, all under `tests/`)

`tests/test_storage.py`:
- fresh file: constructor creates DB + schema; opening twice is idempotent.
- observation round-trip: record → `observations_for` returns an equal model;
  `Decimal("19.99")` survives exactly.
- ordering + limit: newest first, `limit` respected.
- `latest_observation` picks the newest for the (item, source, source_id)
  triple and returns `None` when absent.
- alert idempotency: second `record_alert` with the same id returns `False`
  and leaves one row; `alert_exists` agrees.
- `mark_alert_sent` sets `sent_at` on the rehydrated model.
- feedback: row lands; invalid verdict raises (CHECK or Python-side).

`tests/test_wishlist.py`:
- committed `wishlist.yaml` parses into 2 items (guards the sample staying
  valid against the contract).
- duplicate ids rejected; error names them.
- invalid field (e.g. `target_price: 0`) → `WishlistError` naming the entry.
- missing file and missing `items` key → `WishlistError`.
- empty list → `[]`.

CI: extend `ci.yml` with a schema dry-run step:
`uv run python -c "from agent.storage import Storage; Storage('/tmp/dryrun.db')"`.

## Session checklist (from PLAN.md §4)

1. `uv run pytest` and `uv run ruff check . && uv run ruff format --check .`
   green before claiming done.
2. `DECISIONS.md`: WP-2 entry covering D1–D5 (decided / rejected / why).
3. `CLAUDE.md`: add `wishlist.py` to the layout map (one line, keep ≤50 lines).
4. Commit message tagged `WP-2`; push to the designated branch.
5. Do NOT touch `src/agent/contracts.py` (a PreToolUse hook will challenge
   you if you try — that is by design).
